"""Full-dataset browser acceptance; isolated mock state only."""

import json
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8015")
OUT = Path(os.getenv("FLEET_ARTIFACTS", "/tmp/ojr-fleet-browser"))
OUT.mkdir(parents=True, exist_ok=True)
checks = []
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        executable_path=str(
            Path.home() / ".cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
        ),
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 1100})
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/?view=workspace")
    expect(page.locator("#fleet-scope")).to_be_visible(timeout=30000)
    expect(page.locator("#fleet-panel")).to_contain_text("3032", timeout=30000)
    page.locator("#fleet-scope").select_option("EXPLICIT_DATE")
    page.locator("#fleet-date").fill("2026-12-24")
    page.locator("#fleet-start").click()

    def wait_job(phase):
        last_log = 0
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            r = page.request.get(BASE + "/api/v1/operator/fleet-runs").json()["run"]
            if r:
                status = r["status"] if phase == "scan" else r["contact_status"]
                if time.monotonic() - last_log > 15:
                    print(
                        json.dumps(
                            {
                                "phase": phase,
                                "status": status,
                                "processed": r["processed_businesses"],
                                "contacts": r["contact_processed"],
                                "elapsed": r["elapsed_seconds"],
                            }
                        ),
                        flush=True,
                    )
                    last_log = time.monotonic()
                if status != "RUNNING":
                    return r
            page.wait_for_timeout(1000)
        raise AssertionError("Fleet job did not complete within 5 minutes")

    result = wait_job("scan")
    assert result["status"] == "COMPLETED", result
    assert (
        result["processed_businesses"] == 3032 and result["failed_businesses"] == 0
    ), result
    assert result["case_count"] == 3032 and sum(result["counts"].values()) == 3032
    assert all(result["counts"][k] > 0 for k in ("SUGGEST", "FLAG", "NO_ACTION")), (
        result
    )
    assert page.request.get(BASE + "/api/v1/operator/messages").json()["total"] == 0
    checks.append(
        "All3032 businesses scanned with real3-way counts and no automatic contact"
    )
    expect(page.locator('[data-fleet-contact="SCHEDULED"]')).to_be_enabled(
        timeout=30000
    )
    page.locator('[data-fleet-contact="SCHEDULED"]').click()
    scheduled = wait_job("contact")
    assert scheduled["contact_status"] == "COMPLETED"
    assert scheduled["contact_counts"].get("QUEUED", 0) > 0
    checks.append(
        "Batch scheduled contact follows existing cadence/opt-out/pause and leaves owner decisions pending"
    )
    expect(page.locator('[data-fleet-contact="PREVIEW"]')).to_be_enabled(timeout=30000)
    page.locator('[data-fleet-contact="PREVIEW"]').click()
    preview = wait_job("contact")
    assert preview["contact_status"] == "COMPLETED"
    assert preview["contact_counts"].get("DELIVERED_SIMULATED", 0) > 0
    checks.append(
        "Explicit demo preview creates simulated inbox for eligible businesses"
    )
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "fleet-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(OUT / "fleet-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("#language")).to_have_count(0)
    checks.append("Fleet controls remain English at 390px")
    page.set_viewport_size({"width": 1440, "height": 1100})
    page.locator('[data-tab="inbox"]').first.click()
    # The inbox opens the latest contact mode; preview links are immediately visible.
    expect(page.locator("#message-mode")).to_have_value("PREVIEW", timeout=30000)
    expect(page.locator(".owner-link").first).to_be_visible(timeout=30000)
    with page.expect_popup() as pop:
        page.locator(".owner-link").first.click()
    owner = pop.value
    expect(owner.locator('[data-decision="APPROVE"]').first).to_be_visible(
        timeout=30000
    )
    owner.locator('[data-decision="APPROVE"]').first.click()
    expect(owner.locator(".customer-card").first).to_contain_text(
        "Hours saved and checked.", timeout=30000
    )
    checks.append(
        "Fleet suggestion -> batch contact -> owner approval -> mock write/read-back in browser"
    )
    assert not errors, errors
    report = {
        "scan": result,
        "scheduled": scheduled,
        "preview": preview,
        "checks": checks,
        "browser_errors": errors,
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "ready_businesses": result["ready_businesses"],
                "scan_seconds": result["elapsed_seconds"],
                "contact": preview["contact_counts"],
                "checks": checks,
                "browser_errors": errors,
            },
            indent=2,
        ),
        flush=True,
    )
    browser.close()
