"""Explicit operator reset: immutable baseline, private backup, verified remote restore.
Reset receipts and recovery journal survive clearing the active demo records.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import tempfile
import threading
import urllib.request
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .domain import merge_change_into_hours
from .errors import AppError, check_idempotency_key, fingerprint
from .storage import StateStore


def stamp():
    return datetime.now(timezone.utc).isoformat()


def normalized_hours(hours):
    result = copy.deepcopy(hours or {})
    if not result.get("holidayHours"):
        result.pop("holidayHours", None)
    elif isinstance(result["holidayHours"], list):
        result["holidayHours"].sort(key=lambda row: row["date"])
    return result


class ResetManager:
    def __init__(self, service, fleet=None, *, baseline=None, mock_reset=None):
        self.s = service
        self.fleet = fleet
        self.journal = StateStore(str(service.state_dir / "reset.json"))
        self.s.reset_blocked = bool(self.journal.data.get("active_reset"))
        self.baseline = baseline or json.loads(
            (service.root / "config/reset-baseline.json").read_text()
        )
        self.mock_reset = mock_reset or self._reset_owned_mock
        # Serializes all HTTP mutations in this workspace, including owner decisions.
        self.mutations = threading.RLock()

    def _initial(self):
        if self.s.mode == "mock":
            p = self.s.root / "data/entities.json"
            if (
                hashlib.sha256(p.read_bytes()).hexdigest()
                != self.baseline["mock_entities_sha256"]
            ):
                raise AppError(
                    409,
                    "BASELINE_CHANGED",
                    "The original dataset changed; reset is blocked.",
                )
            return {
                e["meta"]["id"]: e
                for e in json.loads(p.read_text())["response"]["entities"]
            }
        initial = self.baseline.get("sandbox", {})
        if initial.get("target_entity_id") != self.s.target_id:
            raise AppError(
                409,
                "BASELINE_UNAVAILABLE",
                "No verified original hours for this sandbox target.",
            )
        return normalized_hours(initial["hours"])

    def _remote(self):
        if self.s.mode == "sandbox":
            return normalized_hours(self.s._read(self.s.source_id).get("hours"))
        return {e["meta"]["id"]: e for e in self.s.client.list_entities(limit=100)}

    def _guard(self):
        if self.fleet and self.fleet.active:
            raise AppError(
                409, "RUN_ACTIVE", "Wait for the fleet job to finish before resetting."
            )
        if self.s.mode == "sandbox" and not self.s.allow_writes:
            raise AppError(
                403, "SANDBOX_WRITES_DISABLED", "Sandbox writes are not enabled."
            )

    def _expected(self, initial):
        expected = copy.deepcopy(initial)
        for op in self.s.store.data["operations"].values():
            p = self.s.store.get("proposals", op["proposal_id"]) or {}
            if (
                op["status"] == "SUCCEEDED"
                and p.get("target_entity_id") == self.s.target_id
            ):
                expected = merge_change_into_hours(expected, op["change"])
        return normalized_hours(expected)

    def _check_remote(self, initial, remote):
        active = self.journal.data.get("active_reset")
        expected = (
            active["remote_before"]
            if active
            else self._expected(initial)
            if self.s.mode == "sandbox"
            else remote
        )
        if self.s.mode == "sandbox" and remote != initial and remote != expected:
            raise AppError(
                409,
                "EXTERNAL_CHANGES",
                "Yext hours differ from the baseline and this app’s verified writes. Nothing was reset.",
            )

    def _token(self, initial, remote):
        snapshot = [
            self.s.mode,
            self.s.target_id,
            initial,
            remote,
            self.s.store.data,
            self.fleet.state.data if self.fleet else None,
            self.journal.data.get("generation", 0),
            self.journal.data.get("active_reset"),
        ]
        return hmac.new(
            self.s.internal_secret.encode(),
            fingerprint(snapshot).encode(),
            hashlib.sha256,
        ).hexdigest()

    def preview(self):
        with self.fleet.lock if self.fleet else nullcontext():
            with self.s.lock:
                self._guard()
                initial, remote = self._initial(), self._remote()
                self._check_remote(initial, remote)
                return {
                    "mode": self.s.mode,
                    "target_entity_id": self.s.target_id
                    if self.s.mode == "sandbox"
                    else None,
                    "baseline": "RECEIVED_MOCK_DATASET"
                    if self.s.mode == "mock"
                    else "VERIFIED_BEFORE_FIRST_APPLY",
                    "baseline_hours": initial if self.s.mode == "sandbox" else None,
                    "business_count": len(initial) if self.s.mode == "mock" else 1,
                    "counts": {
                        k: len(self.s.store.data[k])
                        for k in (
                            "cases",
                            "proposals",
                            "messages",
                            "decisions",
                            "operations",
                            "preferences",
                        )
                    },
                    "remote_changed": remote != initial,
                    "recovery_required": bool(self.journal.data.get("active_reset")),
                    "preview_token": self._token(initial, remote),
                }

    def _archive(self, remote):
        parent = self.s.state_dir / "reset-backups"
        parent.mkdir(mode=0o700, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="reset-", dir=parent))
        snapshots = {"app-state.json": self.s.store.data, "remote.json": remote}
        if self.fleet:
            snapshots["fleet.json"] = self.fleet.state.data
        mockfile = self.s.state_dir / "mock-state.json"
        if self.s.mode == "mock" and mockfile.exists():
            snapshots["mock-state.json"] = json.loads(mockfile.read_text())
        hashes = {}
        for name, value in snapshots.items():
            raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
            fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            hashes[name] = hashlib.sha256(raw).hexdigest()
        manifest = {
            "created_at": stamp(),
            "mode": self.s.mode,
            "target_entity_id": self.s.target_id,
            "files": hashes,
            "auth": "Old owner tokens are revoked, never restored.",
        }
        fd = os.open(
            folder / "manifest.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(fd, "w") as f:
            json.dump(manifest, f)
            f.flush()
            os.fsync(f.fileno())
        fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return folder.name

    def _reset_owned_mock(self):
        base = self.s.client.base
        u = urlparse(base)
        if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost"):
            raise AppError(
                409,
                "MOCK_HOST_REQUIRED",
                "Reset is restricted to the owned local mock.",
            )
        req = urllib.request.Request(
            base.rstrip("/") + "/mock/reset",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.load(r)
            if (
                result.get("meta", {}).get("errors")
                or result.get("response", {}).get("reset") is not True
            ):
                raise AppError(
                    502, "RESET_NOT_VERIFIED", "The mock did not confirm reset."
                )

    def execute(self, body, key):
        check_idempotency_key(key)
        if body.get("confirm_reset") is not True:
            raise AppError(
                422, "RESET_CONFIRMATION_REQUIRED", "Confirm the displayed reset scope."
            )
        with self.mutations:
            with self.fleet.lock if self.fleet else nullcontext():
                with self.s.lock:
                    old = self.journal.data["idempotency"].get(key)
                    if old:
                        if old["hash"] != fingerprint(body):
                            raise AppError(
                                409,
                                "IDEMPOTENCY_CONFLICT",
                                "This key belongs to a different reset.",
                            )
                        return copy.deepcopy(old["result"])
                    self._guard()
                    initial, remote = self._initial(), self._remote()
                    self._check_remote(initial, remote)
                    if not hmac.compare_digest(
                        body.get("preview_token", ""), self._token(initial, remote)
                    ):
                        raise AppError(
                            409,
                            "RESET_PREVIEW_STALE",
                            "Data changed after the reset preview. Review it again.",
                        )
                    active = self.journal.data.get("active_reset")
                    if not active:
                        backup = self._archive(
                            remote
                        )  # Must succeed before any remote write.
                        active = {
                            "backup_id": backup,
                            "mode": self.s.mode,
                            "target_entity_id": self.s.target_id,
                            "remote_before": remote,
                            "baseline_hash": fingerprint(initial),
                            "phase": "PREPARED",
                            "started_at": stamp(),
                        }
                        self.journal.data["active_reset"] = active
                        self.journal.save()
                    if active["target_entity_id"] != self.s.target_id or active[
                        "baseline_hash"
                    ] != fingerprint(initial):
                        raise AppError(
                            409,
                            "RESET_TARGET_CHANGED",
                            "Recovery target or baseline changed.",
                        )
                    self.s.reset_blocked = True
                    try:
                        if self._remote() != remote:
                            raise AppError(
                                409,
                                "RESET_PREVIEW_STALE",
                                "Remote data changed while saving the backup.",
                            )
                        # A timeout is uncertain. Always check remote state; never blindly retry a PUT.
                        if remote != initial:
                            try:
                                if self.s.mode == "sandbox":
                                    self.s.client._req(
                                        "PUT",
                                        "entities/" + self.s.target_id,
                                        body={
                                            "hours": copy.deepcopy(initial)
                                            if initial
                                            else None
                                        },
                                    )
                                else:
                                    self.mock_reset()
                            except Exception:
                                pass
                        elif self.s.mode == "mock":
                            # Clear mock update_log even if current values already match the original.
                            self.mock_reset()
                        if self._remote() != initial:
                            raise AppError(
                                502,
                                "RESET_NOT_VERIFIED",
                                "Remote restore was not verified. Existing progress is retained; retry the reset.",
                            )
                        active["phase"] = "REMOTE_VERIFIED"
                        self.journal.save()
                        # Revoke old owner links before clearing active records. Keep operator sessions.
                        self.s.auth.clear_for_reset(keep=("operator_sessions",))
                        if self.fleet:
                            self.fleet.state.clear_for_reset()
                        self.s.store.clear_for_reset()
                        self.s._import_mock_permissions()
                        self.s.sandbox_write = (
                            "UNTESTED" if self.s.mode == "sandbox" else "NOT_APPLICABLE"
                        )
                        result = {
                            "reset_id": active["backup_id"],
                            "mode": self.s.mode,
                            "target_entity_id": self.s.target_id
                            if self.s.mode == "sandbox"
                            else None,
                            "status": "COMPLETED",
                            "remote_verified": True,
                            "completed_at": stamp(),
                            "backup_id": active["backup_id"],
                        }
                        self.journal.data["generation"] = (
                            self.journal.data.get("generation", 0) + 1
                        )
                        self.journal.data["idempotency"][key] = {
                            "hash": fingerprint(body),
                            "result": result,
                        }
                        self.journal.data["active_reset"] = None
                        self.journal.save()
                        self.s.reset_blocked = False
                        return result
                    except Exception as ex:
                        active = self.journal.data.get("active_reset") or active
                        active["phase"] = "RECOVERY_REQUIRED"
                        active["error_code"] = getattr(
                            ex, "code", "RESET_RECOVERY_REQUIRED"
                        )
                        self.journal.data["active_reset"] = active
                        self.journal.save()
                        raise AppError(
                            503,
                            "RESET_RECOVERY_REQUIRED",
                            "Reset needs recovery. Progress is backed up; reopen Reset to retry.",
                        ) from None
