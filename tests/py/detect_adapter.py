"""Locate the Detect implementation under test.

    default                       -> `examples/detect.py` if present (the real thing), else None (tests skip, see GAP G1)
    DETECT_IMPL=reference         -> tests/py/reference_detect.py (test double; proves the tests themselves work)
    DETECT_MODULE=my.module       -> any importable module exposing build_profile() and run_case()
"""
from __future__ import annotations

import importlib
import os

REQUIRED = ("build_profile", "run_case")
GAP = ("CRITICAL GAP G1: no Detect layer in the repo (no examples/detect.py with build_profile()/run_case()). "
       "Contract defined in tests/DETECT_QA_REPORT.md section 5. Verify the tests with DETECT_IMPL=reference.")


def load():
    """Return (module, label) or (None, None)."""
    mode = os.environ.get("DETECT_IMPL", "").lower()
    name = "reference_detect" if mode == "reference" else os.environ.get("DETECT_MODULE", "detect")
    try:
        mod = importlib.import_module(name)
    except ImportError:
        return None, None
    if not all(hasattr(mod, f) for f in REQUIRED):
        return None, None
    return mod, ("reference double" if mode == "reference" else name)
