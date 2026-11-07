"""Real browser acceptance. Run against a fresh isolated mock-mode server."""

import json, os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
ART = Path(os.getenv("BROWSER_ARTIFACTS", "tests/browser/artifacts"))
ART.mkdir(parents=True, exist_ok=True)


def main():
    errors = []
    checks = []
    with sync_playwright() as p:
        cached = (
            Path.home() / ".cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
        )
        args = {"headless": True}
        if cached.exists():
            args["executable_path"] = str(cached)
        browser = p.chromium.launch(**args)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/?view=workspace")
        expect(page.locator("#business")).to_be_visible()
        expect(page.locator("#business option").nth(1)).to_be_attached(timeout=60000)
        page.locator('[data-example="FI-D0001"]').click()
        expect(page.locator("[data-case]").first).to_be_visible(timeout=30000)
        page.locator("[data-case]").first.click()
        expect(page.locator("dialog")).to_be_visible()
        expect(page.locator("dialog")).to_contain_text("07:30-13:00")
        checks.append("History-backed proposal visible")
        page.locator('[data-mode="PREVIEW"]').click()
        expect(page.locator(".owner-link").first).to_be_visible(timeout=30000)
        with page.expect_popup() as popup:
            page.locator(".owner-link").first.click()
        owner = popup.value
        owner.on("pageerror", lambda e: errors.append(str(e)))
        expect(owner.locator('[data-decision="APPROVE"]')).to_be_visible(timeout=30000)
        expect(owner.locator("html")).to_have_attribute("lang", "en")
        expect(owner.locator("#language")).to_have_count(0)
        checks.append("English-only customer controls")
        owner.locator("details").filter(has=owner.locator("[data-interpret]")).locator(
            "summary"
        ).click()
        owner.locator('textarea[id^="text-"]').fill("maybe five")
        owner.locator("[data-interpret]").click()
        expect(owner.locator(".notice.warn")).to_be_visible()
        expect(owner.locator('[data-decision="APPROVE"]')).to_be_visible()
        checks.append("Ambiguous language previews without applying")
        owner.locator("[data-edit]").click()
        owner.locator('input[id^="edit-hours-"]').fill("07:30-15:00")
        owner.locator("[data-edit-preview]").click()
        expect(owner.locator("dialog")).to_contain_text("07:30-15:00")
        owner.locator("[data-confirm-edit]").click()
        expect(owner.locator(".result-icon")).to_be_visible(timeout=30000)
        expect(owner.locator(".customer-card").first).to_contain_text(
            "Hours saved and checked."
        )
        expect(owner.locator(".customer-card").first).to_contain_text("07:30-15:00")
        checks.append("Owner edit saved to mock and read back")
        owner.set_viewport_size({"width": 390, "height": 844})
        owner.screenshot(path=str(ART / "owner-mobile.png"), full_page=True)
        assert owner.evaluate("document.documentElement.scrollWidth<=innerWidth"), (
            "Customer horizontal overflow"
        )
        checks.append("390px owner layout")
        owner.locator("#frequency").select_option("PAUSED")
        owner.locator("#save-frequency").click()
        expect(owner.locator("#toast")).to_contain_text("Saved")
        owner.reload()
        expect(owner.locator("#frequency")).to_have_value("PAUSED", timeout=30000)
        checks.append("Contact pause survives refresh")
        page.locator('[data-tab="overview"]').click()
        # Exercise the two other owner decisions through the actual browser.
        for day, decision, expected in [
            ("2026-12-24", "APPROVE", "Hours saved and checked."),
            ("2026-12-31", "REJECT", "Current hours kept."),
        ]:
            page.locator("#business").select_option("FI-D0004")
            page.locator("#target-date").fill(day)
            page.locator("#run").click()
            expect(page.locator("#run")).to_be_enabled(timeout=30000)
            row = page.locator("tbody tr").filter(has_text="FI-D0004").last
            row.locator("[data-case]").click()
            page.locator('[data-mode="PREVIEW"]').click()
            expect(page.locator(".owner-link").last).to_be_visible(timeout=30000)
            with page.expect_popup() as popup2:
                page.locator(".owner-link").last.click()
            other = popup2.value
            expect(other.locator('[data-decision="' + decision + '"]')).to_be_visible(
                timeout=30000
            )
            other.locator('[data-decision="' + decision + '"]').click()
            expect(other.locator(".customer-card").first).to_contain_text(
                expected, timeout=30000
            )
            other.close()
            page.locator('[data-tab="overview"]').click()
        checks.append("Browser approve and reject journeys")
        for eid in ("FI-D0011", "FI-D0013", "FI-D0017"):
            page.locator(f'[data-example="{eid}"]').click()
            page.wait_for_timeout(1200)
        expect(page.locator("tbody")).to_contain_text("Staff review")
        expect(page.locator("tbody")).to_contain_text("Defer")
        checks.append("FLAG / RETAIN / DEFER visible")
        page.screenshot(path=str(ART / "operator-desktop.png"), full_page=True)
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#language")).to_have_count(0)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(ART / "operator-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (
            "Operator horizontal overflow"
        )
        checks.append("390px operator layout")
        with page.expect_download(timeout=180000) as download_info:
            page.locator("#export").click()
        download = download_info.value
        download.save_as(str(ART / "predictions.csv"))
        import csv

        with (ART / "predictions.csv").open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 41755
        assert set(row["action"] for row in rows) <= {"SUGGEST", "FLAG", "NO_ACTION"}
        checks.append("Browser CSV download: all 41,755 targets")
        assert not errors, errors
        browser.close()
    (ART / "browser-results.json").write_text(
        json.dumps({"checks": checks, "page_errors": errors}, indent=2)
    )
    print(json.dumps({"passed": checks, "page_errors": errors}, indent=2))


if __name__ == "__main__":
    main()
