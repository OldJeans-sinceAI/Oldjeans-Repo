"""Shared test helpers. Standard library only (pytest is optional: tests are unittest.TestCase
classes, which pytest collects natively and `python -m unittest` also runs).

Nothing here touches mock_api/state.json: the mock server is started in-process with a temp STATE_FILE.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for sub in ("mock_api", "examples", "evaluation"):
    p = os.path.join(ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("MOCK_QUIET", "1")

import warnings  # noqa: E402
warnings.simplefilter("ignore", ResourceWarning)  # app code leaves files open; not what we test
warnings.simplefilter("ignore", DeprecationWarning)

DEMO_FI = "FI-D0001"          # Kahvila Aurora (Fonecta's own example)
XMAS_EVE = "2026-12-24"


# --------------------------------------------------------------------------- tagging
def integration(obj):
    """Tag a test (class or function) as @integration.

    Skipped unless RUN_INTEGRATION=1. Under pytest it also carries `pytest.mark.integration`,
    so CI can deselect it with:  pytest -m "not integration"
    """
    obj = unittest.skipUnless(os.environ.get("RUN_INTEGRATION") == "1",
                              "@integration: set RUN_INTEGRATION=1 (+ YEXT_* env) to hit the real Yext sandbox")(obj)
    try:
        import pytest  # noqa: WPS433
        obj = pytest.mark.integration(obj)
    except ImportError:
        pass
    return obj


# --------------------------------------------------------------------------- http helper
def http(method, url, params=None, body=None, raw_body=None, headers=None):
    """Return (status, parsed_json_or_text). Never raises on HTTP error codes."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else None)
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            status, txt = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        status, txt = e.code, e.read().decode()
    try:
        return status, json.loads(txt)
    except json.JSONDecodeError:
        return status, txt


# --------------------------------------------------------------------------- in-process mock Yext
class MockApi:
    """One shared in-process instance of mock_api/server.py (Store load is slow, so start it once)."""
    _inst = None

    @classmethod
    def get(cls) -> "MockApi":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        import server  # mock_api/server.py
        self.server = server
        self.tmp = tempfile.mkdtemp(prefix="mock-state-")
        server.STATE_FILE = os.path.join(self.tmp, "state.json")  # never touch mock_api/state.json
        server.STORE = server.Store()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def store(self):
        return self.server.STORE

    def reset(self):
        return http("POST", self.base + "/mock/reset", body={})

    def call(self, method, path, params=None, body=None, raw_body=None, key="demo", v="20261106", headers=None):
        q = {}
        if key is not None:
            q["api_key"] = key
        if v is not None:
            q["v"] = v
        q.update(params or {})
        return http(method, self.base + path, q, body, raw_body, headers)

    def entity(self, eid):
        return self.call("GET", f"/v2/accounts/me/entities/{eid}")


class MockTestCase(unittest.TestCase):
    """Base class: fresh mock state for every test."""

    @classmethod
    def setUpClass(cls):
        cls.api = MockApi.get()

    def setUp(self):
        self.api.reset()

    @property
    def base(self):
        return self.api.base


# --------------------------------------------------------------------------- scripted stub server
class StubServer:
    """Tiny HTTP server that replays a scripted list of (status, body, headers) responses.

    Used to simulate Yext failures the mock cannot produce (429, 5xx, garbage bodies).
    The last scripted response repeats. `requests` records (method, path, headers, body).
    """

    def __init__(self, script):
        self.script, self.requests, self._i = list(script), [], 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _do(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n).decode() if n else ""
                outer.requests.append((self.command, self.path, dict(self.headers), body))
                status, payload, hdrs = outer.script[min(outer._i, len(outer.script) - 1)]
                outer._i += 1
                raw = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
                raw = raw.encode() if isinstance(raw, str) else raw
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                for k, v in (hdrs or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_PUT = do_POST = _do

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()


def yext_error(code, message, status=None):
    return {"meta": {"uuid": "stub", "errors": [{"code": code, "type": "FATAL_ERROR", "message": message}]},
            "response": {}}


def full_week(spec="mo-su 09:00-17:00"):
    from hours import parse_week, week_to_yext
    return week_to_yext(parse_week(spec))
