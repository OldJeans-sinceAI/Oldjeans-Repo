"""Guided presentation with actual customer choices; isolated mock APIs only."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from examples.yext_client import YextClient
from app.domain import read_back_value

BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8029')
MOCK = os.getenv('TEST_MOCK_BASE', 'http://127.0.0.1:8819')
OUT = Path(os.getenv('BROWSER_ARTIFACTS', '/tmp/ojr-interactive-decide-proof'))
OUT.mkdir(parents=True, exist_ok=True)
expect.set_options(timeout=60000)


def main():
    checks, errors, external = [], [], []
    client = YextClient(base_url=MOCK)
    with sync_playwright() as pw:
        cached = Path.home()/'.cache/ms-playwright/chromium-1223/chrome-linux64/chrome'
        browser = pw.chromium.launch(headless=True, **({'executable_path': str(cached)} if cached.exists() else {}))
        page = browser.new_page(viewport={'width':1440,'height':1050})
        page.set_default_timeout(60000)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: external.append(r.url) if not r.url.startswith(BASE) and not r.url.startswith('data:') else None)
        page.goto(BASE)
        next_button = page.locator('[data-presentation-next]')
        expect(next_button).to_be_enabled()
        health = page.request.get(BASE+'/api/v1/health').json()
        assert health['mode']=='mock' and health['presentation_mode'] and not health['reply_interpreter']['configured']

        def phase(value, chapter=None):
            expect(page.locator('[data-presentation-phase]')).to_have_attribute('data-presentation-phase', value)
            if chapter is not None:
                expect(page.locator('[data-presentation-phase]')).to_have_attribute('data-presentation-chapter', str(chapter))
        def advance(value, chapter=None):
            expect(next_button).to_be_enabled()
            next_button.click()
            phase(value,chapter)
            expect(page.locator('.pt-error')).to_have_count(0)
        def current(): return page.evaluate('presentation.proposal')
        def hours(p): return client.get_entity(p['entity_id'])['hours']
        def stored(p): return page.request.get(BASE+'/api/v1/proposals/'+p['proposal_id']).json()
        def shot(name): page.screenshot(path=str(OUT/(name+'.png')), full_page=True)
        def reply(channel, text):
            if channel=='EMAIL':
                page.locator('[data-email-reply]').click()
                page.locator('[data-email-text]').fill(text)
                page.locator('[data-email-composer] button[type=submit]').click()
                expect(page.locator('[data-email-composer]')).to_have_count(0)
            else:
                page.locator('[data-sms-text]').fill(text)
                page.locator('[data-sms-text]').press('Enter')
                page.wait_for_function('() => smsSending.size === 0')

        # Any outcome is allowed on any channel, one decision per business per run.
        cycles = [('REJECT','APPROVE','EDIT'), ('EDIT','REJECT','APPROVE'), ('APPROVE','EDIT','REJECT')]
        originals = {}
        for cycle, decisions in enumerate(cycles):
            print('Rehearsal',cycle+1, decisions, flush=True)
            advance('scan',0)
            expect(next_button).to_be_enabled(timeout=300000)
            run=page.evaluate('presentation.run')
            assert run['status']=='COMPLETED' and run['processed_businesses']==3032 and run['failed_businesses']==0
            assert page.request.get(BASE+'/api/v1/operator/messages').json()['total']==0
            advance('suggest',0)
            for chapter,(channel,decision) in enumerate(zip(('WHATSAPP','EMAIL','SMS'),decisions)):
                p=current()
                print('Customer choice:',channel,decision,p['entity_id'],flush=True)
                before=hours(p)
                if cycle==0: originals[p['entity_id']]=before
                else: assert before==originals[p['entity_id']]
                advance('contact',chapter)
                advance('decide',chapter)
                expect(next_button).to_have_count(0)
                expect(page.locator('.pt-owner-view')).not_to_have_attribute('inert','')
                assert stored(p)['decision_status']=='PENDING'
                assert page.evaluate('async () => { await nextPresentation(); return presentation.phase; }')=='decide'
                assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                if cycle==0: shot(channel.lower()+'-interactive')
                expected_hours=f'{10+chapter:02}:00-17:00'
                if channel=='WHATSAPP':
                    if cycle==0:
                        page.route('**/api/v1/proposals/*/decisions', lambda route: route.fulfill(status=503, content_type='application/json', body=json.dumps({'error':{'code':'TEST_UNAVAILABLE','message':'Injected unavailable backend'}})))
                        page.locator('[data-decision=REJECT]').click()
                        expect(page.locator('#toast')).to_be_visible()
                        phase('decide',chapter)
                        assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                        page.unroute('**/api/v1/proposals/*/decisions')
                        checks.append('Decision API failure stays at Decide with unchanged data')
                    if decision=='EDIT':
                        page.locator('[data-edit]').click()
                        page.locator('#edit-hours-'+p['proposal_id']).fill(expected_hours)
                        page.locator('[data-edit-preview]').click()
                        expect(page.locator('dialog[open]')).to_be_visible()
                        assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                        page.locator('[data-confirm-edit]').click()
                    elif cycle==2:
                        def unverified(route):
                            response=route.fetch()
                            data=response.json()
                            data['application_status']='REVIEW_REQUIRED'
                            data.pop('verified_at',None)
                            route.fulfill(response=response,json=data)
                        page.route('**/api/v1/proposals/*/result',unverified)
                        page.evaluate("""() => { const b=document.querySelector('[data-decision=APPROVE]'); b.click(); b.click(); }""")
                        phase('result',chapter)
                        expect(next_button).to_be_disabled()
                        expect(page.locator('.pt-content')).to_contain_text('This result needs attention.')
                        expect(page.locator('.pt-verified')).to_have_count(0)
                        page.unroute('**/api/v1/proposals/*/result')
                        page.locator('[data-presentation-refresh]').click()
                        expect(next_button).to_be_enabled()
                        checks.append('Unverified result blocks completion; status refresh reads without resubmitting')
                    else:
                        page.locator('[data-decision='+decision+']').click()
                else:
                    expect(page.locator('.pt-owner-view [data-decision],.pt-owner-view [data-edit]')).to_have_count(0)
                    text='YES' if decision=='APPROVE' else 'NO' if decision=='REJECT' else expected_hours
                    if cycle==0 and channel=='SMS':
                        reply(channel,'maybe around five')
                        phase('decide',chapter)
                        expect(page.locator('.cm-sms-row.incoming').last).to_contain_text("couldn't determine")
                        assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                        checks.append('Ambiguous reply stays uncommitted until an exact replacement is confirmed')
                    reply(channel,text)
                    phase('decide',chapter)
                    expect(page.locator('.pt-owner-view')).to_contain_text('Reply CONFIRM')
                    assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                    if cycle==0 and channel=='EMAIL':
                        page.reload()
                        phase('decide',chapter)
                        expect(page.locator('[data-email-reply]')).to_be_visible()
                        expect(page.locator('.cm-email-thread-message.outgoing')).to_have_count(0)
                        assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                        reply(channel,'CONFIRM')
                        expect(page.locator('.cm-email-thread-message.incoming').last).to_contain_text('No current change')
                        assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                        reply(channel,text)
                        reply(channel,'CANCEL')
                        assert stored(p)['decision_status']=='PENDING' and hours(p)==before
                        reply(channel,text)
                        checks.append('Reload and CANCEL never confirm or replay; a fresh preview is required')
                    if cycle==0: shot(channel.lower()+'-preview')
                    reply(channel,'CONFIRM')
                phase('result',chapter)
                expect(next_button).to_be_enabled()
                r=page.evaluate('presentation.result')
                assert r['decision_status']=={'APPROVE':'APPROVED','EDIT':'EDITED','REJECT':'REJECTED'}[decision]
                if decision=='REJECT':
                    assert r['application_status']=='NOT_STARTED' and hours(p)==before
                    expect(page.locator('.pt-content')).to_contain_text('The current hours stay.')
                else:
                    assert r['application_status']=='SUCCEEDED' and r['verified_at']
                    assert read_back_value(hours(p),p['change'])==(p['change']['hours'] if decision=='APPROVE' else expected_hours)
                checks.append(f'{channel} freely chosen {decision} automatically opens the actual step5 result')
                if cycle==0: shot(channel.lower()+'-result')
                if chapter<2: advance('suggest',chapter+1)
            advance('complete',2)
            labels={'APPROVE':'Approved & saved','EDIT':'Edited & saved','REJECT':'Declined & kept'}
            for i,decision in enumerate(decisions):
                expect(page.locator('.pt-finish-cards h2').nth(i)).to_have_text(labels[decision])
            page.reload();phase('complete',2);expect(next_button).to_be_enabled()
            for i,decision in enumerate(decisions):
                expect(page.locator('.pt-finish-cards h2').nth(i)).to_have_text(labels[decision])
            if cycle==0: shot('complete-actual-choices')
        checks.append('Three repeat rehearsals restore original data; summaries and reload reflect actual choices')
        assert not errors,errors
        assert not external,external
        browser.close()
    result={'checks':checks,'browser_errors':errors,'external_requests':external,'mode':'isolated mock','rehearsals':3,'scan_entities':3032}
    (OUT/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__': main()
