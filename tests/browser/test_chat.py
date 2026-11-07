import json, os, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8013")
LIVE = os.getenv("LIVE_GEMINI") == "1"
checks = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        executable_path=str(
            Path.home() / ".cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
        ),
    )
    ctx = browser.new_context(viewport={"width": 1280, "height": 1000})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/?view=workspace")
    expect(page.locator("#business option").nth(1)).to_be_attached(timeout=60000)
    page.locator('[data-example="FI-D0001"]').click()
    expect(page.locator("[data-case]").first).to_be_visible(timeout=30000)
    page.locator("[data-case]").first.click()
    page.locator('[data-mode="PREVIEW"]').click()
    with page.expect_popup() as pop:
        page.locator(".owner-link").last.click()
    owner = pop.value
    owner.on("pageerror", lambda e: errors.append(str(e)))
    expect(owner.locator('[data-decision="APPROVE"]')).to_be_visible(timeout=30000)
    owner.locator("details.reply-panel summary").click()
    reply = owner.locator('textarea[id^="text-"]')
    button = owner.locator("[data-interpret]")
    if not LIVE:

        def unavailable(route):
            time.sleep(0.5)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "status": "UNAVAILABLE",
                        "intent": "UNKNOWN",
                        "preview": "Temporary provider failure",
                        "missing_fields": [],
                        "interpretation": {
                            "provider": "GEMINI",
                            "latency_ms": 8000,
                            "error_code": "TIMEOUT",
                        },
                    }
                ),
            )

        owner.route("**/interpret", unavailable)
        reply.fill("Please close at 15:00 instead")
        button.click()
        expect(owner.locator('[data-reply-status="UNAVAILABLE"]')).to_be_visible(
            timeout=15000
        )
        expect(owner.locator('[data-decision="APPROVE"]')).to_be_visible()
        expect(reply).to_have_value("Please close at 15:00 instead")
        expect(owner.locator("[data-draft]")).to_have_count(0)
        checks.append(
            "Provider failure preserves pending proposal and reply; no confirm draft"
        )
        expect(owner.locator("html")).to_have_attribute("lang", "en")
        expect(owner.locator("#language")).to_have_count(0)
        expect(reply).to_have_value("Please close at 15:00 instead")
        checks.append("English-only failure message preserves input")
        owner.unroute("**/interpret", unavailable)

        def valid(route):
            # Read immutable version from owner API; response intercept tests only UI, not provider.
            url = route.request.url.rsplit("/interpret", 1)[0]
            p = owner.request.get(url).json()
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "status": "READY",
                        "intent": "EDIT",
                        "preview": "Set hours",
                        "missing_fields": [],
                        "decision_draft": {
                            "proposal_version": p["version"],
                            "decision": "EDIT",
                            "edited_change": {**p["change"], "hours": "07:30-15:00"},
                            "confirmed": True,
                        },
                        "interpretation": {
                            "provider": "GEMINI",
                            "latency_ms": 900,
                            "error_code": None,
                        },
                    }
                ),
            )

        owner.route("**/interpret", valid)
    reply.fill("Please close at 15:00 instead")
    start = time.monotonic()
    button.click()
    expect(owner.locator('[data-reply-status="READY"]')).to_be_visible(timeout=15000)
    expect(owner.locator("[data-reply-status]")).to_contain_text("07:30-15:00")
    expect(owner.locator('[data-decision="APPROVE"]')).to_be_visible()
    checks.append(
        "Natural-language edit previews exact hours; pending until confirmation"
    )
    if LIVE:
        checks.append(
            "Live Gemini UI interpretation in "
            + str(round(time.monotonic() - start, 2))
            + " seconds"
        )
    # Changing text must invalidate the older prepared action.
    reply.fill("Wait, I need to check")
    expect(owner.locator("[data-draft]")).to_have_count(0)
    checks.append("Typing after preview invalidates old confirm action")
    if not LIVE:
        reply.fill("Please close at 15:00 instead")
        button.click()
        expect(owner.locator("[data-draft]")).to_be_visible()
    else:
        # Exact offline range avoids another provider call while testing confirmation.
        reply.fill("07:30-15:00")
        button.click()
        expect(owner.locator("[data-draft]")).to_be_visible()
    owner.locator("[data-draft]").click()
    expect(owner.locator(".customer-card").first).to_contain_text(
        "Hours saved and checked.", timeout=30000
    )
    expect(owner.locator(".customer-card").first).to_contain_text("07:30-15:00")
    checks.append(
        "Explicit confirmation applies edited hours and verifies mock read-back"
    )
    owner.set_viewport_size({"width": 390, "height": 844})
    owner.screenshot(
        path="/tmp/ojr-chat-live.png" if LIVE else "/tmp/ojr-chat-ui.png",
        full_page=True,
    )
    assert owner.evaluate("document.documentElement.scrollWidth<=innerWidth")
    assert owner.locator(".publisher-list").bounding_box()["width"] > 280
    checks.append("Mobile result and reply remain outside the three-column schedule")
    assert not errors, errors
    print(
        json.dumps(
            {
                "mode": "live-provider" if LIVE else "UI-with-fault-injection",
                "checks": checks,
                "browser_errors": errors,
            },
            indent=2,
        )
    )
    browser.close()
