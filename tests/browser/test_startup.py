"""No old operator shell before route/data readiness, including cold visits."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8030")
OUT = Path(os.getenv("BROWSER_ARTIFACTS", "/tmp/ojr-startup-proof"))
OUT.mkdir(parents=True, exist_ok=True)
expect.set_options(timeout=30000)

TRACE = """() => {
  window.legacyAdded = 0;
  new MutationObserver(records => {
    for (const record of records) for (const node of record.addedNodes) {
      if (node.nodeType === 1 && (node.matches('.sidebar') || node.querySelector('.sidebar'))) {
        window.legacyAdded++;
      }
    }
  }).observe(document, {childList: true, subtree: true});
}"""


def main():
    checks, errors, mutations = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=str(Path.home()/".cache/ms-playwright/chromium-1223/chrome-linux64/chrome"),
        )

        def fresh():
            # Each context has an empty cookie jar, cache and sessionStorage.
            context = browser.new_context(viewport={"width": 1440, "height": 1050})
            page = context.new_page()
            page.add_init_script("(" + TRACE + ")()")
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: mutations.append(r.url) if r.method not in ("GET", "HEAD") else None)
            return context, page

        def ready(page):
            expect(page.locator("[data-presentation-next]")).to_be_enabled()
            expect(page.locator("[data-startup]")).to_have_count(0)
            assert page.evaluate("legacyAdded") == 0
            assert not page.evaluate("state.booting")

        for endpoint in ("health", "operator/cases"):
            context, page = fresh()
            held = []
            page.route("**/api/v1/" + endpoint, lambda route: held.append(route))
            page.goto(BASE + "/", wait_until="domcontentloaded")
            expect(page.locator('[data-startup="loading"]')).to_be_visible()
            # Also exercise render calls made by restored data/polling callbacks.
            page.wait_for_function("() => typeof state !== 'undefined' && state.booting")
            if endpoint != "health":
                page.wait_for_function("() => !!state.health")
            page.evaluate("() => { render(); renderOperator(); renderPresentation(); }")
            expect(page.locator(".sidebar, .pt-shell")).to_have_count(0)
            assert page.evaluate("legacyAdded") == 0
            assert len(held) == 1
            if endpoint == "health":
                page.screenshot(path=str(OUT/"loading-no-old-page.png"), full_page=True)
            held[0].continue_()
            page.unroute("**/api/v1/" + endpoint)
            ready(page)
            page.reload(wait_until="domcontentloaded")
            ready(page)
            checks.append(f"Cold visit and reload: delayed {endpoint} never paints legacy UI")
            context.close()

        for endpoint in ("health", "operator/cases"):
            context, page = fresh()
            page.route("**/api/v1/" + endpoint, lambda route: route.fulfill(
                status=503, content_type="application/json",
                body=json.dumps({"error": {"code": "TEST_UNAVAILABLE", "message": "Injected startup failure"}}),
            ))
            page.goto(BASE + "/", wait_until="domcontentloaded")
            expect(page.locator('[data-startup="error"]')).to_be_visible()
            expect(page.locator(".sidebar, .pt-shell")).to_have_count(0)
            assert page.evaluate("legacyAdded") == 0
            page.evaluate("() => { render(); renderOperator(); renderPresentation(); }")
            expect(page.locator('[data-startup="error"]')).to_be_visible()
            if endpoint == "health":
                page.screenshot(path=str(OUT/"startup-retry.png"), full_page=True)
            page.unroute("**/api/v1/" + endpoint)
            page.locator("#startup-retry").click()
            ready(page)
            checks.append(f"Failed {endpoint} remains on explicit error; Retry opens correct demo")
            context.close()

        context, page = fresh()
        held = []
        page.route("**/api/v1/health", lambda route: held.append(route))
        page.goto(BASE + "/?view=workspace", wait_until="domcontentloaded")
        expect(page.locator('[data-startup="loading"]')).to_be_visible()
        page.wait_for_function("() => typeof state !== 'undefined' && state.booting")
        assert page.evaluate("legacyAdded") == 0
        assert len(held) == 1
        held[0].continue_()
        expect(page.locator('[data-tab="overview"]')).to_have_class("active")
        expect(page.locator(".pt-shell, [data-startup]")).to_have_count(0)
        checks.append("Advanced workspace waits for readiness then opens the requested overview")
        context.close()

        context, page = fresh()
        page.goto(BASE + "/customer", wait_until="domcontentloaded")
        expect(page.locator(".customer-shell")).to_be_visible()
        expect(page.locator("[data-startup]")).to_have_count(0)
        assert not page.evaluate("state.booting")
        checks.append("Direct customer view keeps its existing initialization path")
        context.close()

        assert not errors, errors
        assert not mutations, mutations
        browser.close()
    result = {"checks": checks, "browser_errors": errors, "mutating_requests": mutations}
    (OUT/"result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
