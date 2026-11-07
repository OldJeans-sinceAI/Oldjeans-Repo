"""API tests against the in-process Yext mock (mock_api/server.py). No network, no real Yext."""
import copy
import importlib.util
import json
import threading
import unittest

import helpers
from helpers import DEMO_FI, MockTestCase, full_week, http

HAVE_PANDAS = bool(importlib.util.find_spec("pandas") and importlib.util.find_spec("pyarrow"))


class Auth(MockTestCase):
    def test_health_needs_no_auth(self):
        st, body = http("GET", self.base + "/health")
        self.assertEqual(st, 200)
        self.assertEqual(body["response"]["status"], "ok")
        self.assertEqual(body["response"]["entities"], 3032)

    def test_missing_api_key_is_401(self):
        st, body = self.api.call("GET", f"/v2/accounts/me/entities/{DEMO_FI}", key=None)
        self.assertEqual(st, 401)
        self.assertEqual(body["meta"]["errors"][0]["type"], "FATAL_ERROR")

    def test_api_key_in_header_is_accepted(self):
        st, _ = self.api.call("GET", f"/v2/accounts/me/entities/{DEMO_FI}", key=None, headers={"api-key": "demo"})
        self.assertEqual(st, 200)

    def test_missing_or_malformed_version_is_400(self):
        for v in (None, "abc", "2026-11-06", "202611061"):
            st, _ = self.api.call("GET", f"/v2/accounts/me/entities/{DEMO_FI}", v=v)
            self.assertEqual(st, 400, v)

    def test_mock_does_not_validate_key_value(self):
        """Characterisation: ANY non-empty key works on the mock, so 'invalid key -> 401' can only be tested
        against the real sandbox (see test_integration_sandbox.py)."""
        st, _ = self.api.call("GET", f"/v2/accounts/me/entities/{DEMO_FI}", key="totally-wrong")
        self.assertEqual(st, 200)

    def test_put_without_key_is_401(self):
        st, _ = self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", key=None, body={"hours": full_week()})
        self.assertEqual(st, 401)

    def test_cors_headers(self):
        import urllib.request
        req = urllib.request.Request(self.base + "/health", method="OPTIONS")
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 204)
            self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
            self.assertIn("PUT", r.headers["Access-Control-Allow-Methods"])


class ReadEndpoints(MockTestCase):
    def test_get_entity(self):
        st, body = self.api.entity(DEMO_FI)
        self.assertEqual(st, 200)
        self.assertEqual(body["response"]["name"], "Kahvila Aurora")
        self.assertEqual(body["response"]["meta"]["id"], DEMO_FI)

    def test_unknown_entity_is_404_with_yext_style_error(self):
        st, body = self.api.entity("DOES-NOT-EXIST")
        self.assertEqual(st, 404)
        self.assertEqual(body["meta"]["errors"][0]["code"], 2000)

    def test_unknown_endpoint_is_404(self):
        st, _ = self.api.call("GET", "/v2/accounts/me/nope")
        self.assertEqual(st, 404)

    def test_list_limit_is_capped_at_50_and_paginates(self):
        st, body = self.api.call("GET", "/v2/accounts/me/entities", {"limit": 500})
        self.assertEqual(len(body["response"]["entities"]), 50)
        self.assertEqual(body["response"]["count"], 3032)
        token = body["response"]["pageToken"]
        _, p2 = self.api.call("GET", "/v2/accounts/me/entities", {"limit": 50, "pageToken": token})
        ids1 = {e["meta"]["id"] for e in body["response"]["entities"]}
        ids2 = {e["meta"]["id"] for e in p2["response"]["entities"]}
        self.assertFalse(ids1 & ids2)

    def test_filter_eq_and_in(self):
        f = json.dumps({"meta.countryCode": {"$eq": "NO"}})
        _, body = self.api.call("GET", "/v2/accounts/me/entities", {"filter": f, "limit": 50})
        self.assertTrue(body["response"]["entities"])
        self.assertTrue(all(e["meta"]["countryCode"] == "NO" for e in body["response"]["entities"]))
        f = json.dumps({"meta.countryCode": {"$in": ["NO", "SE"]}})
        _, both = self.api.call("GET", "/v2/accounts/me/entities", {"filter": f, "limit": 50})
        self.assertGreater(both["response"]["count"], body["response"]["count"])

    def test_unsupported_filter_operator_and_bad_json_are_400(self):
        for f in (json.dumps({"name": {"$startsWith": "K"}}), "{not json"):
            st, _ = self.api.call("GET", "/v2/accounts/me/entities", {"filter": f})
            self.assertEqual(st, 400, f)

    def test_non_numeric_limit_is_400_not_500(self):
        st, _ = self.api.call("GET", "/v2/accounts/me/entities", {"limit": "abc"})
        self.assertEqual(st, 400)

    def test_listings_requires_location_ids(self):
        st, _ = self.api.call("GET", "/v2/accounts/me/listings/listings")
        self.assertEqual(st, 400)

    def test_listings_before_any_write_have_no_expected_live_by(self):
        _, body = self.api.call("GET", "/v2/accounts/me/listings/listings", {"locationIds": DEMO_FI})
        live = [l for l in body["response"]["listings"] if l["status"] == "LIVE"]
        self.assertTrue(live)
        self.assertTrue(all("expectedLiveBy" not in l for l in live))

    def test_reviews_and_publisher_suggestions_filter_by_location(self):
        _, r = self.api.call("GET", "/v2/accounts/me/reviews", {"locationIds": DEMO_FI, "limit": 100})
        self.assertTrue(all(x["locationId"] == DEMO_FI for x in r["response"]["reviews"]))
        _, s = self.api.call("GET", "/v2/accounts/me/listings/publishersuggestions",
                             {"statuses": "ACCEPTED,REJECTED", "limit": 50})
        self.assertTrue(all(x["status"] in ("ACCEPTED", "REJECTED") for x in s["response"]["suggestions"]))

    @unittest.skipUnless(HAVE_PANDAS, "pandas+pyarrow not installed")
    def test_analytics_report(self):
        st, body = self.api.call("POST", "/v2/accounts/me/analytics/reports",
                                 body={"metrics": ["GOOGLE_SEARCH_VIEWS"], "dimensions": ["DAYS", "ENTITY_IDS"],
                                       "filters": {"startDate": "2026-10-01", "endDate": "2026-10-07",
                                                   "entityIds": [DEMO_FI]}})
        self.assertEqual(st, 200)
        self.assertEqual(len(body["response"]["data"]), 7)

    @unittest.skipIf(HAVE_PANDAS, "only meaningful when analytics deps are missing")
    def test_analytics_without_pandas_is_501_not_a_crash(self):
        st, _ = self.api.call("POST", "/v2/accounts/me/analytics/reports", body={})
        self.assertEqual(st, 501)


