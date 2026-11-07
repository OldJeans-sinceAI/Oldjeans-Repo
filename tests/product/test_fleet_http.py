import copy
import threading
import unittest
import test_http


class FleetHTTPTests(unittest.TestCase):
    setUp = test_http.HTTPTests.setUp
    tearDown = test_http.HTTPTests.tearDown
    request = test_http.HTTPTests.request

    def prepare_client(self):
        self.s.client.list_entities = lambda limit=100: iter(
            copy.deepcopy(list(self.s.client.entities.values()))
        )

    def test_fleet_contract_and_no_implicit_contact(self):
        self.prepare_client()
        result = self.request(
            "/api/v1/operator/fleet-runs",
            "POST",
            {"scope": "EXPLICIT_DATE", "date": "2026-12-24"},
            expected=202,
            schema="FleetRun",
        )
        self.server.fleet.thread.join(5)
        latest = self.request("/api/v1/operator/fleet-runs", schema="FleetLatest")
        self.assertEqual(latest["run"]["processed_businesses"], 2)
        self.assertEqual(
            self.request("/api/v1/operator/messages", schema="MessageList")["total"], 0
        )
        self.request(
            "/api/v1/operator/fleet-runs/" + result["run_id"] + "/contacts",
            "POST",
            {"delivery_mode": "PREVIEW"},
            expected=202,
            schema="FleetRun",
        )
        self.server.fleet.thread.join(5)
        messages = self.request(
            "/api/v1/operator/messages?delivery_mode=PREVIEW", schema="MessageList"
        )
        self.assertEqual(messages["total"], 1)
        self.assertEqual(self.client.puts, [])

    def test_csrf_scope_and_extra_fields_enforced(self):
        self.prepare_client()
        self.request(
            "/api/v1/operator/fleet-runs",
            "POST",
            {"scope": "OPERATIONAL"},
            extra={"X-CSRF-Token": "wrong"},
            expected=403,
        )
        self.request(
            "/api/v1/operator/fleet-runs",
            "POST",
            {"scope": "EXPLICIT_DATE"},
            expected=422,
        )
        self.request(
            "/api/v1/operator/fleet-runs",
            "POST",
            {"scope": "OPERATIONAL", "apply": True},
            expected=422,
        )
        self.assertIsNone(self.server.fleet.get()["run"])

    def test_only_one_active_fleet_job(self):
        entered = threading.Event()
        release = threading.Event()

        def read(limit=100):
            entered.set()
            release.wait(5)
            return iter(copy.deepcopy(list(self.client.entities.values())))

        self.client.list_entities = read
        self.request(
            "/api/v1/operator/fleet-runs",
            "POST",
            {"scope": "OPERATIONAL"},
            expected=202,
        )
        self.assertTrue(entered.wait(1))
        try:
            self.request(
                "/api/v1/operator/fleet-runs",
                "POST",
                {"scope": "OPERATIONAL"},
                expected=409,
            )
        finally:
            release.set()
            self.server.fleet.thread.join(5)
