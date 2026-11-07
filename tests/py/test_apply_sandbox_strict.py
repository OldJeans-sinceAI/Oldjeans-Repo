"""Steps A/B (refresh calls) and step 5 APPLY, with the sandbox rules asserted strictly.

Rules under test (task brief "ENVIRONMENT CONSTRAINTS"):
  * account is `me`, every call carries v=YYYYMMDD, base URL is configurable (mock or https://sbx-api.yextapis.com)
  * Knowledge Graph fields are fixed: Apply may change VALUES (hours.holidayHours) but must never add fields/keys
  * Listings are fixed: no new publishers; confirmation comes from data/listings.json (served by the mock)
  * A/B (data refresh) is read-only: zero PUTs

Offline tests use the in-process mock or a scripted StubServer. `@integration` tests hit the REAL sandbox and are
skipped unless RUN_INTEGRATION=1 (+ YEXT_* env); writes also need YEXT_ALLOW_WRITE=1 and restore what they change.
"""
import contextlib
import copy
import io
import json
import os
import re
import unittest
import urllib.parse

import helpers
from helpers import MockTestCase, StubServer, ROOT, integration

from yext_client import DAYS, YextClient

WEEKDAYS = set(DAYS)
HOURS_KEYS = WEEKDAYS | {"holidayHours", "reopenDate", "holidayHoursConversationEnabled"}
HOLIDAY_ITEM_KEYS = {"date", "isClosed", "isRegularHours", "openIntervals"}
DEMO_IDS = ["FI-D0001", "SE-D0008", "NO-D0009"]            # one per country
LISTINGS = json.load(open(os.path.join(ROOT, "data", "listings.json"), encoding="utf-8"))["listings"]
PUBLISHER_UNIVERSE = {l["publisherId"] for l in LISTINGS}
V = "20261106"


def ok(payload):
    return (200, {"meta": {"uuid": "stub", "errors": []}, "response": payload}, None)


def week_obj(h="09:00-17:00"):
    a, b = h.split("-")
    return {d: {"openIntervals": [{"start": a, "end": b}]} for d in DAYS}


# ============================================================================ steps A/B: refresh calls
class DetectRefreshCallsAreReadOnly(unittest.TestCase):
    """A (source data changed) and B (refresh profile) pull entities, reviews, suggestions, analytics."""

    def test_refresh_sequence_shape_and_zero_writes(self):
        script = [ok({"entities": [{"meta": {"id": "A"}}], "pageToken": "t2"}),
                  ok({"entities": [{"meta": {"id": "B"}}]}),
                  ok({"reviews": [], "count": 0}), ok({"suggestions": []}), ok({"rows": []})]
        with StubServer(script) as s:
            yx = YextClient(base_url=s.base, api_key="k", v=V)
            ids = [e["meta"]["id"] for e in yx.list_entities(limit=1)]
            yx.reviews(["A", "B"], min_date="2026-06-01")
            yx.publisher_suggestions(["A"], statuses=["WAITING_ON_CUSTOMER"])
            yx.analytics(["GOOGLE_SEARCH_VIEWS"], "2026-01-01", "2026-10-31", ["A"])
        self.assertEqual(ids, ["A", "B"])
        self.assertEqual(len(s.requests), 5)
        for method, path, headers, body in s.requests:
            u = urllib.parse.urlparse(path)
            self.assertTrue(u.path.startswith("/v2/accounts/me/"), f"account must be `me`: {u.path}")
            self.assertRegex(urllib.parse.parse_qs(u.query)["v"][0], r"^\d{8}$")
            self.assertEqual({k.lower(): v for k, v in headers.items()}.get("api-key"), "k")
            self.assertNotEqual(method, "PUT", "refresh (A/B) must never write")
        self.assertEqual([r[0] for r in s.requests], ["GET", "GET", "GET", "GET", "POST"])
        q2 = urllib.parse.parse_qs(urllib.parse.urlparse(s.requests[1][1]).query)
        self.assertEqual(q2["pageToken"], ["t2"], "second page must follow the pageToken")
        q3 = urllib.parse.parse_qs(urllib.parse.urlparse(s.requests[2][1]).query)
        self.assertEqual((q3["locationIds"], q3["minPublisherDate"]), (["A,B"], ["2026-06-01"]))
        q4 = urllib.parse.parse_qs(urllib.parse.urlparse(s.requests[3][1]).query)
        self.assertEqual(q4["statuses"], ["WAITING_ON_CUSTOMER"])
        body = json.loads(s.requests[4][3])
        self.assertEqual(body["metrics"], ["GOOGLE_SEARCH_VIEWS"])
        self.assertEqual(body["filters"], {"startDate": "2026-01-01", "endDate": "2026-10-31", "entityIds": ["A"]})

    def test_reviews_and_suggestions_endpoints_exist_on_the_mock(self):
        api = helpers.MockApi.get()
        api.reset()
        st, r = api.call("GET", "/v2/accounts/me/reviews", {"locationIds": "FI-D0001", "limit": 5})
        self.assertEqual(st, 200)
        self.assertIn("reviews", r["response"])
        st, r = api.call("GET", "/v2/accounts/me/listings/publishersuggestions", {"locationIds": "FI-D0001"})
        self.assertEqual(st, 200)
        self.assertIn("suggestions", r["response"])

    def test_missing_version_parameter_is_rejected_by_the_mock(self):
        api = helpers.MockApi.get()
        st, _ = api.call("GET", "/v2/accounts/me/entities/FI-D0001", v=None)
        self.assertEqual(st, 400)


