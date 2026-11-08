import http.cookiejar, json, tempfile, threading, unittest, urllib.request, urllib.error
from test_backend import FakeClient, FakeData, NOW
from app.service import Service
from app.server import WebServer


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = FakeClient()
        self.s = Service(
            state_dir=self.tmp.name, now=NOW, client=self.client, data=FakeData()
        )
        self.server = WebServer(("127.0.0.1", 0), self.s)
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
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(
        self, path, method="GET", body=None, extra=None, expected=200, schema=None
    ):
        headers = {
            "Origin": self.base,
            "Content-Type": "application/json",
            "X-CSRF-Token": next(c.value for c in self.jar if c.name == "csrf_token"),
            "Idempotency-Key": path + str(body),
        }
        headers.update(extra or {})
        r = urllib.request.Request(
            self.base + path,
            method=method,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            response = self.http.open(r)
        except urllib.error.HTTPError as ex:
            response = ex
        self.assertEqual(
            response.status,
            expected,
            response.read().decode() if response.status != expected else "",
        )
        data = json.loads(response.read())
        if schema:
            self.server.validators[schema].validate(data)
        return data

    def setup_owner(self):
        self.request(
            "/api/v1/operator/cycles",
            "POST",
            dict(scope="EXPLICIT_DATES", entity_ids=["A"], dates=["2026-12-24"]),
            schema="CycleResponse",
        )
        c = self.request("/api/v1/operator/cases", schema="CaseList")["items"][0]
        p = self.request("/api/v1/proposals/" + c["proposal_id"], schema="Proposal")
        m = self.request(
            "/api/v1/operator/messages",
            "POST",
            dict(
                entity_id="A", proposal_ids=[p["proposal_id"]], delivery_mode="PREVIEW"
            ),
            expected=201,
            schema="Message",
        )
        token = m["owner_entry_path"].split("token=")[1]
        self.request(
            "/api/v1/session", "POST", dict(token=token), schema="SessionResponse"
        )
        return p

    def test_channel_assets_are_scoped_to_the_static_allowlist(self):
        for path, mime in (("/whatsapp.js", "text/javascript"), ("/whatsapp.css", "text/css"), ("/channel-mockups.js", "text/javascript"), ("/channel-mockups.css", "text/css")):
            with self.http.open(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.headers["Content-Type"].startswith(mime))
                self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        for path in ("/private/internal.py", "/api/messages", "/api/reply"):
            self.request(path, expected=404)
        for view in ("whatsapp", "email", "sms"):
            with self.http.open(self.base + "/customer?view=" + view) as response:
                self.assertEqual(response.status, 200)
        self.request("/api/v1/businesses/A/contact-preferences", expected=401)

    def test_http_whole_journey_contracts(self):
        self.request("/api/v1/health", schema="Health")
        self.request("/api/v1/operator/businesses", schema="BusinessList")
        p = self.setup_owner()
        pid = p["proposal_id"]
        self.request(
            "/api/v1/proposals/" + pid + "/interpret",
            "POST",
            dict(text="yes", language="en"),
            schema="InterpretResponse",
        )
        self.assertEqual(len(self.client.puts), 0)
        result = self.request(
            "/api/v1/proposals/" + pid + "/decisions",
            "POST",
            dict(proposal_version=1, decision="APPROVE"),
            expected=202,
            schema="Result",
        )
        self.assertEqual(result["application_status"], "SUCCEEDED")
        self.request("/api/v1/proposals/" + pid + "/result", schema="Result")
        self.assertEqual(len(self.client.puts), 1)
        pref = self.request(
            "/api/v1/businesses/A/contact-preferences", schema="Preferences"
        )
        self.request(
            "/api/v1/businesses/A/contact-preferences",
            "PATCH",
            dict(version=pref["version"], frequency="MONTHLY"),
            schema="Preferences",
        )
        perm = self.request(
            "/api/v1/businesses/A/standing-permissions",
            "POST",
            dict(
                day_keys=["XMAS_EVE"],
                change_kind="DATE_HOURS",
                purpose="CORRECTION",
                expires_at="2027-01-01T00:00:00Z",
                confirmed=True,
            ),
            expected=201,
            schema="Permission",
        )
        self.request(
            "/api/v1/businesses/A/standing-permissions", schema="PermissionList"
        )
        self.request(
            "/api/v1/businesses/A/standing-permissions/" + perm["permission_id"],
            "DELETE",
            schema="Permission",
        )
        self.request("/api/v1/operator/messages", schema="MessageList")

    def test_AC14_operator_cannot_decide_without_owner(self):
        self.s.cycle(
            dict(scope="EXPLICIT_DATES", entity_ids=["A"], dates=["2026-12-24"])
        )
        pid = next(iter(self.s.store.data["proposals"]))
        self.request(
            "/api/v1/proposals/" + pid + "/decisions",
            "POST",
            dict(proposal_version=1, decision="APPROVE"),
            expected=401,
            schema="Error",
        )
        self.assertEqual(len(self.client.puts), 0)

    def test_AC14_origin_csrf_scope_and_get(self):
        p = self.setup_owner()
        self.request(
            "/api/v1/businesses/B/contact-preferences", expected=403, schema="Error"
        )
        self.request(
            "/api/v1/proposals/" + p["proposal_id"] + "/decisions",
            "POST",
            dict(proposal_version=1, decision="APPROVE"),
            extra={"Origin": "https://evil.invalid"},
            expected=403,
            schema="Error",
        )
        self.request(
            "/api/v1/proposals/" + p["proposal_id"] + "/decisions",
            "POST",
            dict(proposal_version=1, decision="APPROVE"),
            extra={"X-CSRF-Token": "wrong"},
            expected=403,
            schema="Error",
        )
        self.request("/api/v1/proposals/" + p["proposal_id"], schema="Proposal")
        self.assertEqual(len(self.client.puts), 0)

    def test_scope_extra_fields_rejected(self):
        p = self.setup_owner()
        self.request(
            "/api/v1/proposals/" + p["proposal_id"] + "/decisions",
            "POST",
            dict(proposal_version=1, decision="APPROVE", target_entity_id="B"),
            expected=422,
            schema="Error",
        )
        self.assertEqual(len(self.client.puts), 0)

    def test_bad_version_and_expired(self):
        p = self.setup_owner()
        self.request(
            "/api/v1/proposals/" + p["proposal_id"] + "/decisions",
            "POST",
            dict(proposal_version=99, decision="APPROVE"),
            expected=409,
            schema="Error",
        )
        self.s.proposal(p["proposal_id"])["expires_at"] = "2026-11-05T00:00:00Z"
        self.request(
            "/api/v1/proposals/" + p["proposal_id"] + "/decisions",
            "POST",
            dict(proposal_version=1, decision="APPROVE"),
            expected=410,
            schema="Error",
        )
        self.assertEqual(len(self.client.puts), 0)

    def test_health_requires_session(self):
        request = urllib.request.Request(self.base + "/api/v1/health")
        with self.assertRaises(urllib.error.HTTPError) as ex:
            urllib.request.urlopen(request)
        self.assertEqual(ex.exception.code, 401)
