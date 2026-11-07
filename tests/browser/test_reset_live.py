"""Opt-in, private isolated-state reset/reapply roundtrip for the team sandbox."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
from datetime import datetime, timezone

from dotenv import load_dotenv
from app.reset import ResetManager, normalized_hours
from app.service import Service
from app.domain import merge_change_into_hours
from examples.yext_client import YextClient

assert os.environ.get("RUN_RESET_LIVE_TEST") == "1"
with socket.socket() as sock:
    assert sock.connect_ex(("127.0.0.1", 8000)) != 0, (
        "Stop the original server/scheduler before live verification."
    )
root = Path(__file__).resolve().parents[2]
load_dotenv(root / ".env", override=False)
os.environ["GEMINI_ENABLED"] = "false"
target = os.environ["YEXT_ENTITY_ID"]
assert target == "SinceAI18"
client = YextClient(
    base_url="https://sbx-api.yextapis.com",
    api_key=os.environ["YEXT_API_KEY"],
    v="20261106",
)
folder = Path(tempfile.mkdtemp(prefix="ojr-reset-live-"))
os.chmod(folder, 0o700)


def save(name, value):
    fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unchanged_fields(a, b):
    return all(a.get(k) == b.get(k) for k in (set(a) | set(b)) - {"hours", "meta"})


tracked = [root / "runtime/state.json", root / "runtime/sandbox/state.json"]
prior_hashes = [digest(p) for p in tracked]
before = client.get_entity(target)
before_hours = normalized_hours(before.get("hours"))
assert before_hours == {
    "holidayHours": [
        {"date": "2026-12-24", "openIntervals": [{"start": "07:30", "end": "13:00"}]}
    ]
}, "Unexpected live baseline; no mutation attempted."
save("before.json", before)
print("Pre-reset private GET backup: " + str(folder / "before.json"), flush=True)
state = folder / "isolated-state"
state.mkdir(mode=0o700)
shutil.copyfile(root / "runtime/sandbox/state.json", state / "state.json")
os.chmod(state / "state.json", 0o600)
s = Service(
    root,
    state,
    mode="sandbox",
    source_id="FI-D0001",
    target_id=target,
    allow_writes=True,
    client=client,
)
r = ResetManager(s)
preview = r.preview()
assert preview["baseline_hours"] == {} and preview["remote_changed"]
report = {
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "target_entity_id": target,
    "before_hours": before_hours,
    "isolated_application_state": True,
    "reset_verified": False,
    "reapply_verified": False,
}
save("result.json", report)
try:
    receipt = r.execute(
        {"confirm_reset": True, "preview_token": preview["preview_token"]},
        "live-reset-roundtrip-1",
    )
    cleared = client.get_entity(target)
    assert normalized_hours(cleared.get("hours")) == {}
    assert unchanged_fields(before, cleared)
    report.update(
        reset_verified=True,
        reset_receipt=receipt,
        reset_hours=normalized_hours(cleared.get("hours")),
    )
    save("cleared.json", cleared)
    save("result.json", report)
    s.cycle(
        {
            "scope": "EXPLICIT_DATES",
            "entity_ids": ["FI-D0001"],
            "dates": ["2026-12-24"],
        },
        apply_permissions=False,
    )
    proposal = next(iter(s.store.data["proposals"].values()))
    assert (
        normalized_hours(merge_change_into_hours({}, proposal["change"]))
        == before_hours
    )
    result = s.decide(
        proposal["proposal_id"],
        {"decision": "APPROVE", "proposal_version": proposal["version"]},
        "live-reapply-after-reset",
    )
    assert result["application_status"] == "SUCCEEDED", result["application_status"]
    final = client.get_entity(target)
    assert normalized_hours(final.get("hours")) == before_hours
    assert unchanged_fields(before, final)
    report.update(
        reapply_verified=True,
        final_hours=normalized_hours(final.get("hours")),
        unrelated_fields_preserved=True,
    )
    save("after.json", final)
finally:
    # Preserve the existing visible demo even if an assertion above failed.
    current = client.get_entity(target)
    current_hours = normalized_hours(current.get("hours"))
    if current_hours != before_hours:
        if current_hours != {}:
            raise RuntimeError(
                "Concurrent external hours detected; guarded restore aborted. Inspect private backup at "
                + str(folder)
            )
        client._req(
            "PUT", "entities/" + target, body={"hours": copy.deepcopy(before_hours)}
        )
        current = client.get_entity(target)
        assert normalized_hours(current.get("hours")) == before_hours, (
            "Recovery restore was not verified"
        )
        report["backup_recovery_used"] = True
    report["existing_demo_remote_preserved"] = (
        normalized_hours(current.get("hours")) == before_hours
    )
    report["existing_app_state_unchanged"] = [
        digest(p) for p in tracked
    ] == prior_hashes
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    save("result.json", report)
print(json.dumps({"result": report, "private_artifacts": str(folder)}, indent=2))