# ============================================================================ step 5: APPLY, strict schema
class ApplyOnlyUpdatesExistingValues(MockTestCase):
    def apply_and_diff(self, eid, day="2026-12-24", hours="07:30-13:00"):
        yx = YextClient(base_url=self.base, api_key="demo", v=V)
        before = copy.deepcopy(yx.get_entity(eid))
        yx.set_holiday_hours(eid, day, hours)
        return before, yx.get_entity(eid)

    def test_only_hours_holidayhours_changes_for_each_country(self):
        for eid in DEMO_IDS:
            with self.subTest(entity=eid):
                before, after = self.apply_and_diff(eid)
                self.assertEqual(set(after), set(before), "no top-level field may be added or removed")
                for k in before:
                    if k != "hours":
                        self.assertEqual(after[k], before[k], f"field {k} must not change")
                self.assertEqual(set(after["hours"]) - set(before["hours"]), {"holidayHours"} - set(before["hours"]))
                for k in set(before["hours"]) - {"holidayHours"}:
                    self.assertEqual(after["hours"][k], before["hours"][k], f"hours.{k} must not change")
                self.assertLessEqual(set(after["hours"]), HOURS_KEYS)

    def test_holiday_item_has_exactly_one_state_flag_and_only_schema_keys(self):
        for hours, flag in (("closed", "isClosed"), ("07:30-13:00", "openIntervals"),
                            ("10:00-14:00,17:00-22:00", "openIntervals")):
            with self.subTest(hours=hours):
                _, after = self.apply_and_diff("FI-D0001", hours=hours)
                item = next(h for h in after["hours"]["holidayHours"] if h["date"] == "2026-12-24")
                self.assertLessEqual(set(item), HOLIDAY_ITEM_KEYS)
                self.assertEqual(sum(bool(item.get(x)) for x in ("isClosed", "isRegularHours", "openIntervals")), 1)
                self.assertIn(flag, item)
                self.api.reset()

    def test_apply_replaces_the_date_never_duplicates_and_keeps_other_dates(self):
        yx = YextClient(base_url=self.base, api_key="demo", v=V)
        yx.set_holiday_hours("FI-D0001", "2026-12-31", "09:00-14:00")
        yx.set_holiday_hours("FI-D0001", "2026-12-24", "07:30-13:00")
        yx.set_holiday_hours("FI-D0001", "2026-12-24", "closed")
        hol = yx.get_entity("FI-D0001")["hours"]["holidayHours"]
        self.assertEqual([h["date"] for h in hol], ["2026-12-24", "2026-12-31"])
        self.assertEqual(hol[0], {"date": "2026-12-24", "isClosed": True})

    def test_server_side_update_log_shows_hours_only(self):
        YextClient(base_url=self.base, api_key="demo", v=V).set_holiday_hours("FI-D0001", "2026-12-24", "closed")
        self.assertEqual([u["fields"] for u in self.api.store.update_log], [["hours"]])

    def test_new_top_level_field_is_refused_and_nothing_is_written(self):
        before = self.api.entity("FI-D0001")[1]["response"]
        st, body = self.api.call("PUT", "/v2/accounts/me/entities/FI-D0001", body={"c_brandNewField": "x"})
        self.assertEqual(st, 400)
        self.assertEqual(self.api.entity("FI-D0001")[1]["response"], before)

    def test_new_key_inside_hours_is_refused_and_nothing_is_written(self):
        before = self.api.entity("FI-D0001")[1]["response"]
        bad = {**before["hours"], "specialSeasonHours": []}
        st, body = self.api.call("PUT", "/v2/accounts/me/entities/FI-D0001", body={"hours": bad})
        self.assertEqual(st, 400)
        self.assertIn("unknown key", json.dumps(body))
        self.assertEqual(self.api.entity("FI-D0001")[1]["response"], before)

    def test_apply_never_creates_or_removes_entities(self):
        yx = YextClient(base_url=self.base, api_key="demo", v=V)
        n = len(list(yx.list_entities(limit=500, filter_={"meta.countryCode": {"$eq": "FI"}})))
        yx.set_holiday_hours("FI-D0001", "2026-12-24", "closed")
        self.assertEqual(len(list(yx.list_entities(limit=500, filter_={"meta.countryCode": {"$eq": "FI"}}))), n)


