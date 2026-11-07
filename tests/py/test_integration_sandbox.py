"""@integration - hits the REAL Yext sandbox (https://sbx-api.yextapis.com). Skipped in normal CI.

Enable (never commit keys; load them from your shell, not from tests):
    set -a; source .env; set +a                     # YEXT_BASE_URL / YEXT_API_KEY / YEXT_ENTITY_ID / YEXT_API_VERSION
    RUN_INTEGRATION=1 python -m unittest tests/py/test_integration_sandbox.py
    RUN_INTEGRATION=1 pytest -m integration
Write tests additionally need  YEXT_ALLOW_WRITE=1  and only touch ONE date (YEXT_TEST_DATE, default 2027-12-24),
restoring the original holidayHours afterwards.

Note: YEXT_BASE_URL in .env has a trailing slash (the JS script needs it); YextClient strips it.
"""
import copy
import os
import unittest

import helpers
from helpers import integration

from yext_client import YextClient

BASE = os.environ.get("YEXT_BASE_URL", "https://sbx-api.yextapis.com")
KEY = os.environ.get("YEXT_API_KEY")
EID = os.environ.get("YEXT_ENTITY_ID")
V = os.environ.get("YEXT_API_VERSION") or "20261106"
TEST_DATE = os.environ.get("YEXT_TEST_DATE", "2027-12-24")
HAVE_CREDS = bool(KEY and EID)


def need_creds(fn):
    return unittest.skipUnless(HAVE_CREDS, "YEXT_API_KEY / YEXT_ENTITY_ID not set")(fn)


def need_write(fn):
    return unittest.skipUnless(os.environ.get("YEXT_ALLOW_WRITE") == "1", "set YEXT_ALLOW_WRITE=1 to allow PUT")(fn)


@integration
class SandboxRead(unittest.TestCase):
    """@integration read-only checks."""

    def setUp(self):
        self.yx = YextClient(base_url=BASE, api_key=KEY, v=V)

    @need_creds
    def test_get_entity_returns_name_and_hours(self):
        e = self.yx.get_entity(EID)
        self.assertTrue(e.get("name"))
        self.assertIn("meta", e)

    @need_creds
    def test_unknown_entity_is_404(self):
        with self.assertRaises(RuntimeError) as cm:
            self.yx.get_entity("definitely-not-an-entity-id-123")
        self.assertIn("404", str(cm.exception))

    def test_invalid_api_key_is_401_or_403(self):
        bad = YextClient(base_url=BASE, api_key="invalid-key-for-test", v=V)
        with self.assertRaises(RuntimeError) as cm:
            bad.get_entity(EID or "any")
        self.assertRegex(str(cm.exception), r"\b(401|403)\b")

    @need_creds
    def test_missing_version_parameter_is_rejected(self):
        import urllib.error, urllib.request
        url = f"{BASE.rstrip('/')}/v2/accounts/me/entities/{EID}?api_key={KEY}"   # no v=
        try:
            urllib.request.urlopen(url, timeout=30)
            self.fail("expected an HTTP error without v=")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (400, 401))   # Yext requires v=YYYYMMDD; exact code not documented in repo


@integration
class SandboxApply(unittest.TestCase):
    """@integration write path (step 5). Restores the original holidayHours."""

    def setUp(self):
        self.yx = YextClient(base_url=BASE, api_key=KEY, v=V)

    @need_creds
    @need_write
    def test_write_then_read_back_then_restore(self):
        original = copy.deepcopy(self.yx.get_entity(EID).get("hours", {}))
        orig_hol = [h for h in original.get("holidayHours", [])]
        try:
            self.yx.set_holiday_hours(EID, TEST_DATE, "07:30-13:00")
            got = [h for h in self.yx.get_entity(EID)["hours"]["holidayHours"] if h["date"] == TEST_DATE]
            self.assertEqual(got[0]["openIntervals"], [{"start": "07:30", "end": "13:00"}])
            # edit applied later replaces, never duplicates
            self.yx.set_holiday_hours(EID, TEST_DATE, "closed")
            got = [h for h in self.yx.get_entity(EID)["hours"]["holidayHours"] if h["date"] == TEST_DATE]
            self.assertEqual(got, [{"date": TEST_DATE, "isClosed": True}])
        finally:
            restore = copy.deepcopy(original)
            restore["holidayHours"] = orig_hol
            self.yx._req("PUT", f"entities/{EID}", body={"hours": restore})
        after = [h for h in self.yx.get_entity(EID)["hours"].get("holidayHours", []) if h["date"] == TEST_DATE]
        self.assertEqual(after, [h for h in orig_hol if h["date"] == TEST_DATE])

    @need_creds
    @need_write
    def test_invalid_hours_are_rejected_by_yext_with_4xx(self):
        with self.assertRaises(RuntimeError) as cm:
            self.yx.set_holiday_hours(EID, TEST_DATE, "25:00-26:00")
        self.assertRegex(str(cm.exception), r"\b4\d\d\b")


if __name__ == "__main__":
    unittest.main()
