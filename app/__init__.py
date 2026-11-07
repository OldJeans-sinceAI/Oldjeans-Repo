"""Shared schema and versioned implementation policy."""

import json
from pathlib import Path

SCHEMA_VERSION = 1
with (Path(__file__).resolve().parents[1] / "config/policies.json").open(
    encoding="utf-8"
) as source:
    POLICY = json.load(source)
POLICY_VERSION = POLICY["version"]
