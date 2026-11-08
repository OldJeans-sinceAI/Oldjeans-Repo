"""Fixed Next-button walkthrough, real local API calls, isolated mock only."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from examples.yext_client import YextClient
from app.domain import read_back_value

BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8029')
MOCK = os.getenv('TEST_MOCK_BASE', 'http://127.0.0.1:8819')
OUT = Path(os.getenv('BROWSER_ARTIFACTS', '/tmp/ojr-presentation-proof'))
OUT.mkdir(parents=True, exist_ok=True)
expect.set_options(timeout=60000)


def main():
    checks, errors, external = [], [], []
    client = YextClient(base_url=MOCK)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=str(Path.home()/'.cache/ms-playwright/chromium-1223/chrome-linux64/chrome'))
        page = browser.new_page(viewport={'width':1440,'height':1050})
        page.set_default_timeout(60000)
        page.on('pageerror', lambda e: (errors.append(str(e)), print('BROWSER ERROR:', str(e), flush=True)))
        page.on('request', lambda r: external.append(r.url) if not r.url.startswith(BASE) and not r.url.startswith('data:') else None)
        print('Opening presentation browser', flush=True)
        page.goto(BASE)
        next_button = page.locator('[data-presentation-next]')
        expect(next_button).to_be_enabled()
        health = page.request.get(BASE+'/api/v1/health').json()
        assert health['mode']=='mock' and health['presentation_mode'] and not health['reply_interpreter']['configured']
        checks.append('Presentation is isolated mock and Gemini is disabled')

        def phase(value, chapter=None):
            print('Expect:',value,chapter,flush=True)
            expect(page.locator('[data-presentation-phase]')).to_have_attribute('data-presentation-phase',value)
            if chapter is not None: expect(page.locator('[data-presentation-phase]')).to_have_attribute('data-presentation-chapter',str(chapter))
        def advance(value, chapter=None):
            expect(next_button).to_be_enabled()
            next_button.click()
            phase(value,chapter)
            assert page.locator('.pt-error').count()==0, page.locator('.pt-error').inner_text() if page.locator('.pt-error').count() else ''
        def shot(name): page.screenshot(path=str(OUT/(name+'.png')), full_page=True)
        def current(): return page.evaluate('presentation.proposal')
        def shown(p): return read_back_value(client.get_entity(p['entity_id'])['hours'],p['change'])

        phase('start')
        shot('00-ready')
        advance('scan')
        expect(next_button).to_be_enabled(timeout=300000)
        run=page.evaluate('presentation.run')
        assert run['status']=='COMPLETED' and run['processed_businesses']==3032 and run['failed_businesses']==0
        assert page.request.get(BASE+'/api/v1/operator/messages').json()['total']==0
        checks.append('Full 3032-entity scan uses actual results and produces no automatic message or decision')
        shot('01-detect')
        advance('suggest',0)
        p=current(); assert p['entity_id']=='FI-D0003'
        original_whatsapp_hours=client.get_entity(p['entity_id'])['hours']
        shot('02-suggest')
        # Double click cannot create two messages or jump past Contact.
        page.evaluate('''() => { const b=document.querySelector('[data-presentation-next]'); b.click(); b.click(); }''')
        phase('contact',0)
        expect(next_button).to_be_enabled()
        assert page.request.get(BASE+'/api/v1/operator/messages').json()['total']==1
        expect(page.locator('.pt-message')).to_contain_text('We propose')
        shot('03-contact')
        advance('owner',0)
        expect(page.locator('#whatsapp-demo .wa-window')).to_be_visible()
        assert page.locator('#whatsapp-demo [data-decision]').count()==2
        before=shown(p)
        assert page.request.get(BASE+'/api/v1/proposals/'+p['proposal_id']).json()['decision_status']=='PENDING'
        shot('04-whatsapp')
        advance('result',0)
        assert shown(p)==p['change']['hours']
        assert page.evaluate('presentation.result.application_status')=='SUCCEEDED'
        checks.append('WhatsApp owner approval via Next is a real decision with independent mock read-back')
        shot('05-approved')

        advance('suggest',1)
        p=current(); assert p['entity_id']=='FI-D0002'
        before=shown(p)
        advance('contact',1); advance('owner',1)
        expect(page.locator('#email-demo .cm-monitor')).to_be_visible()
        assert page.locator('#email-demo [data-decision],#email-demo [data-edit]').count()==0
        shot('06-email')
        advance('preview',1)
        assert shown(p)==before
        expect(page.locator('#email-demo')).to_contain_text('11:00-16:00')
        assert page.request.get(BASE+'/api/v1/proposals/'+p['proposal_id']).json()['decision_status']=='PENDING'
        page.reload(); phase('preview',1)
        expect(next_button).to_be_enabled()
        assert shown(p)==before
        shot('07-email-preview')
        advance('result',1)
        assert shown(p)=='11:00-16:00'
        assert page.evaluate('presentation.result.decision_status')=='EDITED'
        checks.append('Email uses exact-hours reply then CONFIRM; reload rebuilds preview and does not apply early')
        shot('08-edited')

        advance('suggest',2)
        p=current(); assert p['entity_id']=='FI-D0001'
        before=shown(p)
        advance('contact',2); advance('owner',2)
        expect(page.locator('#sms-demo .cm-phone')).to_be_visible()
        assert page.locator('#sms-demo [data-decision],#sms-demo [data-edit]').count()==0
        shot('09-sms')
        advance('preview',2)
        assert shown(p)==before
        shot('10-sms-preview')
        advance('result',2)
        assert shown(p)==before
        assert page.evaluate('presentation.result.decision_status')=='REJECTED'
        assert page.evaluate('presentation.result.application_status')=='NOT_STARTED'
        checks.append('SMS uses NO then CONFIRM; rejected hours remain unchanged with no false applied state')
        shot('11-rejected')
        advance('complete',2)
        page.reload(); phase('complete',2); expect(next_button).to_be_enabled()
        shot('12-complete')
        checks.append('Completion survives reload only after all three server outcomes are verified')
        for width,height in [(1280,800),(960,900),(390,844)]:
            page.set_viewport_size({'width':width,'height':height})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
            shot('complete-'+str(width))
        page.set_viewport_size({'width':1440,'height':1050})
        advance('scan',0)
        expect(next_button).to_be_enabled(timeout=300000)
        advance('suggest',0)
        again=current()
        assert again['entity_id']=='FI-D0003' and again['change']=={'kind':'DATE_HOURS','date':'2026-12-24','hours':'09:00-13:00'}
        assert client.get_entity(again['entity_id'])['hours']==original_whatsapp_hours
        checks.append('Restart restores original mock data and repeats the same case, date, and suggestion')
        advance('contact',0);advance('owner',0)
        page.route('**/api/v1/proposals/*/decisions', lambda route: route.fulfill(status=503,content_type='application/json',body=json.dumps({'error':{'message':'Injected unavailable backend','code':'TEST_UNAVAILABLE'}})))
        next_button.click()
        expect(page.locator('.pt-error')).to_be_visible()
        phase('owner',0)
        expect(next_button).to_be_disabled()
        assert page.request.get(BASE+'/api/v1/proposals/'+again['proposal_id']).json()['decision_status']=='PENDING'
        assert client.get_entity(again['entity_id'])['hours']==original_whatsapp_hours
        checks.append('Unavailable decision API stops the tour without applying or faking success')
        assert not errors,errors
        assert not external,external
        browser.close()
    result={'checks':checks,'browser_errors':errors,'external_requests':external,'mode':'isolated mock','scan_entities':3032}
    (OUT/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__': main()
