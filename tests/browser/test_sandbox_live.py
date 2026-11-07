"""Explicitly opt-in live team sandbox acceptance. Never discovered by unit tests.
Leaves the approved date in the team entity and in the visible application history.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, expect
from examples.yext_client import YextClient
from app.domain import read_back_value, change_target_value

if os.getenv("RUN_LIVE_YEXT_TEST") != "1":
    raise SystemExit(
        "Requires RUN_LIVE_YEXT_TEST=1 and user authorization for the team sandbox."
    )
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
OUT = Path(os.getenv("SANDBOX_ARTIFACTS", "/tmp/ojr-live-yext-proof"))
OUT.mkdir(parents=True, exist_ok=True)
eid = os.environ["YEXT_ENTITY_ID"]
client = YextClient(
    base_url="https://sbx-api.yextapis.com",
    api_key=os.environ["YEXT_API_KEY"],
    v=os.getenv("YEXT_API_VERSION", "20261106"),
)
before = client.get_entity(eid)
proof = {
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "target_entity_id": eid,
    "target_name": before.get("name"),
    "before_hours": before.get("hours") or {},
    "contact": "SIMULATED",
    "approval": "NOT_YET",
    "live_put_verified": False,
}
(OUT / "result.json").write_text(json.dumps(proof, indent=2))
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        executable_path=str(
            Path.home() / ".cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
        ),
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/sandbox/")
    expect(page.locator("#sandbox-panel")).to_contain_text(eid, timeout=30000)
    page.locator("#sandbox-demo").click()
    expect(page.locator(".message-card").first).to_be_visible(timeout=60000)
    message = page.request.get(
        BASE + "/sandbox/api/v1/operator/messages?delivery_mode=PREVIEW"
    ).json()["items"][0]
    proof["message"] = {
        k: message[k]
        for k in ["channel", "language", "sender", "text", "status", "simulated"]
    }
    page.screenshot(path=str(OUT / "contact.png"), full_page=True)
    with page.expect_popup() as pop:
        page.locator(".owner-link").first.click()
    owner = pop.value
    owner.on("pageerror", lambda e: errors.append(str(e)))
    expect(owner.locator(".customer-card").first).to_contain_text(eid, timeout=30000)
    owner.screenshot(path=str(OUT / "owner-before.png"), full_page=True)
    proof["approval"] = "EXPLICIT_OWNER_APPROVE_BUTTON"
    with owner.expect_response(
        lambda r: "/decisions" in r.url and r.request.method == "POST", timeout=90000
    ) as response:
        owner.locator('[data-decision="APPROVE"]').first.click()
    result = response.value.json()
    proof["application_result"] = result
    (OUT / "result.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False))
    assert result.get("application_status") == "SUCCEEDED", result
    expect(owner.locator("[data-sandbox-verified]")).to_contain_text(eid, timeout=30000)
    after = client.get_entity(eid)
    proof["after_hours"] = after.get("hours") or {}
    change = result["final_change"]
    assert result["mode"] == "sandbox" and result["target_entity_id"] == eid
    assert read_back_value(proof["after_hours"], change) == change_target_value(change)
    changed = [
        k
        for k in set(before) | set(after)
        if k not in ("hours", "meta") and before.get(k) != after.get(k)
    ]
    assert not changed, changed
    prior_other = dict(proof["before_hours"])
    final_other = dict(proof["after_hours"])
    day = change["date"]
    for h in (prior_other, final_other):
        h["holidayHours"] = [
            r for r in h.get("holidayHours", []) if r.get("date") != day
        ]
    assert prior_other == final_other, "Unrelated hours changed"
    proof.update(
        live_put_verified=True,
        unrelated_fields_changed=changed,
        unrelated_hours_preserved=True,
        browser_errors=errors,
    )
    owner.screenshot(path=str(OUT / "owner-after.png"), full_page=True)
    page.goto(BASE + "/sandbox/")
    expect(page.locator("#sandbox-panel")).to_contain_text(
        "Write verified", timeout=30000
    )
    page.screenshot(path=str(OUT / "sandbox-after.png"), full_page=True)
    assert not errors, errors
    (OUT / "result.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False))
    print(
        json.dumps(
            {
                "target": eid,
                "result": result["application_status"],
                "change": change,
                "independent_readback": True,
                "other_fields_preserved": True,
                "artifacts": str(OUT),
            },
            indent=2,
        ),
        flush=True,
    )
    browser.close()
