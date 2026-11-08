"""Durable JSON application state (runtime/state.json).

Single writer, temp-file + flush/fsync + atomic os.replace, with a retained previous
snapshot (.bak). Startup validates the file and REPORTS corruption rather than silently
resetting it (AC16). Token hashes and the server secret live here; raw secrets never do.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
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
	state: dict[str, Any] = {
		"schema_version": SCHEMA_VERSION,
		"policy_version": POLICY["version"],
		"counters": {},
		"server_secret": None,
	}
	for collection_name in _COLLECTIONS:
		state[collection_name] = {}
	for map_name in _MAPS:
		state[map_name] = {}
	return state


class StateStore:
	def __init__(self, path: str):
		self.path = path
		self.bak = path + ".bak"
		self._lock = threading.RLock()
		self.data = self._load()
		self._committed = copy.deepcopy(self.data)

	def _load(self) -> dict:
		if not os.path.exists(self.path):
			if os.path.exists(self.bak):
				raise StateError(
					"Primary state is missing but backup exists; explicit recovery required."
				)
			os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
			state_data = _empty_state()
			self._atomic_write(state_data)
			return state_data
		try:
			with open(self.path, encoding="utf-8") as file:
				state_data = json.load(file)
		except (ValueError, OSError) as exc:
			raise StateError(
				f"state file {self.path} is corrupt and was NOT reset: {exc}. Inspect it or restore {self.bak}."
			) from None
		if not isinstance(state_data, dict) or state_data.get("schema_version") != SCHEMA_VERSION:
			raise StateError(
				f"state file {self.path} has an unexpected schema_version {state_data.get('schema_version') if isinstance(state_data, dict) else '?'}; not reset."
			)
		for collection_name in _COLLECTIONS:
			state_data.setdefault(collection_name, {})
			if not isinstance(state_data[collection_name], dict):
				raise StateError("Invalid state collection: " + collection_name)
		for map_name in _MAPS:
			state_data.setdefault(map_name, {})
			if not isinstance(state_data[map_name], dict):
				raise StateError("Invalid state map: " + map_name)
		state_data.setdefault("counters", {})
		state_data.setdefault("server_secret", None)
		return state_data

	def _atomic_write(self, state_data: dict) -> None:
		state_dir = os.path.dirname(os.path.abspath(self.path))
		os.makedirs(state_dir, exist_ok=True)
		fd, temp_path = tempfile.mkstemp(dir=state_dir, prefix=".state-", suffix=".tmp")
		try:
			with os.fdopen(fd, "w", encoding="utf-8") as file:
				json.dump(state_data, file, ensure_ascii=False, separators=(",", ":"))
				file.flush()
				os.fsync(file.fileno())
			# Copy a backup without removing the only valid live snapshot.
			if os.path.exists(self.path):
				backup_temp = self.bak + ".tmp"
				shutil.copyfile(self.path, backup_temp)
				with open(backup_temp, "rb") as prev_file:
					os.fsync(prev_file.fileno())
				os.replace(backup_temp, self.bak)
			os.replace(temp_path, self.path)
			os.chmod(self.path, 0o600)
			dir_fd = os.open(state_dir, os.O_RDONLY)
			try:
				os.fsync(dir_fd)
			finally:
				os.close(dir_fd)
		except OSError as exc:
			try:
				os.unlink(temp_path)
			except OSError:
				pass
			raise StateError(f"could not persist state: {exc}") from None

	def save(self) -> None:
		with self._lock:
			self.data["policy_version"] = POLICY["version"]
			try:
				self._atomic_write(self.data)
			except StateError:
				self.data = copy.deepcopy(self._committed)
				raise
			self._committed = copy.deepcopy(self.data)

	@property
	def lock(self) -> threading.RLock:
		return self._lock

	def clear_for_reset(self, keep=()):
		"""Start a fresh demo, retaining counters so old proposal IDs are never reused."""
		with self._lock:
			fresh_state = _empty_state()
			for key in ("counters", *keep):
				fresh_state[key] = copy.deepcopy(self.data[key])
			self.data = fresh_state
			self.save()

	def next_id(self, kind: str) -> str:
		with self._lock:
			next_num = self.data["counters"].get(kind, 0) + 1
			self.data["counters"][kind] = next_num
			return f"{kind}-{next_num:06d}"

	def collection(self, name: str) -> dict:
		return self.data[name]

	def get(self, name: str, key: str):
		return self.data[name].get(key)

	def put(self, name: str, key: str, value) -> None:
		self.data[name][key] = value