class ApplyPayloadOnTheWire(unittest.TestCase):
    """Capture the exact PUT body. Proves read-modify-write keeps unknown-to-us hours keys and sends nothing else."""

    ENTITY = {"meta": {"id": "SinceAI05"}, "name": "Sandbox Cafe", "c_segment": "cafe", "description": "x",
              "hours": {**week_obj(), "reopenDate": "2027-01-10", "holidayHoursConversationEnabled": True,
                        "holidayHours": [{"date": "2026-12-31", "isClosed": True}]}}

    def run_apply(self):
        with StubServer([ok(copy.deepcopy(self.ENTITY)), ok({"id": "SinceAI05"})]) as s:
            YextClient(base_url=s.base, api_key="k", v=V).set_holiday_hours("SinceAI05", "2026-12-24", "07:30-13:00")
        return s.requests

    def test_exactly_one_get_then_one_put_to_the_entity(self):
        reqs = self.run_apply()
        self.assertEqual([r[0] for r in reqs], ["GET", "PUT"])
        self.assertEqual(urllib.parse.urlparse(reqs[1][1]).path, "/v2/accounts/me/entities/SinceAI05")

    def test_put_body_contains_only_hours(self):
        body = json.loads(self.run_apply()[1][3])
        self.assertEqual(set(body), {"hours"}, "no name/description/c_* fields may be pushed")

    def test_put_hours_adds_no_keys_and_keeps_existing_ones(self):
        hours = json.loads(self.run_apply()[1][3])["hours"]
        self.assertEqual(set(hours), set(self.ENTITY["hours"]), "hours keys must equal the keys read from Yext")
        self.assertEqual(hours["reopenDate"], "2027-01-10")
        self.assertIs(hours["holidayHoursConversationEnabled"], True)
        for d in DAYS:
            self.assertEqual(hours[d], self.ENTITY["hours"][d])

    def test_put_holiday_items_are_schema_valid_and_keep_unrelated_dates(self):
        items = json.loads(self.run_apply()[1][3])["hours"]["holidayHours"]
        self.assertEqual([i["date"] for i in items], ["2026-12-24", "2026-12-31"])
        for i in items:
            self.assertLessEqual(set(i), HOLIDAY_ITEM_KEYS)
        self.assertEqual(items[0]["openIntervals"], [{"start": "07:30", "end": "13:00"}])

    def test_every_call_uses_me_and_a_dated_version(self):
        for _, path, _, _ in self.run_apply():
            u = urllib.parse.urlparse(path)
            self.assertTrue(u.path.startswith("/v2/accounts/me/"))
            self.assertEqual(urllib.parse.parse_qs(u.query)["v"], [V])

    def test_apply_plus_confirmation_never_writes_to_listings(self):
        with StubServer([ok(copy.deepcopy(self.ENTITY)), ok({}), ok({"listings": []})]) as s:
            yx = YextClient(base_url=s.base, api_key="k", v=V)
            yx.set_holiday_hours("SinceAI05", "2026-12-24", "closed")
            yx.listings(["SinceAI05"])
        writes = [(m, p) for m, p, _, _ in s.requests if m in ("PUT", "POST", "DELETE", "PATCH")]
        self.assertEqual(len(writes), 1)
        self.assertIn("/entities/SinceAI05", writes[0][1])
        self.assertFalse([p for m, p, _, _ in s.requests if "/listings" in p and m != "GET"])


