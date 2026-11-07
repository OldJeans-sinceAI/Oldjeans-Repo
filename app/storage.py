"""Durable JSON application state (runtime/state.json).

Single writer, temp-file + flush/fsync + atomic os.replace, with a retained previous
snapshot (.bak). Startup validates the file and REPORTS corruption rather than silently
resetting it (AC16). Token hashes and the server secret live here; raw secrets never do.
"""

from __future__ import annotations

import copy
import json
import shutil
import os
import tempfile
import threading
from typing import Any

from . import POLICY, SCHEMA_VERSION


class StateError(RuntimeError):
    """Raised when state cannot be loaded (corruption) or safely persisted."""


_COLLECTIONS = (
    "cases",
    "proposals",
    "messages",
    "decisions",
    "operations",
    "issues",
    "preferences",
    "permissions",
    "jobs",
)
_MAPS = (
    "idempotency",
    "owner_tokens",
    "operator_sessions",
    "owner_sessions",
    "detections",
)


def _empty_state() -> dict:
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY["version"],
        "counters": {},
        "server_secret": None,
    }
    for c in _COLLECTIONS:
        data[c] = {}
    for m in _MAPS:
        data[m] = {}
    return data


class StateStore:
    def __init__(self, path: str):
        self.path = path
        self.bak = path + ".bak"
        self._lock = threading.RLock()
        self.data = self._load()
        self._committed = copy.deepcopy(self.data)

    # ---------------------------------------------------------------- load
    def _load(self) -> dict:
        if not os.path.exists(self.path):
            if os.path.exists(self.bak):
                raise StateError(
                    "Primary state is missing but backup exists; explicit recovery required."
                )
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            data = _empty_state()
            self._atomic_write(data)
            return data
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, OSError) as ex:
            raise StateError(
                f"state file {self.path} is corrupt and was NOT reset: {ex}. "
                f"Inspect it or restore {self.bak}."
            ) from None
        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
            raise StateError(
                f"state file {self.path} has an unexpected schema_version "
                f"{data.get('schema_version') if isinstance(data, dict) else '?'}; not reset."
            )
        for c in _COLLECTIONS:
            data.setdefault(c, {})
            if not isinstance(data[c], dict):
                raise StateError("Invalid state collection: " + c)
        for m in _MAPS:
            data.setdefault(m, {})
            if not isinstance(data[m], dict):
                raise StateError("Invalid state map: " + m)
        data.setdefault("counters", {})
        data.setdefault("server_secret", None)
        return data

    # ---------------------------------------------------------------- write
    def _atomic_write(self, data: dict) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            # Copy a backup without removing the only valid live snapshot.
            if os.path.exists(self.path):
                backup_tmp = self.bak + ".tmp"
                shutil.copyfile(self.path, backup_tmp)
                with open(backup_tmp, "rb") as previous:
                    os.fsync(previous.fileno())
                os.replace(backup_tmp, self.bak)
            os.replace(tmp, self.path)
            os.chmod(self.path, 0o600)
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as ex:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise StateError(f"could not persist state: {ex}") from None

    def save(self) -> None:
        with self._lock:
            self.data["policy_version"] = POLICY["version"]
            try:
                self._atomic_write(self.data)
            except StateError:
                self.data = copy.deepcopy(self._committed)
                raise
            self._committed = copy.deepcopy(self.data)

    # ---------------------------------------------------------------- access
    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def clear_for_reset(self, keep=()):
        """Start a fresh demo, retaining counters so old proposal IDs are never reused."""
        with self._lock:
            fresh = _empty_state()
            for key in ("counters", *keep):
                fresh[key] = copy.deepcopy(self.data[key])
            self.data = fresh
            self.save()

    def next_id(self, kind: str) -> str:
        with self._lock:
            n = self.data["counters"].get(kind, 0) + 1
            self.data["counters"][kind] = n
            return f"{kind}-{n:06d}"

    def collection(self, name: str) -> dict:
        return self.data[name]

    def get(self, name: str, key: str):
        return self.data[name].get(key)

    def put(self, name: str, key: str, value) -> None:
        self.data[name][key] = value
