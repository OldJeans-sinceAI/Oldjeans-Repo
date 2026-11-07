"""Step 5 (APPLY) client side: examples/yext_client.py.

* Happy paths run against the in-process mock.
* Failure paths (401/404/429/5xx/garbage/connection refused) run against a scripted StubServer, because the mock
  cannot produce 429/5xx. Nothing here talks to the real Yext sandbox (see test_integration_sandbox.py).
"""
import json
import socket
import unittest
import urllib.error
import urllib.parse

import helpers
from helpers import DEMO_FI, MockTestCase, StubServer, yext_error

from yext_client import YextClient, hours_to_yext_day


class HoursToYext(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(hours_to_yext_day("closed"), {"isClosed": True})
        self.assertEqual(hours_to_yext_day("  CLOSED "), {"isClosed": True})
        self.assertEqual(hours_to_yext_day("10:00-15:00"), {"openIntervals": [{"start": "10:00", "end": "15:00"}]})
        self.assertEqual(hours_to_yext_day("10:00-14:00,17:00-22:00"),
                         {"openIntervals": [{"start": "10:00", "end": "14:00"}, {"start": "17:00", "end": "22:00"}]})

    def test_no_client_side_validation_of_garbage(self):
        """Characterisation: the client does not validate; bad input surfaces as ValueError (unpack) or is passed on."""
        with self.assertRaises(ValueError):
            hours_to_yext_day("10:00")           # no dash -> unpack error
        # '25:00-26:00' is happily converted; only the server (400 / 2201) rejects it:
        self.assertEqual(hours_to_yext_day("25:00-26:00")["openIntervals"][0]["start"], "25:00")


class AgainstMock(MockTestCase):
    def setUp(self):
        super().setUp()
        self.yx = YextClient(base_url=self.base, api_key="demo", v="20261106")

    def holiday(self, eid=DEMO_FI):
        return {h["date"]: h for h in self.yx.get_entity(eid)["hours"].get("holidayHours", [])}

    def test_get_entity(self):
        self.assertEqual(self.yx.get_entity(DEMO_FI)["name"], "Kahvila Aurora")

    def test_list_entities_follows_page_tokens_and_filter(self):
        flt = {"meta.countryCode": {"$eq": "NO"}}
        ents = list(self.yx.list_entities(limit=50, filter_=flt))
        _, first = self.api.call("GET", "/v2/accounts/me/entities", {"filter": json.dumps(flt), "limit": 1})
        self.assertEqual(len(ents), first["response"]["count"])
        self.assertEqual(len({e["meta"]["id"] for e in ents}), len(ents))   # no duplicates across pages

    def test_set_holiday_hours_writes_and_preserves_weekday_hours(self):
        before = self.yx.get_entity(DEMO_FI)["hours"]
        self.yx.set_holiday_hours(DEMO_FI, "2026-12-24", "07:30-13:00")
        after = self.yx.get_entity(DEMO_FI)["hours"]
        self.assertEqual(self.holiday()["2026-12-24"], {"date": "2026-12-24",
                                                         "openIntervals": [{"start": "07:30", "end": "13:00"}]})
        for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            self.assertEqual(after[d], before[d])

    def test_closed_and_split_day(self):
        self.yx.set_holiday_hours(DEMO_FI, "2026-12-25", "closed")
        self.yx.set_holiday_hours(DEMO_FI, "2026-12-31", "10:00-14:00,17:00-22:00")
        h = self.holiday()
        self.assertEqual(h["2026-12-25"], {"date": "2026-12-25", "isClosed": True})
        self.assertEqual(len(h["2026-12-31"]["openIntervals"]), 2)

    def test_idempotent_and_replaces_same_date(self):
        self.yx.set_holiday_hours(DEMO_FI, "2026-12-24", "07:30-13:00")
        self.yx.set_holiday_hours(DEMO_FI, "2026-12-24", "07:30-13:00")
        self.yx.set_holiday_hours(DEMO_FI, "2026-12-24", "08:00-12:00")   # customer edit applied later
        entries = [h for h in self.yx.get_entity(DEMO_FI)["hours"]["holidayHours"] if h["date"] == "2026-12-24"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["openIntervals"], [{"start": "08:00", "end": "12:00"}])

    def test_other_dates_are_kept_and_sorted(self):
        for d, h in (("2027-01-01", "closed"), ("2026-12-24", "07:30-13:00"), ("2026-12-25", "closed")):
            self.yx.set_holiday_hours(DEMO_FI, d, h)
        dates = [h["date"] for h in self.yx.get_entity(DEMO_FI)["hours"]["holidayHours"]]
        self.assertEqual(dates, sorted(dates))
        self.assertTrue({"2026-12-24", "2026-12-25", "2027-01-01"} <= set(dates))

    def test_server_side_rejection_surfaces_as_runtimeerror_and_writes_nothing(self):
        with self.assertRaises(RuntimeError) as cm:
            self.yx.set_holiday_hours(DEMO_FI, "2026-12-24", "25:00-26:00")
        self.assertIn("400", str(cm.exception))
        self.assertEqual(self.api.store.update_log, [])

    def test_bad_date_rejected_by_server(self):
        with self.assertRaises(RuntimeError) as cm:
            self.yx.set_holiday_hours(DEMO_FI, "24.12.2026", "closed")
        self.assertIn("bad date", str(cm.exception))

    def test_unknown_entity_404(self):
        with self.assertRaises(RuntimeError) as cm:
            self.yx.get_entity("NOPE")
        self.assertIn("404", str(cm.exception))
        with self.assertRaises(RuntimeError):
            self.yx.set_holiday_hours("NOPE", "2026-12-24", "closed")

    def test_missing_api_key_401(self):
        self.yx.key = ""
        with self.assertRaises(RuntimeError) as cm:
            self.yx.get_entity(DEMO_FI)
        self.assertIn("401", str(cm.exception))

    def test_listings_confirmation_data_after_write(self):
        self.yx.set_holiday_hours(DEMO_FI, "2026-12-24", "07:30-13:00")
        live = [l for l in self.yx.listings([DEMO_FI])["listings"] if l["status"] == "LIVE"]
        self.assertTrue(live)
        self.assertTrue(all("expectedLiveBy" in l for l in live))   # what the customer confirmation message needs
        self.assertIn("Google (Search & Maps)", [l["publisherName"] for l in live])

    def test_url_and_auth_shape(self):
        with StubServer([(200, {"meta": {"errors": []}, "response": {"hours": {}}}, {})]) as stub:
            YextClient(base_url=stub.base + "/", api_key="K", v="20261106").get_entity("E1")
            method, path, headers, _ = stub.requests[0]
        u = urllib.parse.urlparse(path)
        self.assertEqual((method, u.path), ("GET", "/v2/accounts/me/entities/E1"))   # 'me', trailing slash tolerated
        self.assertEqual(urllib.parse.parse_qs(u.query), {"v": ["20261106"]})
        self.assertEqual({k.lower(): v for k, v in headers.items()}.get("api-key"), "K")  # urllib re-cases header names


class FailureModes(unittest.TestCase):
    """What YextClient does when Yext misbehaves. Several tests document GAPS (no retry, mixed exception types)."""

    def client(self, stub):
        return YextClient(base_url=stub.base, api_key="K", v="20261106")

    def test_401_unauthorized(self):
        with StubServer([(401, yext_error(1, "Invalid API key"), {})]) as s:
            with self.assertRaises(RuntimeError) as cm:
                self.client(s).get_entity("E1")
        self.assertIn("401", str(cm.exception))
        self.assertIn("Invalid API key", str(cm.exception))

    def test_404_not_found(self):
        with StubServer([(404, yext_error(2000, "Entity not found"), {})]) as s:
            with self.assertRaises(RuntimeError) as cm:
                self.client(s).get_entity("E1")
        self.assertIn("404", str(cm.exception))

    def test_429_rate_limited_is_raised_with_status(self):
        with StubServer([(429, yext_error(5, "Too many requests"), {"Retry-After": "2"})]) as s:
            with self.assertRaises(RuntimeError) as cm:
                self.client(s).get_entity("E1")
        self.assertIn("429", str(cm.exception))

    @unittest.expectedFailure
    def test_known_gap_429_is_retried_with_backoff(self):
        """KNOWN GAP: no retry/backoff. A 429 followed by a 200 should succeed, but the client gives up at once.
        (Yext enforces rate limits; ~3,000 businesses x several dates will hit them.)"""
        ok = {"meta": {"errors": []}, "response": {"name": "Recovered"}}
        with StubServer([(429, yext_error(5, "Too many requests"), {"Retry-After": "0"}), (200, ok, {})]) as s:
            self.assertEqual(self.client(s).get_entity("E1")["name"], "Recovered")

    def test_429_during_apply_leaves_the_write_unconfirmed(self):
        """Read succeeds, PUT is throttled: set_holiday_hours must raise (caller can keep the suggestion pending)."""
        ent = {"meta": {"errors": []}, "response": {"hours": {"holidayHours": []}}}
        with StubServer([(200, ent, {}), (429, yext_error(5, "Too many requests"), {})]) as s:
            with self.assertRaises(RuntimeError) as cm:
                self.client(s).set_holiday_hours("E1", "2026-12-24", "closed")
            self.assertEqual([r[0] for r in s.requests], ["GET", "PUT"])
        self.assertIn("429", str(cm.exception))

    def test_5xx(self):
        with StubServer([(503, "upstream down", {})]) as s:
            with self.assertRaises(RuntimeError) as cm:
                self.client(s).get_entity("E1")
        self.assertIn("503", str(cm.exception))

    def test_error_body_is_truncated_in_message(self):
        with StubServer([(500, "x" * 5000, {})]) as s:
            with self.assertRaises(RuntimeError) as cm:
                self.client(s).get_entity("E1")
        self.assertLess(len(str(cm.exception)), 500)

    def test_garbage_200_body_raises_jsondecodeerror_not_runtimeerror(self):
        """Characterisation / GAP: callers must catch more than RuntimeError (also JSONDecodeError, URLError)."""
        with StubServer([(200, "<html>maintenance</html>", {})]) as s:
            with self.assertRaises(json.JSONDecodeError):
                self.client(s).get_entity("E1")

    def test_valid_json_but_unexpected_shape_raises_keyerror(self):
        with StubServer([(200, {"unexpected": True}, {})]) as s:
            with self.assertRaises(KeyError):
                self.client(s).get_entity("E1")

    def test_connection_refused_raises_urlerror(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()  # nothing listens here
        with self.assertRaises(urllib.error.URLError):
            YextClient(base_url=f"http://127.0.0.1:{port}", api_key="K").get_entity("E1")

    def test_no_retry_is_attempted_today(self):
        with StubServer([(429, yext_error(5, "slow down"), {})]) as s:
            with self.assertRaises(RuntimeError):
                self.client(s).get_entity("E1")
            self.assertEqual(len(s.requests), 1)

    def test_apply_is_not_atomic_with_concurrent_writers(self):
        """Read-modify-write has no ETag/version check: a concurrent change between GET and PUT is overwritten.
        Documented so the 'customer edits in Connect UI while approval is pending' case is not forgotten."""
        base = {"meta": {"errors": []}, "response": {"hours": {"holidayHours": [{"date": "2026-12-31", "isClosed": True}]}}}
        with StubServer([(200, base, {}), (200, {"meta": {"errors": []}, "response": {}}, {})]) as s:
            self.client(s).set_holiday_hours("E1", "2026-12-24", "closed")
            sent = json.loads(s.requests[1][3])["hours"]["holidayHours"]
        self.assertEqual([h["date"] for h in sent], ["2026-12-24", "2026-12-31"])
        self.assertNotIn("if-match", {k.lower() for k in s.requests[1][2]})


if __name__ == "__main__":
    unittest.main()
