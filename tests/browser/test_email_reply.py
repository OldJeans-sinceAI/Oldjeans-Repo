"""Reply-only email/SMS UI against isolated HTTP/FakeYext; set REPLY_CHANNEL=SMS for SMS."""
import copy
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/product'))
from test_backend import FakeClient, FakeData, NOW
from app.service import Service
from app.server import WebServer
from app.domain import read_back_value
from playwright.sync_api import sync_playwright, expect

CHANNEL = os.environ.get('REPLY_CHANNEL', 'EMAIL')
assert CHANNEL in ('EMAIL', 'SMS')
IS_SMS = CHANNEL == 'SMS'
DEVICE = '.cm-phone' if IS_SMS else '.cm-monitor'
COMPOSER = '[data-sms-composer]' if IS_SMS else '[data-email-composer]'
INPUT = '[data-sms-text]' if IS_SMS else '[data-email-text]'
OUTGOING = '.cm-sms-row.outgoing' if IS_SMS else '.cm-email-thread-message.outgoing'
RECEIPT = '.cm-sms-receipt' if IS_SMS else '.cm-email-receipt'

OUT = Path(os.environ.get('BROWSER_ARTIFACTS', '/tmp/ojr-email-reply-proof'))
OUT.mkdir(parents=True, exist_ok=True)
expect.set_options(timeout=30000)

@contextmanager
def mailbox(browser, sandbox=False, failure=None, expired=False):
    with tempfile.TemporaryDirectory(prefix='email-reply-test-') as path:
        data = FakeData()
        data.contacts['A']['preferred_channel'] = CHANNEL
        client = FakeClient()
        client.failure = failure
        extra = dict(mode='sandbox', source_id='A', target_id='TARGET', allow_writes=True) if sandbox else {}
        service = Service(state_dir=path, now=NOW, client=client, data=data, **extra)
        service.cycle(dict(scope='EXPLICIT_DATES', entity_ids=['A'], dates=['2026-12-24']))
        proposal = next(iter(service.store.data['proposals'].values()))
        message = service.create_message(dict(entity_id='A', proposal_ids=[proposal['proposal_id']], delivery_mode='PREVIEW'))
        if expired:
            proposal['expires_at'] = NOW
        server = WebServer(('127.0.0.1', 0), service, sandbox_service=service if sandbox else None)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        context = browser.new_context(viewport={'width': 1440, 'height': 1050})
        page = context.new_page()
        errors, requests = [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: requests.append(r.url) if r.method == 'POST' and r.url.endswith(('/interpret', '/decisions')) else None)
        base = '/sandbox' if sandbox else ''
        entry = message['owner_entry_path'].replace('/customer#', base + '/customer?view=' + CHANNEL.lower() + '#')
        try:
            page.goto('http://127.0.0.1:' + str(server.server_port) + entry)
            if expired:
                expect(page.locator('[data-channel-outcome]')).to_be_visible()
            else:
                expect(page.locator(DEVICE)).to_be_visible()
            yield page, client, proposal, requests
            assert not errors, errors
        finally:
            context.close()
            server.shutdown()
            server.server_close()
            thread.join()

def reply(page, text, duplicate=False):
    if not IS_SMS:
        page.locator('[data-email-reply]').click()
    count = page.locator(OUTGOING).count()
    page.locator(INPUT).fill(text)
    assert page.locator(OUTGOING).count() == count
    if duplicate:
        page.locator(COMPOSER).evaluate('form => { form.requestSubmit(); form.requestSubmit(); }')
    else:
        page.locator(COMPOSER + ' button[type=submit]').click()
    if IS_SMS:
        page.wait_for_function("selector => {const input=document.querySelector(selector); return !input || (!input.disabled && input.value==='');}", arg=INPUT)
    else:
        expect(page.locator(COMPOSER)).to_have_count(0)