# ============================================================================ listings.json = confirmation source
class ApplyConfirmationUsesListingsJson(MockTestCase):
    EID = "FI-D0001"

    def listings(self):
        return YextClient(base_url=self.base, api_key="demo", v=V).listings([self.EID])["listings"]

    def expected_rows(self):
        return {l["publisherId"]: l for l in LISTINGS if l["entityId"] == self.EID}

    def test_mock_serves_exactly_the_rows_of_data_listings_json(self):
        got = {l["publisherId"]: l for l in self.listings()}
        exp = self.expected_rows()
        self.assertEqual(set(got), set(exp))
        for pid, row in exp.items():
            for k in ("publisherName", "status", "typicalUpdateSpeedSeconds", "listingUrl"):
                self.assertEqual(got[pid][k], row[k], f"{pid}.{k}")

    def test_apply_does_not_add_or_remove_publishers(self):
        before = {l["publisherId"] for l in self.listings()}
        YextClient(base_url=self.base, api_key="demo", v=V).set_holiday_hours(self.EID, "2026-12-24", "07:30-13:00")
        after = {l["publisherId"] for l in self.listings()}
        self.assertEqual(before, after)
        self.assertLessEqual(after, PUBLISHER_UNIVERSE)

    def test_only_live_listings_get_an_expected_live_by_time(self):
        YextClient(base_url=self.base, api_key="demo", v=V).set_holiday_hours(self.EID, "2026-12-24", "07:30-13:00")
        rows = self.listings()
        self.assertTrue(any(l["status"] != "LIVE" for l in rows), "fixture should include a non-LIVE publisher")
        for l in rows:
            if l["status"] == "LIVE":
                self.assertRegex(l["expectedLiveBy"], r"^\d{4}-\d\d-\d\dT")
            else:
                self.assertNotIn("expectedLiveBy", l, f"{l['publisherId']} is {l['status']}")

    def test_expected_live_by_is_update_time_plus_publisher_speed(self):
        from datetime import datetime
        YextClient(base_url=self.base, api_key="demo", v=V).set_holiday_hours(self.EID, "2026-12-24", "07:30-13:00")
        for l in (x for x in self.listings() if x["status"] == "LIVE"):
            sent = datetime.fromisoformat(l["lastUpdateSentAt"].rstrip("Z"))
            live = datetime.fromisoformat(l["expectedLiveBy"].rstrip("Z"))
            self.assertLessEqual(abs((live - sent).total_seconds() - l["typicalUpdateSpeedSeconds"]), 1)

    def test_quickstart_confirmation_lists_exactly_the_live_publishers_from_listings_json(self):
        import quickstart
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            quickstart.run(self.EID, __import__("datetime").date(2026, 12, 24), self.base)
        out = buf.getvalue()
        if "5 APPLY    written" not in out:
            self.skipTest("owner simulator did not approve this case; nothing applied")
        live = [l for l in self.expected_rows().values() if l["status"] == "LIVE"]
        confirm = out.split("new hours visible on:")[1]
        for l in live:
            self.assertIn(l["publisherName"], confirm)
        for l in self.expected_rows().values():
            if l["status"] != "LIVE":
                self.assertNotIn(l["publisherName"], confirm)
        speeds = [l["typicalUpdateSpeedSeconds"] for l in sorted(live, key=lambda x: x["typicalUpdateSpeedSeconds"])]
        self.assertEqual(speeds, sorted(speeds))


