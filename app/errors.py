"""Application exceptions and idempotency / hash utilities."""

from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_IDEMPOTENCY_KEY_LENGTH = 200


class AppError(Exception):
	def __init__(
		self,
		status: int,
		code: str,
		message: str,
		retryable: bool = False,
		details: dict[str, Any] | None = None,
	):
		self.status = status
		self.code = code
		self.message = message
		self.retryable = retryable
		self.details = details or {}
		super().__init__(message)


def check_idempotency_key(key: str | None) -> None:
	if not key or len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
		raise AppError(
			400, "IDEMPOTENCY_KEY_REQUIRED", "A valid Idempotency-Key is required."
		)


def digest(v: str) -> str:
	return hashlib.sha256(v.encode()).hexdigest()


def fingerprint(v: Any) -> str:
	return digest(json.dumps(v, sort_keys=True, separators=(",", ":")))
