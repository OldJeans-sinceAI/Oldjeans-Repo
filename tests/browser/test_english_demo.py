"""English guided flow with real APIs and Gemini disabled; isolated mock only."""

import csv
import json
import os
import re
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from examples.yext_client import YextClient
from app.domain import read_back_value

BASE = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8025")
MOCK = os.environ.get("TEST_MOCK_BASE", "http://127.0.0.1:8815")
OUT = Path(os.environ.get("BROWSER_ARTIFACTS", "/tmp/ojr-english-demo-proof"))
OUT.mkdir(parents=True, exist_ok=True)
expect.set_options(timeout=60000)


def main():
    checks, errors = [], []
    client = YextClient(base_url=MOCK)
    with (Path(__file__).resolve().parents[2] / "data/customer_contacts.csv").open() as source:
        contacts = {row["entity_id"]: row for row in csv.DictReader(source)}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=str(
                Path.home() / ".cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
            ),
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        context.add_init_script("localStorage.setItem('connect-language', 'ko');")
        page = context.new_page()
        page.set_default_timeout(60000)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE)
        expect(page.locator("#demo-journey")).to_be_visible()
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#language")).to_have_count(0)
        expect(page.locator('[data-demo-action="scan"]')).to_contain_text("3032")
        health = page.request.get(BASE + "/api/v1/health").json()
        assert (
            health["mode"] == "mock" and not health["reply_interpreter"]["configured"]
        ), health
        checks.append(
            "Saved Korean preference is overridden; English guided demo is the default"
        )
        page.screenshot(path=str(OUT / "01-detect.png"), full_page=True)
        page.locator('[data-demo-action="scan"]').click()
        deadline = time.monotonic() + 300
        last = 0
        while time.monotonic() < deadline:
            run = page.request.get(BASE + "/api/v1/operator/fleet-runs").json()["run"]
            if run and run["status"] != "RUNNING":
                break
            if time.monotonic() - last > 20:
                print("Scan:", run["processed_businesses"] if run else 0, flush=True)
                last = time.monotonic()
            page.wait_for_timeout(1000)
        else:
            raise AssertionError("Scan did not finish")
        assert run["status"] == "COMPLETED" and run["processed_businesses"] == 3032, run
        assert page.request.get(BASE + "/api/v1/operator/messages").json()["total"] == 0
        expect(page.locator('[data-demo-action="suggest"]')).to_be_enabled()
        checks.append(
            "Real scan covers all3032 businesses and creates no automatic contact"
        )
        page.locator('[data-demo-action="suggest"]').click()
        expect(page.locator(".journey-card")).to_contain_text(
            "A clear proposal, with a reason."
        )
        expect(page.locator(".schedule")).to_be_visible()
        page.screenshot(path=str(OUT / "02-suggest.png"), full_page=True)
        page.reload()
        expect(page.locator(".journey-card")).to_contain_text(
            "A clear proposal, with a reason."
        )
        checks.append("Selected real proposal and current stage survive reload")
        page.locator('[data-demo-action="contact"]').click()
        expect(page.locator("#demo-owner-link")).to_be_visible()
        expect(page.locator(".journey-message-body")).to_contain_text("Currently shown")
        expect(page.locator(".journey-message-body")).to_contain_text("We propose")
        assert "Jouluaatto" not in page.locator(".journey-message-body").inner_text()
        messages = page.request.get(BASE + "/api/v1/operator/messages").json()["items"]
        assert len(messages) == 1 and messages[0]["language"] == "en"
        assert messages[0]["channel"] == "EMAIL"
        pid = messages[0]["proposal_ids"][0]
        proposal = page.request.get(BASE + "/api/v1/proposals/" + pid).json()
        assert proposal["entity_id"] == "FI-00003", proposal
        assert messages[0]["channel"] == contacts[proposal["entity_id"]]["preferred_channel"]
        assert proposal["decision_status"] == "PENDING"
        initial_hours = client.get_entity(proposal["entity_id"])["hours"]
        saved = page.evaluate("sessionStorage.getItem('connect-demo-journey')")
        assert "token" not in saved and "owner_entry_path" not in saved
        page.screenshot(path=str(OUT / "03-contact.png"), full_page=True)
        page.reload()
        expect(page.locator("#demo-owner-link")).to_be_visible()
        checks.append(
            "English contact preview persists without storing the owner capability in guide state"
        )

        page.locator("#demo-owner-link").click()
        expect(page.locator("[data-email-reply]")).to_be_visible()
        expect(page.locator(".journey-steps [aria-current=step]")).to_contain_text(
            "Decide"
        )
        expect(page.locator("html")).to_have_attribute("lang", "en")
        page.screenshot(path=str(OUT / "04-owner.png"), full_page=True)
        checks.append("First eligible suggestion follows queue order and opens the EMAIL mock")

        page.locator('.journey-return').click()
        expect(page.locator('.journey-steps [aria-current=step]')).to_contain_text('Decide')
        expect(page.locator('.journey-card')).to_contain_text("The owner's decision comes next.")
        page.reload()
        expect(page.locator('.journey-steps [aria-current=step]')).to_contain_text('Decide')
        page.locator('#demo-owner-link').click()
        expect(page.locator('[data-email-reply]')).to_be_visible()
        checks.append('Returning from an undecided owner view stays at Decide, including after reload')

        expect(page.locator("#email-demo .cm-monitor")).to_be_visible()
        assert "view=email" in page.url
        expect(page.locator('.cm-email [data-decision], .cm-email [data-edit], .cm-email details, .cm-email a')).to_have_count(0)
        expect(page.locator('.cm-email-body button, .cm-email-body textarea')).to_have_count(0)
        for width in (1440, 390, 320):
            page.set_viewport_size({"width": width, "height": 1050 if width == 1440 else 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator('.cm-email-reading').evaluate('el => el.scrollWidth <= el.clientWidth')
            page.locator('.cm-monitor').screenshot(path=str(OUT / f"email-monitor-{width}.png"))
        page.set_viewport_size({"width": 1440, "height": 1050})
        expect(page.locator("#whatsapp-demo")).to_have_count(0)
        page.reload()
        expect(page.locator('[data-email-reply]')).to_be_visible()
        page.locator('[data-email-reply]').click()
        page.locator('[data-email-text]').fill("Please close at 15:00 instead")
        expect(page.locator('.cm-email-thread-message.outgoing')).to_have_count(0)
        with page.expect_response(lambda r: r.url.endswith("/interpret")) as response:
            page.locator('[data-email-composer] button[type=submit]').click()
        expect(page.locator('.cm-email-thread-message.incoming')).to_contain_text("Nothing has been changed.")
        expect(page.locator('.cm-email-thread-message.outgoing')).to_contain_text("Please close at 15:00 instead")
        assert client.get_entity(proposal["entity_id"])["hours"] == initial_hours
        interpreted = response.value.json()
        assert interpreted["status"] == "NEEDS_CLARIFICATION"
        assert interpreted["interpretation"]["error_code"] == "NOT_CONFIGURED"
        assert "decision_draft" not in interpreted
        assert page.request.get(BASE + "/api/v1/proposals/" + pid).json()["decision_status"] == "PENDING"
        checks.append("Email uses native reply with no links; ambiguous offline reply leaves hours unchanged; monitor fits320px")
        page.locator('[data-email-reply]').click()
        page.locator('[data-email-text]').fill('07:30-15:00')
        page.locator('[data-email-composer] button[type=submit]').click()
        expect(page.locator('.cm-email-thread-message.incoming').last).to_contain_text('Reply CONFIRM')
        expect(page.locator('.cm-email-thread-message.incoming').last).to_contain_text('07:30-15:00')
        assert client.get_entity(proposal["entity_id"])["hours"] == initial_hours
        page.locator('[data-email-reply]').click()
        page.locator('[data-email-text]').fill('CONFIRM')
        page.locator('[data-email-composer] button[type=submit]').click()
        expect(page.locator('[data-channel-outcome]')).to_contain_text('Hours saved and checked.')
        expect(page.locator('.cm-email-receipt')).to_contain_text('07:30-15:00')
        assert (
            read_back_value(
                client.get_entity(proposal["entity_id"])["hours"], proposal["change"]
            )
            == "07:30-15:00"
        )
        expect(page.locator(".journey-steps [aria-current=step]")).to_contain_text(
            "Apply & confirm"
        )
        checks.append(
            "Confirmed email reply edit works without a model and matches independent mock read-back"
        )
        page.screenshot(path=str(OUT / "05-applied.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUT / "owner-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator(".journey-return").click()
        expect(page.locator(".journey-card")).to_contain_text("07:30-15:00")
        expect(page.locator(".journey-card")).to_contain_text(
            "Hours saved and checked."
        )
        page.screenshot(path=str(OUT / "demo-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        checks.append("Return to guide shows actual outcome; owner and guide fit390px")
        expect(page.locator("[data-refresh-owner]")).to_have_count(0)
        with page.expect_response(lambda r: r.url.endswith("/result")) as refreshed:
            page.locator('[data-demo-action="refresh"]').click()
        assert refreshed.value.json()["application_status"] == "SUCCEEDED"
        expect(page.locator(".journey-card")).to_contain_text("07:30-15:00")
        checks.append("Operator result refresh uses its own proposal, without an owner session")
        page.set_viewport_size({"width": 1440, "height": 1050})

        page.goto(BASE + '/customer?view=email')
        expect(page.locator('[data-next-business]')).to_be_visible()
        expect(page.locator('[data-next-business]')).to_be_in_viewport()
        page.screenshot(path=str(OUT / 'business-complete-page.png'), full_page=True)
        next_requests = []
        def record_navigation(request):
            if request.method == 'POST':
                next_requests.append(request.url)
        page.on('request', record_navigation)
        page.locator('[data-next-business]').click()
        expect(page.locator('[data-demo-action="contact"]')).to_be_visible()
        expect(page.locator('.journey-steps [aria-current=step]')).to_contain_text('Suggest')
        next_state = page.evaluate("JSON.parse(sessionStorage.getItem('connect-demo-journey'))")
        assert next_state['proposalId'] != pid and next_state['runId'] == run['run_id']
        next_proposal = page.request.get(BASE + '/api/v1/proposals/' + next_state['proposalId'], headers={'X-Operator-View': '1'}).json()
        assert next_proposal['entity_id'] != proposal['entity_id']
        assert not next_requests, next_requests
        assert 'next_business' not in page.url
        page.reload()
        expect(page.locator('[data-demo-action="contact"]')).to_be_visible()
        assert page.evaluate("JSON.parse(sessionStorage.getItem('connect-demo-journey')).proposalId") == next_state['proposalId']
        page.remove_listener('request', record_navigation)
        page.screenshot(path=str(OUT / 'next-business-page.png'), full_page=True)
        checks.append('Primary Next business opens a different company at Suggest, reuses the scan, consumes the intent once, and creates no contact or write')

        for decision in ("APPROVE", "REJECT"):
            if decision != "APPROVE":
                page.locator('[data-demo-action="another"]').click()
            expect(page.locator('[data-demo-action="contact"]')).to_be_visible()
            page.locator('[data-demo-action="contact"]').click()
            expect(page.locator("#demo-owner-link")).to_be_visible()
            page.locator("#demo-owner-link").click()
            expect(page.locator('[data-email-reply]')).to_be_visible()
            page.reload()
            expect(page.locator('[data-email-reply]')).to_be_visible()
            current_pid = page.locator('.cm-monitor').get_attribute('id').removeprefix('proposal-')
            current = page.request.get(BASE + "/api/v1/proposals/" + current_pid).json()
            before = client.get_entity(current["entity_id"])["hours"]
            page.locator('[data-email-reply]').click()
            page.locator('[data-email-text]').fill('YES' if decision == 'APPROVE' else 'NO')
            page.locator('[data-email-composer] button[type=submit]').click()
            expect(page.locator('.cm-email-thread-message.incoming').last).to_contain_text('Reply CONFIRM')
            assert client.get_entity(current["entity_id"])["hours"] == before
            page.locator('[data-email-reply]').click()
            page.locator('[data-email-text]').fill('CONFIRM')
            page.locator('[data-email-composer] button[type=submit]').click()
            expect(page.locator(".customer-card").first).to_contain_text(
                "Hours saved and checked."
                if decision == "APPROVE"
                else "Current hours kept."
            )
            after = client.get_entity(current["entity_id"])["hours"]
            if decision == "APPROVE":
                assert (
                    read_back_value(after, current["change"])
                    == current["change"]["hours"]
                )
            else:
                assert after == before
                expect(page.locator('.journey-steps li').last).to_have_class(re.compile(r'\bskipped\b'))
                expect(page.locator('.journey-steps li').last).to_contain_text('No change needed')
                page.screenshot(path=str(OUT / 'business-kept-page.png'), full_page=True)
            page.locator(".journey-return").click()
            expect(page.locator(".journey-card")).to_contain_text(
                "Hours saved and checked."
                if decision == "APPROVE"
                else "Current hours kept."
            )
            checks.append(f"{decision} completes the guided journey without Gemini")

        def resume_channel_suggestion(channel):
            # Resume a known real contact to exercise a specific channel explicitly.
            # This fixture setup does not change normal demo selection or preferences.
            cases = page.request.get(BASE + "/api/v1/operator/cases").json()["items"]
            for case in cases:
                contact = contacts.get(case["entity_id"], {})
                if (case["action"] != "SUGGEST" or case["target_date"] != "2026-12-24"
                    or contact.get("preferred_channel") != channel
                    or contact.get("opted_out_of_suggestions") == "1"):
                    continue
                response = page.request.get(
                    BASE + "/api/v1/proposals/" + case["proposal_id"],
                    headers={"X-Operator-View": "1"},
                )
                assert response.ok, response.status
                target = response.json()
                if target["decision_status"] == "PENDING":
                    page.evaluate("saved => sessionStorage.setItem('connect-demo-journey', JSON.stringify(saved))", {
                        "stage": 2, "date": "2026-12-24", "runId": run["run_id"],
                        "proposalId": target["proposal_id"],
                    })
                    page.reload()
                    return
            raise AssertionError(f"No pending {channel} fixture is available")

        # Plain SMS uses only replies, including the explicit final confirmation.
        for decision in ("EDIT", "APPROVE", "REJECT"):
            resume_channel_suggestion("SMS")
            page.locator('[data-demo-action="contact"]').click()
            expect(page.locator("#demo-owner-link")).to_have_attribute("href", re.compile(r"view=sms"))
            page.locator("#demo-owner-link").click()
            expect(page.locator("#sms-demo .cm-phone")).to_be_visible()
            page.reload()
            expect(page.locator("#sms-demo .cm-phone")).to_be_visible()
            expect(page.locator(".cm-sms-thread a, .cm-phone [data-decision], .cm-phone [data-edit], .cm-phone [data-draft], .cm-phone details, .cm-phone table, .cm-phone strong, .cm-phone .cm-response")).to_have_count(0)
            active_pid = page.locator(".cm-phone").get_attribute("id").removeprefix("proposal-")
            active = page.request.get(BASE + "/api/v1/proposals/" + active_pid).json()
            before = client.get_entity(active["entity_id"])["hours"]
            if decision == "EDIT":
                page.screenshot(path=str(OUT / "sms-page.png"), full_page=True)
                for width in (390, 320):
                    page.set_viewport_size({"width": width, "height": 844})
                    page.locator(".cm-phone").screenshot(path=str(OUT / f"sms-{width}.png"))
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert page.locator(".cm-sms-thread").evaluate("el => el.scrollWidth <= el.clientWidth")
                page.set_viewport_size({"width": 1440, "height": 1050})
            page.locator('[data-sms-text]').fill('10:00-16:00' if decision == 'EDIT' else 'YES' if decision == 'APPROVE' else 'NO')
            expect(page.locator('.cm-sms-row.outgoing')).to_have_count(0)
            with page.expect_response(lambda r: r.url.endswith('/interpret')) as response:
                page.get_by_role('button', name='Send reply', exact=True).click()
            draft = response.value.json()
            assert draft['status'] == 'READY' and draft['interpretation']['provider'] == 'RULES'
            expect(page.locator('.cm-sms-row.incoming').last).to_contain_text('Reply CONFIRM')
            assert client.get_entity(active['entity_id'])['hours'] == before
            if decision == 'EDIT':
                page.screenshot(path=str(OUT / 'sms-reply-page.png'), full_page=True)
            page.locator('[data-sms-text]').fill('CONFIRM')
            page.locator('[data-sms-text]').press('Enter')
            expected = 'Current hours kept.' if decision == 'REJECT' else 'Hours saved and checked.'
            expect(page.locator('[data-channel-outcome]')).to_contain_text(expected)
            expect(page.locator('.cm-sms-receipt')).to_be_visible()
            expect(page.locator('[data-sms-composer]')).to_have_count(0)
            after = client.get_entity(active['entity_id'])['hours']
            if decision == 'REJECT':
                assert after == before
            else:
                assert read_back_value(after, active['change']) == ('10:00-16:00' if decision == 'EDIT' else active['change']['hours'])
            expect(page.locator('.journey-steps [aria-current=step]')).to_contain_text('Apply & confirm')
            page.locator('.journey-return').click()
            expect(page.locator('.journey-card')).to_contain_text(expected)
            checks.append(f'SMS reply-only {decision}: draft then CONFIRM, text receipt and actual stage5 result without Gemini')
        checks.append('SMS contains no review links, rich text or decision buttons; send/Enter work; phone fits320px')

        # Actual WhatsApp messages still use their chat layout and preview API.
        resume_channel_suggestion("WHATSAPP")
        page.locator('[data-demo-action="contact"]').click()
        expect(page.locator("#demo-owner-link")).to_have_attribute("href", re.compile(r"view=whatsapp"))
        page.locator("#demo-owner-link").click()
        expect(page.locator("#whatsapp-demo .wa-window")).to_be_visible()
        page.reload()
        expect(page.locator("#whatsapp-demo .wa-window")).to_be_visible()
        page.locator("#whatsapp-demo .wa-window").screenshot(path=str(OUT / "whatsapp-phone-desktop.png"))
        assert page.locator("#whatsapp-demo .wa-window").bounding_box()["width"] <= 420
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#whatsapp-demo .wa-window").screenshot(path=str(OUT / f"whatsapp-phone-{width}.png"))
        page.set_viewport_size({"width": 1440, "height": 1050})
        active_pid = page.locator('[data-decision="APPROVE"]').get_attribute("data-id")
        active = page.request.get(BASE + "/api/v1/proposals/" + active_pid).json()
        old_hours = client.get_entity(active["entity_id"])["hours"]
        page.locator('textarea[id^="text-"]').fill("10:00-16:00")
        with page.expect_response(lambda r: r.url.endswith("/interpret")) as response:
            page.locator('textarea[id^="text-"]').press("Enter")
        draft = response.value.json()
        assert draft["status"] == "READY" and draft["interpretation"]["provider"] == "RULES"
        assert client.get_entity(active["entity_id"])["hours"] == old_hours
        expect(page.locator("[data-draft]")).to_be_visible()
        expect(page.locator(".wa-quoted")).to_contain_text("Fonecta Connect")
        page.locator("#whatsapp-demo .wa-window").screenshot(path=str(OUT / "whatsapp-phone-reply.png"))
        page.locator("[data-draft]").click()
        expect(page.locator("[data-wa-outcome]")).to_contain_text("10:00-16:00")
        assert read_back_value(client.get_entity(active["entity_id"])["hours"], active["change"]) == "10:00-16:00"
        page.locator(".journey-return").click()
        expect(page.locator(".journey-card")).to_contain_text("10:00-16:00")
        checks.append("WhatsApp typed hours stay preview-only until confirmation, then advance to actual step5")

        # Quick-reply buttons below the bubble retain their actual decision semantics.
        for decision in ("APPROVE", "REJECT"):
            resume_channel_suggestion("WHATSAPP")
            page.locator('[data-demo-action="contact"]').click()
            page.locator("#demo-owner-link").click()
            expect(page.locator("#whatsapp-demo .wa-window")).to_be_visible()
            current_pid = page.locator('[data-decision="APPROVE"]').get_attribute("data-id")
            current = page.request.get(BASE + "/api/v1/proposals/" + current_pid).json()
            before = client.get_entity(current["entity_id"])["hours"]
            page.locator(f'.wa-choices [data-decision="{decision}"]').click()
            expected = "Hours saved and checked." if decision == "APPROVE" else "Current hours kept."
            expect(page.locator("[data-wa-outcome]")).to_contain_text(expected)
            after = client.get_entity(current["entity_id"])["hours"]
            if decision == "APPROVE":
                assert read_back_value(after, current["change"]) == current["change"]["hours"]
            else:
                assert after == before
            page.locator(".journey-return").click()
            expect(page.locator(".journey-card")).to_contain_text(expected)
            checks.append(f"WhatsApp phone quick reply {decision} matches the database and actual stage5 result")
        # Concurrent changes must not be overwritten or rendered as success.
        resume_channel_suggestion("WHATSAPP")
        page.locator('[data-demo-action="contact"]').click()
        page.locator("#demo-owner-link").click()
        active_pid = page.locator('[data-decision="APPROVE"]').get_attribute("data-id")
        active = page.request.get(BASE + "/api/v1/proposals/" + active_pid).json()
        client.set_holiday_hours(active["entity_id"], active["change"]["date"], "03:00-04:00")
        with page.expect_response(lambda r: r.url.endswith("/decisions")) as response:
            page.locator('[data-decision="APPROVE"]').click()
        assert response.value.status == 409
        expect(page.locator("#toast")).to_be_visible()
        expect(page.locator("[data-wa-outcome]")).to_have_count(0)
        expect(page.locator(".journey-steps [aria-current=step]")).to_contain_text("Decide")
        assert read_back_value(client.get_entity(active["entity_id"])["hours"], active["change"]) == "03:00-04:00"
        assert page.request.get(BASE + "/api/v1/proposals/" + active_pid).json()["decision_status"] == "PENDING"
        checks.append("Concurrent baseline change is blocked; WhatsApp stays at Decide without false success")
        page.locator(".journey-return").click()

        page.locator('[data-tab="overview"]').click()
        expect(page.locator("#fleet-panel")).to_be_visible()
        expect(page.locator("#business")).to_be_visible()
        checks.append("Original workspace controls remain accessible")
        # Inbox links use the actual prepared message's channel too.
        page.locator('[data-tab="inbox"]').click()
        expect(page.locator(".message-card").first).to_be_visible()
        for card in page.locator(".message-card").all():
            channel = card.locator(".badge.mock").inner_text()
            link = card.locator("a.owner-link")
            if link.count() and channel in ("EMAIL", "SMS", "WHATSAPP"):
                assert f"view={channel.lower()}" in link.get_attribute("href")
        checks.append("Inbox routes prepared EMAIL, SMS and WhatsApp messages to their matching views")
        assert not errors, errors
        browser.close()
    result = {
        "checks": checks,
        "browser_errors": errors,
        "llm_enabled": False,
        "scan_businesses": run["processed_businesses"],
        "scope": "isolated mock",
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