# ============================================================================ @integration: REAL sandbox
BASE = os.environ.get("YEXT_BASE_URL", "https://sbx-api.yextapis.com")
KEY, EID = os.environ.get("YEXT_API_KEY"), os.environ.get("YEXT_ENTITY_ID")
LIVE_V = os.environ.get("YEXT_API_VERSION") or V
TEST_DATE = os.environ.get("YEXT_TEST_DATE", "2027-12-24")


def need_creds(fn):
    return unittest.skipUnless(KEY and EID, "YEXT_API_KEY / YEXT_ENTITY_ID not set")(fn)


def need_write(fn):
    return unittest.skipUnless(os.environ.get("YEXT_ALLOW_WRITE") == "1", "set YEXT_ALLOW_WRITE=1 to allow PUT")(fn)


@integration
class SandboxStrictSchema(unittest.TestCase):
    """@integration - live sandbox. Read-only unless YEXT_ALLOW_WRITE=1."""

    def setUp(self):
        self.yx = YextClient(base_url=BASE, api_key=KEY, v=LIVE_V)

    @need_creds
    def test_live_entity_hours_use_only_schema_keys(self):
        hours = self.yx.get_entity(EID).get("hours", {})
        self.assertLessEqual(set(hours), HOURS_KEYS)
        for item in hours.get("holidayHours", []):
            self.assertLessEqual(set(item), HOLIDAY_ITEM_KEYS)

    @need_creds
    def test_live_publishers_are_within_the_fixed_listings_universe(self):
        try:
            rows = self.yx.listings([EID])["listings"]
        except RuntimeError as e:
            self.skipTest(f"listings endpoint not available for this sandbox entity: {e}")
        self.assertLessEqual({l["publisherId"] for l in rows}, PUBLISHER_UNIVERSE,
                             "sandbox lists a publisher that is not in data/listings.json (publishers are fixed)")

    @need_creds
    @need_write
    def test_live_apply_changes_only_holiday_hours_values_then_restores(self):
        before = copy.deepcopy(self.yx.get_entity(EID))
        orig_hours = copy.deepcopy(before.get("hours", {}))
        try:
            self.yx.set_holiday_hours(EID, TEST_DATE, "07:30-13:00")
            after = self.yx.get_entity(EID)
            self.assertEqual(set(after), set(before), "Apply added/removed a Knowledge Graph field")
            for k in before:
                if k not in ("hours", "meta"):
                    self.assertEqual(after[k], before[k], f"Apply changed {k}")
            self.assertLessEqual(set(after["hours"]), HOURS_KEYS)
            for k in set(orig_hours) - {"holidayHours"}:
                self.assertEqual(after["hours"][k], orig_hours[k], f"Apply changed hours.{k}")
            self.assertIn(TEST_DATE, [h["date"] for h in after["hours"]["holidayHours"]])
        finally:
            self.yx._req("PUT", f"entities/{EID}", body={"hours": orig_hours})
        restored = self.yx.get_entity(EID).get("hours", {})
        self.assertEqual(restored.get("holidayHours", []), orig_hours.get("holidayHours", []))


if __name__ == "__main__":
    unittest.main()