def main():
    checks = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=str(Path.home() / '.cache/ms-playwright/chromium-1223/chrome-linux64/chrome'))
        for decision, text, expected in [('APPROVE', 'YES', '07:30-13:00'), ('EDIT', '10:00-16:00', '10:00-16:00'), ('REJECT', 'NO', None)]:
            with mailbox(browser) as (page, client, proposal, requests):
                before = copy.deepcopy(client.entities['A']['hours'])
                if IS_SMS:
                    # Old review bookmarks must also render the reply-only conversation.
                    page.goto(page.url + '&screen=review')
                    expect(page.locator(DEVICE)).to_be_visible()
                    expect(page.locator('.cm-sms-thread a, .cm-phone [data-decision], .cm-phone [data-edit], .cm-phone [data-draft], .cm-phone details, .cm-phone strong, .cm-phone table')).to_have_count(0)
                else:
                    expect(page.locator('.cm-email a, .cm-email [data-decision], .cm-email [data-edit], .cm-email [data-draft], .cm-email details')).to_have_count(0)
                    expect(page.locator('.cm-email-body button, .cm-email-body textarea')).to_have_count(0)
                if decision == 'APPROVE':
                    for w in [1440, 390, 320]:
                        page.set_viewport_size({'width':w, 'height':1050 if w==1440 else 844})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        assert page.locator('.cm-sms-thread' if IS_SMS else '.cm-email-reading').evaluate('el => el.scrollWidth <= el.clientWidth')
                        page.locator(DEVICE).screenshot(path=str(OUT / f'{CHANNEL.lower()}-{w}.png'))
                    page.set_viewport_size({'width':1440, 'height':1050})
                reply(page, text, duplicate=True)
                expect(page.locator('.incoming').last).to_contain_text('Reply CONFIRM')
                assert not client.puts and len(requests) == 1
                page.locator(DEVICE).screenshot(path=str(OUT / f'{decision.lower()}-preview.png'))
                reply(page, 'CONFIRM', duplicate=True)
                expect(page.locator('[data-channel-outcome]')).to_contain_text('Current hours kept.' if decision == 'REJECT' else 'Hours saved and checked.')
                expect(page.locator(RECEIPT)).to_be_visible()
                expect(page.locator(COMPOSER if IS_SMS else '[data-email-reply]')).to_have_count(0)
                assert len([url for url in requests if url.endswith('/decisions')]) == 1
                if decision == 'REJECT':
                    assert not client.puts and client.entities['A']['hours'] == before
                else:
                    assert len(client.puts) == 1
                    assert read_back_value(client.entities['A']['hours'], proposal['change']) == expected
                page.reload()
                expect(page.locator(RECEIPT)).to_be_visible()
                assert len(client.puts) == (0 if decision == 'REJECT' else 1)
                checks.append(f'{decision}: no links; reply preview then explicit confirmation; duplicate-send safe; persisted receipt')
        with mailbox(browser) as (page, client, proposal, requests):
            reply(page, 'CONFIRM')
            assert requests == [] and not client.puts
            reply(page, 'Please close at 15:00 instead')
            expect(page.locator('.incoming').last).to_contain_text("couldn't determine")
            reply(page, 'CONFIRM')
            assert not any(url.endswith('/decisions') for url in requests)
            reply(page, '09:00-15:00')
            reply(page, 'Maybe a bit earlier')
            reply(page, 'CONFIRM')
            assert not client.puts
            reply(page, '09:00-15:00')
            reply(page, 'CANCEL')
            reply(page, 'CONFIRM')
            assert not client.puts
            reply(page, '09:00-15:00')
            page.reload()
            expect(page.locator(DEVICE)).to_be_visible()
            reply(page, 'CONFIRM')
            assert not client.puts
            reply(page, '09:00-15:00')
            reply(page, '10:00-16:00')
            reply(page, 'CONFIRM')
            expect(page.locator('[data-channel-outcome]')).to_contain_text('Hours saved and checked.')
            assert len(client.puts) == 1
            assert read_back_value(client.entities['A']['hours'], proposal['change']) == '10:00-16:00'
            checks.append('No preview/ambiguous/cancelled/reloaded CONFIRM never writes; newest preview replaces old; no LLM needed')
        with mailbox(browser) as (page, client, proposal, requests):
            reply(page, 'YES')
            proposal['version'] += 1
            reply(page, 'CONFIRM')
            assert not client.puts
            expect(page.locator('.incoming').last).to_contain_text("couldn't verify")
            checks.append('Stale proposal version rejected by backend; no write or false success')
        for malformed in ('version', 'preference', 'permission'):
            with mailbox(browser) as (page, client, proposal, requests):
                payload = {'status': 'READY', 'intent': 'APPROVE'}
                if malformed == 'version':
                    payload['decision_draft'] = {'decision': 'APPROVE', 'proposal_version': proposal['version'] + 1}
                elif malformed == 'preference':
                    payload['preference_draft'] = {'frequency': 'PAUSED'}
                else:
                    payload['permission_draft'] = {'day_keys': ['XMAS_EVE']}
                page.route('**/interpret', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(payload)))
                reply(page, 'YES')
                reply(page, 'CONFIRM')
                assert not client.puts and not any(url.endswith('/decisions') for url in requests)
                expect(page.locator('.incoming').last).to_contain_text('No current change')
                checks.append(f'CONFIRM cannot apply a {malformed} draft')
        with mailbox(browser, failure='before') as (page, client, proposal, requests):
            before = copy.deepcopy(client.entities['A']['hours'])
            reply(page, 'YES')
            reply(page, 'CONFIRM')
            expect(page.locator('[data-channel-outcome]')).to_contain_text('WRITE_NOT_VERIFIED')
            expect(page.locator(RECEIPT)).to_contain_text('could not verify')
            expect(page.locator('.journey-steps [aria-current=step]')).to_contain_text('Needs attention')
            expect(page.locator('.journey-steps li.done').last).to_contain_text('Decide')
            expect(page.locator('[data-next-business]')).to_have_count(0)
            assert client.entities['A']['hours'] == before
            checks.append('Write failure shows unverified receipt and actual failed result')
        with mailbox(browser, expired=True) as (page, client, proposal, requests):
            expect(page.locator('[data-channel-outcome]')).to_contain_text('no longer available')
            expect(page.locator('.journey-steps [aria-current=step]')).to_contain_text('Decide')
            expect(page.locator('.journey-steps [aria-current=step]')).to_contain_text('No longer available')
            expect(page.locator('[data-next-business]')).to_have_count(0)
            expect(page.locator(COMPOSER if IS_SMS else '[data-email-reply], [data-email-composer]')).to_have_count(0)
            assert not client.puts
            checks.append('Expired proposal has no reply composer')
        with mailbox(browser, sandbox=True) as (page, client, proposal, requests):
            expect(page.locator('.cm-sms-thread' if IS_SMS else '.cm-email-body')).to_contain_text('TARGET')
            reply(page, '10:00-16:00')
            expect(page.locator('.incoming').last).to_contain_text('TARGET')
            assert not client.puts
            reply(page, 'CONFIRM')
            expect(page.locator('[data-channel-outcome]')).to_contain_text('Hours saved and checked.')
            assert len(client.puts) == 1 and client.puts[0][0] == 'TARGET'
            checks.append('Sandbox warning in email and confirmation; only fake TARGET written after confirmation')
        with mailbox(browser) as (page, client, proposal, requests):
            reply(page, 'YES')
            def lost_response(route):
                route.fetch()
                route.abort('failed')
            page.route('**/decisions', lost_response)
            reply(page, 'CONFIRM')
            expect(page.locator('[data-channel-outcome]')).to_contain_text('Hours saved and checked.')
            assert len(client.puts) == 1
            checks.append('Lost confirmation response refreshes actual status; no automatic retry or false nothing-changed claim')
        browser.close()
    result = {'channel': CHANNEL, 'checks': checks, 'scope': 'Isolated mock HTTP and FakeYext only; Gemini disabled; no real sends or writes'}
    (OUT / 'results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