class ApplyWritePath(MockTestCase):
    """Step 5 (APPLY): PUT /entities/{id}."""

    def current_hours(self):
        return copy.deepcopy(self.api.entity(DEMO_FI)[1]["response"]["hours"])

    def test_put_full_hours_with_holiday_persists(self):
        h = self.current_hours()
        h["holidayHours"] = [{"date": "2026-12-24", "openIntervals": [{"start": "07:30", "end": "13:00"}]}]
        st, body = self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", body={"hours": h})
        self.assertEqual(st, 200, body)
        got = self.api.entity(DEMO_FI)[1]["response"]["hours"]["holidayHours"]
        self.assertIn({"date": "2026-12-24", "openIntervals": [{"start": "07:30", "end": "13:00"}]}, got)

    def test_put_is_recorded_in_update_log_and_unlocks_expected_live_by(self):
        h = self.current_hours()
        h["holidayHours"] = [{"date": "2026-12-25", "isClosed": True}]
        self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", body={"hours": h})
        self.assertEqual(self.api.store.update_log[-1]["entityId"], DEMO_FI)
        _, body = self.api.call("GET", "/v2/accounts/me/listings/listings", {"locationIds": DEMO_FI})
        live = [l for l in body["response"]["listings"] if l["status"] == "LIVE"]
        self.assertTrue(all("expectedLiveBy" in l and "lastUpdateSentAt" in l for l in live))

    def test_holiday_only_payload_keeps_weekday_hours_and_warns(self):
        before = self.current_hours()
        st, body = self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}",
                                 body={"hours": {"holidayHours": [{"date": "2026-12-24", "isClosed": True}]}})
        self.assertEqual(st, 200)
        self.assertEqual(body["meta"]["errors"][0]["code"], 9001)
        after = self.api.entity(DEMO_FI)[1]["response"]["hours"]
        for d in ("monday", "saturday", "sunday"):
            self.assertEqual(after[d], before[d])

    def test_invalid_hours_are_rejected_400_and_not_persisted(self):
        before = self.api.entity(DEMO_FI)[1]["response"]
        bad = copy.deepcopy(before["hours"])
        bad["holidayHours"] = [{"date": "2026-12-24", "openIntervals": [{"start": "9:00", "end": "13:00"}]}]
        st, body = self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", body={"hours": bad})
        self.assertEqual(st, 400)
        self.assertEqual(body["meta"]["errors"][0]["code"], 2201)
        self.assertEqual(self.api.entity(DEMO_FI)[1]["response"], before)
        self.assertEqual(self.api.store.update_log, [])

    def test_unsupported_fields_rejected(self):
        st, body = self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", body={"mainPhone": "123"})
        self.assertEqual(st, 400)
        self.assertIn("only hours/closed/name", body["meta"]["errors"][0]["message"])

    def test_non_json_body_is_400(self):
        st, _ = self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", raw_body=b"{not json")
        self.assertEqual(st, 400)

    def test_put_unknown_entity_is_404(self):
        st, body = self.api.call("PUT", "/v2/accounts/me/entities/NOPE", body={"hours": full_week()})
        self.assertEqual(st, 404)
        self.assertEqual(body["meta"]["errors"][0]["code"], 2000)

    def test_put_unknown_route_is_404(self):
        st, _ = self.api.call("PUT", "/v2/accounts/me/reviews", body={})
        self.assertEqual(st, 404)

    def test_reset_undoes_writes(self):
        before = self.api.entity(DEMO_FI)[1]["response"]
        h = self.current_hours()
        h["holidayHours"] = [{"date": "2026-12-24", "isClosed": True}]
        self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", body={"hours": h})
        self.assertNotEqual(self.api.entity(DEMO_FI)[1]["response"], before)
        self.api.reset()
        self.assertEqual(self.api.entity(DEMO_FI)[1]["response"], before)

    def test_state_file_is_a_temp_file_not_the_repo_one(self):
        self.assertNotIn("mock_api", self.api.server.STATE_FILE)

    def test_parallel_puts_all_succeed(self):
        results = []

        def put(i):
            h = self.current_hours()
            h["holidayHours"] = [{"date": f"2027-01-{i + 1:02d}", "isClosed": True}]
            results.append(self.api.call("PUT", f"/v2/accounts/me/entities/{DEMO_FI}", body={"hours": h})[0])

        ts = [threading.Thread(target=put, args=(i,)) for i in range(10)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(results, [200] * 10)
        self.assertEqual(len(self.api.store.update_log), 10)  # no lost log entries


class OwnerSimulatorEndpoint(MockTestCase):
    """Step 4 (DECIDE) stand-in: POST /sim/v1/owner-response."""

    def post(self, **body):
        return http("POST", self.base + "/sim/v1/owner-response", body=body)

    def test_body_required_and_fields_required(self):
        self.assertEqual(self.post()[0], 400)
        self.assertEqual(self.post(entityId=DEMO_FI, date="2026-12-24")[0], 400)

    def test_bad_hours_string_rejected(self):
        for bad in ("9-17", "open", "25:00-26:00"):
            self.assertEqual(self.post(entityId=DEMO_FI, date="2026-12-24", proposedHours=bad)[0], 400, bad)

    def test_scored_test_entities_are_refused_403(self):
        st, body = self.post(entityId="FI-00001", date="2026-11-08", proposedHours="closed")
        self.assertEqual(st, 403)
        self.assertIn("test entities are used for scoring", body["meta"]["errors"][0]["message"])

    def test_unknown_date_for_demo_entity_is_403(self):
        self.assertEqual(self.post(entityId=DEMO_FI, date="2031-01-01", proposedHours="closed")[0], 403)

    def test_response_shape_and_determinism(self):
        a = self.post(entityId=DEMO_FI, date="2026-12-24", proposedHours="07:30-13:00", messageId="m1")
        b = self.post(entityId=DEMO_FI, date="2026-12-24", proposedHours="07:30-13:00", messageId="m1")
        self.assertEqual(a[0], 200)
        self.assertEqual(a[1]["response"], b[1]["response"])
        self.assertIn(a[1]["response"]["decision"], ("ACCEPTED", "EDITED", "REJECTED", "NO_RESPONSE"))
        self.assertEqual(a[1]["response"]["channel"], "SMS")  # persona default

    def test_channel_override(self):
        _, body = self.post(entityId=DEMO_FI, date="2026-12-24", proposedHours="07:30-13:00", channel="EMAIL")
        self.assertEqual(body["response"]["channel"], "EMAIL")

    def test_simulator_does_not_write_to_the_entity(self):
        before = self.api.entity(DEMO_FI)[1]
        self.post(entityId=DEMO_FI, date="2026-12-24", proposedHours="closed")
        self.assertEqual(self.api.entity(DEMO_FI)[1]["response"], before["response"])


if __name__ == "__main__":
    unittest.main()
