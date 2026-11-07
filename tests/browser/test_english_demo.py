"""English guided flow with real APIs and Gemini disabled; isolated mock only."""

import json
import os
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
        assert messages[0]["channel"] == "WHATSAPP"
        pid = messages[0]["proposal_ids"][0]
        proposal = page.request.get(BASE + "/api/v1/proposals/" + pid).json()
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
        expect(page.locator('[data-decision="APPROVE"]')).to_be_visible()
        expect(page.locator(".journey-steps [aria-current=step]")).to_contain_text(
            "Decide"
        )
        expect(page.locator("html")).to_have_attribute("lang", "en")
        page.screenshot(path=str(OUT / "04-owner.png"), full_page=True)
        checks.append("Same-tab handoff opens the teammate WhatsApp owner at Decide; reload preserves the layout")

        expect(page.locator("#whatsapp-demo .wa-window")).to_be_visible()
        assert "view=whatsapp" in page.url
        page.reload()
        expect(page.locator("#whatsapp-demo .wa-window")).to_be_visible()
        page.locator('textarea[id^="text-"]').fill("Please close at 15:00 instead")
        with page.expect_response(lambda r: r.url.endswith("/interpret")) as response:
            page.get_by_role("button", name="Preview my reply", exact=True).click()
        interpreted = response.value.json()
        assert interpreted["status"] == "NEEDS_CLARIFICATION"
        assert interpreted["interpretation"]["error_code"] == "NOT_CONFIGURED"
        assert "decision_draft" not in interpreted
        expect(page.get_by_role("button", name="Enter hours manually")).to_be_visible()
        assert client.get_entity(proposal["entity_id"])["hours"] == initial_hours
        assert (
            page.request.get(BASE + "/api/v1/proposals/" + pid).json()[
                "decision_status"
            ]
            == "PENDING"
        )
        checks.append(
            "Unavailable model leaves complex reply pending and offers the manual editor"
        )
        page.get_by_role("button", name="Enter hours manually").click()
        page.locator('input[id^="edit-hours-"]').fill("07:30-15:00")
        page.locator("[data-edit-preview]").click()
        expect(page.locator("dialog")).to_contain_text("07:30-15:00")
        assert client.get_entity(proposal["entity_id"])["hours"] == initial_hours
        page.locator("[data-confirm-edit]").click()
        expect(page.locator(".customer-card").first).to_contain_text(
            "Hours saved and checked."
        )
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
            "Confirmed manual edit works without a model and matches independent mock read-back"
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

        for decision in ("APPROVE", "REJECT"):
            page.locator('[data-demo-action="another"]').click()
            expect(page.locator('[data-demo-action="contact"]')).to_be_visible()
            page.locator('[data-demo-action="contact"]').click()
            expect(page.locator("#demo-owner-link")).to_be_visible()
            page.locator("#demo-owner-link").click()
            expect(page.locator('[data-decision="APPROVE"]')).to_be_visible()
            current_pid = page.locator('[data-decision="APPROVE"]').get_attribute(
                "data-id"
            )
            current = page.request.get(BASE + "/api/v1/proposals/" + current_pid).json()
            before = client.get_entity(current["entity_id"])["hours"]
            page.locator(f'[data-decision="{decision}"]').click()
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
            page.locator(".journey-return").click()
            expect(page.locator(".journey-card")).to_contain_text(
                "Hours saved and checked."
                if decision == "APPROVE"
                else "Current hours kept."
            )
            checks.append(f"{decision} completes the guided journey without Gemini")

        # Natural-language shortcuts still use the actual interpreter preview API.
        page.locator('[data-demo-action="another"]').click()
        page.locator('[data-demo-action="contact"]').click()
        page.locator("#demo-owner-link").click()
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
        page.locator("[data-draft]").click()
        expect(page.locator("[data-wa-outcome]")).to_contain_text("10:00-16:00")
        assert read_back_value(client.get_entity(active["entity_id"])["hours"], active["change"]) == "10:00-16:00"
        page.locator(".journey-return").click()
        expect(page.locator(".journey-card")).to_contain_text("10:00-16:00")
        checks.append("WhatsApp typed hours stay preview-only until confirmation, then advance to actual step5")

        # Concurrent changes must not be overwritten or rendered as success.
        page.locator('[data-demo-action="another"]').click()
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
