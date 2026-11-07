"""Destructive reset acceptance: opt in against an isolated mock server only."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from examples.yext_client import YextClient


def main():
    if os.getenv("RUN_RESET_BROWSER_TEST") != "1":
        raise SystemExit("Set RUN_RESET_BROWSER_TEST=1 for an isolated mock workspace.")
    base = os.environ["TEST_BASE_URL"]
    client = YextClient(base_url=os.environ["TEST_MOCK_BASE"])
    out = Path(os.environ["BROWSER_ARTIFACTS"])
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    original = {
        e["meta"]["id"]: e
        for e in json.loads((root / "data/entities.json").read_text())["response"][
            "entities"
        ]
    }
    errors, checks = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=str(
                Path.home() / ".cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
            ),
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.set_default_timeout(60000)
        page.on("pageerror", lambda e: errors.append(str(e)))
        reset_responses = []

        def capture_reset(route):
            if route.request.method == "POST":
                response = route.fetch()
                reset_responses.append(response.json())
                route.fulfill(response=response)
            else:
                route.continue_()

        # Capture before fulfilling: the app immediately navigates on success.
        page.route("**/api/v1/operator/reset", capture_reset)
        page.goto(base + "/?view=workspace")
        expect(page.locator("#reset-open")).to_be_visible(timeout=60000)
        assert page.request.get(base + "/api/v1/health").json()["mode"] == "mock"

        # Reproduce the user's failure: there are proposals, but no applied hours.
        page.locator('[data-example="FI-D0001"]').click()
        expect(page.locator("[data-case]").first).to_be_visible(timeout=60000)
        for attempt in range(2):
            page.locator("#reset-open").click()
            expect(page.locator("#reset-confirm")).to_be_visible(timeout=60000)
            with page.expect_navigation(wait_until="domcontentloaded"):
                with page.expect_response(
                    lambda r: r.request.method == "POST"
                    and r.url.endswith("/operator/reset"),
                    timeout=90000,
                ) as response:
                    page.locator("#reset-confirm").click()
            assert response.value.status == 200
            assert reset_responses[-1]["status"] == "COMPLETED"
            expect(page.locator("#reset-open")).to_be_visible(timeout=60000)
            assert (
                page.request.get(base + "/api/v1/operator/cases").json()["items"] == []
            )
        checks.append("Original-data reset and immediate repeated reset both complete")

        def approve():
            page.locator('[data-tab="overview"]').click()
            page.locator('[data-example="FI-D0001"]').click()
            expect(page.locator("[data-case]").first).to_be_visible(timeout=60000)
            page.locator("[data-case]").first.click()
            page.locator('[data-mode="PREVIEW"]').click()
            expect(page.locator(".owner-link").first).to_be_visible(timeout=60000)
            with page.expect_popup() as pop:
                page.locator(".owner-link").first.click()
            owner = pop.value
            owner.on("pageerror", lambda e: errors.append(str(e)))
            expect(owner.locator('[data-decision="APPROVE"]').first).to_be_visible(
                timeout=60000
            )
            with owner.expect_response(
                lambda r: r.request.method == "POST" and "/decisions" in r.url,
                timeout=60000,
            ) as resp:
                owner.locator('[data-decision="APPROVE"]').first.click()
            result = resp.value.json()
            assert result["application_status"] == "SUCCEEDED", result
            return owner

        owner = approve()
        assert client.get_entity("FI-D0001")["hours"] != original["FI-D0001"]["hours"]
        checks.append("Owner-approved mock change independently read back")
        # Return from Inbox to the operator view. Cancel must preserve the change.
        page.locator("#reset-open").click()
        expect(page.locator("#reset-confirm")).to_be_visible(timeout=60000)
        page.locator("dialog [data-close]").last.click()
        assert client.get_entity("FI-D0001")["hours"] != original["FI-D0001"]["hours"]
        checks.append("Cancel leaves applied values intact")
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#reset-open").click()
        expect(page.locator("#reset-confirm")).to_be_visible(timeout=60000)
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#language")).to_have_count(0)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(out / "reset-en.png"), full_page=True)
        page.locator("dialog [data-close]").last.click()
        checks.append("English reset confirmation at 390px without horizontal overflow")
        page.locator("#reset-open").click()
        expect(page.locator("#reset-confirm")).to_be_visible(timeout=60000)
        with page.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith("/operator/reset"),
            timeout=90000,
        ) as resp:
            page.locator("#reset-confirm").click()
        assert resp.value.status == 200
        receipt = reset_responses[-1]
        assert receipt["status"] == "COMPLETED" and receipt["remote_verified"], receipt
        expect(page.locator("#reset-open")).to_be_visible(timeout=60000)
        # Navigation after reset must finish before requesting the cleared case list.
        expect(page.locator("dialog[open]")).to_have_count(0)
        assert page.request.get(base + "/api/v1/operator/cases").json()["items"] == []
        after = {e["meta"]["id"]: e for e in client.list_entities(limit=100)}
        assert after == original
        checks.append(
            f"Reset restored all {len(after)} original entities and cleared active cases"
        )
        assert (
            owner.request.get(
                base + "/api/v1/businesses/FI-D0001/contact-preferences"
            ).status
            == 401
        )
        checks.append("Previously authenticated owner session revoked")
        owner.close()
        page.set_viewport_size({"width": 1440, "height": 1000})
        second = approve()
        checks.append(
            "Same company/date can be proposed and approved again after reset"
        )
        second.close()
        assert not errors, errors
        browser.close()
    result = {
        "checks": checks,
        "page_errors": errors,
        "restored_entities": len(original),
        "reset_status": receipt["status"],
    }
    (out / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
