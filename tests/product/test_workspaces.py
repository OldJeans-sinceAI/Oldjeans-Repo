import json
import tempfile
import threading
import http.cookiejar
import urllib.request
import urllib.error
import unittest
import copy
from app.server import WebServer
from app.service import Service, AppError
from test_backend import FakeClient, FakeData, NOW


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = FakeClient()
        self.client.entities["TARGET"]["hours"] = {}
        self.main = Service(
            state_dir=self.tmp.name + "/mock",
            client=FakeClient(),
            data=FakeData(),
            now=NOW,
        )
        self.sandbox = Service(
            state_dir=self.tmp.name + "/sandbox",
            client=self.client,
            data=FakeData(),
            now=NOW,
            mode="sandbox",
            source_id="A",
            target_id="TARGET",
            allow_writes=True,
        )
        self.server = WebServer(("127.0.0.1", 0), self.main, self.sandbox)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.http.open(self.base + "/").read()

    def tearDown(self):
        self.server.shutdown()
        self.server.fleet.close()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, body=None, expected=200, schema=None, extra=None):
        prefix = "sandbox_" if path.startswith("/sandbox/") else ""
        csrf = next((c.value for c in self.jar if c.name == prefix + "csrf_token"), "")
        headers = {
            "Origin": self.base,
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": path + str(body),
        }
        headers.update(extra or {})
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
        )
        try:
            resp = self.http.open(req)
        except urllib.error.HTTPError as ex:
            resp = ex
        data = json.loads(resp.read())
        self.assertEqual(resp.status, expected, data)
        if schema:
            self.server.validators[schema].validate(data)
        return data

    def test_workspace_sessions_and_csrf_are_isolated(self):
        self.request("/sandbox/api/v1/health", expected=401)
        self.http.open(self.base + "/sandbox/").read()
        self.assertEqual(
            self.request("/api/v1/health", schema="Health")["mode"], "mock"
        )
        self.assertEqual(
            self.request("/sandbox/api/v1/health", schema="Health")["mode"], "sandbox"
        )
        self.assertEqual(
            next(c.path for c in self.jar if c.name == "sandbox_operator_session"),
            "/sandbox/",
        )
        self.request(
            "/sandbox/api/v1/operator/cycles",
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]},
            expected=403,
            extra={
                "X-CSRF-Token": next(
                    c.value for c in self.jar if c.name == "csrf_token"
                )
            },
        )
        self.assertEqual(self.client.puts, [])
        self.request("/sandbox/api/v1/operator/fleet-runs", expected=409)
        self.assertEqual(len(self.main.store.data["cases"]), 0)

    def test_reset_operator_contract_and_owner_link_revocation(self):
        self.request("/sandbox/api/v1/operator/reset", expected=401)
        self.http.open(self.base + "/sandbox/").read()
        self.server.sandbox_reset.baseline["sandbox"] = {
            "target_entity_id": "TARGET",
            "hours": {},
        }
        root = "/sandbox/api/v1/"
        self.request(
            root + "operator/cycles",
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]},
        )
        p = next(iter(self.sandbox.store.data["proposals"].values()))
        token = self.sandbox.mint_token("A", [p["proposal_id"]])
        self.request(root + "session", {"token": token})
        self.request(
            root + "proposals/" + p["proposal_id"] + "/decisions",
            {"decision": "APPROVE", "proposal_version": p["version"]},
            expected=202,
        )
        self.main.store.data["preferences"]["A"] = {
            "frequency": "MONTHLY",
            "version": 1,
        }
        preview = self.request(root + "operator/reset", schema="ResetPreview")
        body = {"confirm_reset": True, "preview_token": preview["preview_token"]}
        self.request(
            root + "operator/reset", {**body, "target_entity_id": "OTHER"}, expected=422
        )
        self.request(
            root + "operator/reset", body, extra={"X-CSRF-Token": "bad"}, expected=403
        )
        self.assertEqual(len(self.client.puts), 1)
        result = self.request(root + "operator/reset", body, schema="ResetResult")
        self.assertTrue(result["remote_verified"])
        self.assertEqual(self.sandbox.cases()["items"], [])
        self.assertEqual(
            self.main.store.data["preferences"]["A"]["frequency"], "MONTHLY"
        )
        self.request(root + "session", {"token": token}, expected=401)
        repeated = self.request(root + "operator/reset", body, schema="ResetResult")
        self.assertEqual(repeated["reset_id"], result["reset_id"])

    def test_changed_target_cannot_receive_old_approval_or_recovery(self):
        self.sandbox.cycle(
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]}
        )
        p = next(iter(self.sandbox.store.data["proposals"].values()))
        body = {"decision": "APPROVE", "proposal_version": p["version"]}
        self.sandbox.target_id = "OTHER"
        with self.assertRaises(AppError) as cm:
            self.sandbox.decide(p["proposal_id"], body, "changed-target")
        self.assertEqual(cm.exception.code, "SANDBOX_TARGET_CHANGED")
        self.assertEqual(self.client.puts, [])
        self.sandbox.target_id = "TARGET"
        self.sandbox.decide(p["proposal_id"], body, "original-target")
        self.client.entities["OTHER"] = copy.deepcopy(self.client.entities["TARGET"])
        other = Service(
            state_dir=self.tmp.name + "/sandbox",
            client=self.client,
            data=FakeData(),
            now=NOW,
            mode="sandbox",
            source_id="A",
            target_id="OTHER",
            allow_writes=True,
        )
        self.assertEqual(other.sandbox_write, "UNTESTED")
        op = next(iter(other.store.data["operations"].values()))
        put_count = len(self.client.puts)
        other._apply(op)
        self.assertEqual(op["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(self.client.puts), put_count)

    def test_real_target_route_requires_owner_and_preserves_baseline_unknown(self):
        self.http.open(self.base + "/sandbox/").read()
        root = "/sandbox/api/v1/"
        before = self.request(root + "operator/sandbox-state", schema="SandboxState")
        self.assertEqual(before["hours"], {})
        self.assertEqual(self.request(root + "operator/businesses")["total"], 1)
        self.request(
            root + "operator/cycles",
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]},
        )
        c = self.request(root + "operator/cases")["items"][0]
        pid = c["proposal_id"]
        p = self.request(root + "proposals/" + pid, schema="Proposal")
        self.assertEqual(p["baseline"]["hours"], "not_registered")
        body = {"decision": "APPROVE", "proposal_version": p["version"]}
        self.request(root + "proposals/" + pid + "/decisions", body, expected=401)
        m = self.request(
            root + "operator/messages",
            {"entity_id": "A", "proposal_ids": [pid], "delivery_mode": "PREVIEW"},
            expected=201,
            schema="Message",
        )
        self.assertEqual(self.client.puts, [])
        self.assertIn("sender", m)
        self.assertIn("recipient", m)
        self.request(
            root + "session", {"token": m["owner_entry_path"].split("#token=")[1]}
        )
        r = self.request(
            root + "proposals/" + pid + "/decisions",
            body,
            expected=202,
            schema="Result",
        )
        self.assertEqual(r["application_status"], "SUCCEEDED")
        self.assertEqual(self.client.puts[0][0], "TARGET")
        self.assertEqual(
            self.request(root + "operator/sandbox-state")["write_status"], "VERIFIED"
        )
        self.assertEqual(self.main.store.data["operations"], {})
        self.request("/api/v1/proposals/" + pid, expected=404)
