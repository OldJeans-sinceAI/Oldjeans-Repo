"""Same-origin local HTTP API. No public-hosting authentication claim."""

from __future__ import annotations
import json
import secrets
import hmac
import re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie, CookieError
from urllib.parse import urlparse, parse_qs, unquote
from jsonschema import Draft202012Validator, FormatChecker
from .errors import AppError, digest, fingerprint
from .evaluate import export_text
from .fleet import FleetRunner
from .reset import ResetManager
from .domain import HoursError
from .storage import StateError
from contextlib import nullcontext


MAX_REQUEST_SIZE = 65536
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100


class WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, service, sandbox_service=None):
        self.service = service
        self.sandbox_service = sandbox_service
        self.fleet = FleetRunner(service)
        self.reset = ResetManager(service, self.fleet)
        self.sandbox_reset = ResetManager(sandbox_service) if sandbox_service else None
        self.contract = json.loads(
            (service.root / "config/openapi.json").read_text()
        )
        self.validators = {
            name: Draft202012Validator(
                {
                    "$ref": "#/components/schemas/" + name,
                    "components": self.contract["components"],
                },
                format_checker=FormatChecker(),
            )
            for name in self.contract["components"]["schemas"]
        }
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "ConnectSuggests"

    def log_message(self, *args):
        pass  # Tokens, bodies and credentials never enter access logs.

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_PATCH(self):
        self.handle_request("PATCH")

    def do_DELETE(self):
        self.handle_request("DELETE")

    def do_OPTIONS(self):
        self.reply(405, {"error": "Cross-origin API access is disabled."})

    def cookies(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except CookieError:
            return {}
        prefix = "sandbox_" if getattr(self, "workspace", "") else ""
        names = ("operator_session", "owner_session", "csrf_token")
        return {k: c[prefix + k].value for k in names if prefix + k in c}

    def _reply_error(
        self, status, code, message, retryable=False, details=None
    ):
        self.reply(
            status,
            {
                "error": {
                    "code": code,
                    "message": message,
                    "retryable": retryable,
                    "details": details or {},
                },
                "request_id": secrets.token_hex(8),
            },
        )

    def reply(
        self, status, data, headers=None, content_type="application/json; charset=utf-8"
    ):
        raw = (
            data
            if isinstance(data, bytes)
            else json.dumps(data, ensure_ascii=False).encode()
            if content_type.startswith("application/json")
            else str(data).encode()
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.send_header(
            "X-App-Time", getattr(self, "service", self.server.service).stamp()
        )
        for k, v in headers or []:
            if k == "Set-Cookie" and getattr(self, "workspace", ""):
                v = "sandbox_" + v.replace("Path=/;", "Path=/sandbox/;")
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def validate(self, name, b):
        errors = list(self.server.validators[name].iter_errors(b))
        if errors:
            raise AppError(
                422,
                "INVALID_REQUEST",
                "Request does not match " + name + ".",
                details={
                    "fields": [".".join(str(x) for x in e.path) for e in errors[:5]]
                },
            )

    def _query_int(self, q, key, default, min_val=None, max_val=None):
        raw = q.get(key, [str(default)])[0]
        try:
            val = int(raw)
        except (ValueError, TypeError):
            raise AppError(
                422, "INVALID_VALUE", f"Query parameter '{key}' must be an integer."
            )
        if min_val is not None:
            val = max(min_val, val)
        if max_val is not None:
            val = min(max_val, val)
        return val

    def _query_str(self, q, key, default=None):
        vals = q.get(key)
        return vals[0] if vals else default

    def handle_request(self, method):
        try:
            path = unquote(urlparse(self.path).path)
            sandbox = path == "/sandbox" or path.startswith("/sandbox/")
            manager = self.server.sandbox_reset if sandbox else self.server.reset
            with manager.mutations if method != "GET" and manager else nullcontext():
                self.dispatch(method)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except AppError as e:
            self._reply_error(e.status, e.code, e.message, e.retryable, e.details)
        except (HoursError, ValueError, KeyError, TypeError):
            self._reply_error(
                422, "INVALID_VALUE", "Invalid hours, date or request value."
            )
        except (StateError, OSError):
            self._reply_error(
                503,
                "STORAGE_UNAVAILABLE",
                "State could not be persisted. Do not assume the change succeeded.",
                True,
            )
        except Exception as e:
            print(f"Request failed: {type(e).__name__}: {e}", flush=True)
            self._reply_error(
                500, "INTERNAL_ERROR", "The request could not be completed."
            )

    def _parse_and_validate_body(self, method, path, host, cookies, s):
        if method == "GET":
            return None
        if path != "/internal/v1/detections":
            origin = self.headers.get("Origin")
            if origin not in ("http://" + host,):
                raise AppError(
                    403, "ORIGIN_REQUIRED", "A same-origin request is required."
                )
            if not cookies.get("csrf_token") or not hmac.compare_digest(
                cookies["csrf_token"], self.headers.get("X-CSRF-Token", "")
            ):
                raise AppError(
                    403, "CSRF_REQUIRED", "A valid request token is required."
                )
        size = int(self.headers.get("Content-Length", "0"))
        if size > MAX_REQUEST_SIZE:
            raise AppError(413, "REQUEST_TOO_LARGE", "Request is too large.")
        if size:
            if not self.headers.get("Content-Type", "").startswith(
                "application/json"
            ):
                raise AppError(415, "JSON_REQUIRED", "Use application/json.")
            try:
                b = json.loads(self.rfile.read(size))
            except json.JSONDecodeError as e:
                raise AppError(
                    400, "INVALID_JSON", f"Malformed JSON request body: {e.msg}"
                ) from e
        else:
            b = {}
        if s.reset_blocked and path != "/api/v1/operator/reset":
            raise AppError(
                503,
                "RESET_RECOVERY_REQUIRED",
                "Finish reset recovery before making changes.",
            )
        return b

    def _handle_static_files(self, method, path, cookies, s):
        if method != "GET":
            return False
        if path in ("/", "/customer", "/customer/"):
            headers = []
            if path == "/":
                token, csrf = s.operator_session()
                headers += [
                    (
                        "Set-Cookie",
                        f"operator_session={token}; Path=/; HttpOnly; SameSite=Strict",
                    ),
                    ("Set-Cookie", f"csrf_token={csrf}; Path=/; SameSite=Strict"),
                ]
            elif not cookies.get("csrf_token"):
                headers.append(
                    (
                        "Set-Cookie",
                        f"csrf_token={secrets.token_urlsafe(32)}; Path=/; SameSite=Strict",
                    )
                )
            self.reply(
                200,
                (s.root / "web/index.html").read_bytes(),
                headers,
                "text/html; charset=utf-8",
            )
            return True
        if path in ("/app.js", "/demo.js", "/whatsapp.js", "/styles.css", "/whatsapp.css", "/channel-mockups.js", "/channel-mockups.css", "/presentation.js", "/presentation.css"):
            self.reply(
                200,
                (s.root / "web" / path[1:]).read_bytes(),
                content_type="text/javascript; charset=utf-8"
                if path.endswith(".js")
                else "text/css; charset=utf-8",
            )
            return True
        if path == "/favicon.ico":
            self.reply(204, b"", content_type="image/x-icon")
            return True
        return False

    def dispatch(self, method):
        u = urlparse(self.path)
        path = unquote(u.path)
        self.workspace = (
            "/sandbox" if path == "/sandbox" or path.startswith("/sandbox/") else ""
        )
        self.service = self.server.service
        if self.workspace:
            if not self.server.sandbox_service:
                raise AppError(
                    503, "SANDBOX_NOT_CONFIGURED", "Sandbox workspace is not enabled."
                )
            self.service = self.server.sandbox_service
            path = path[len(self.workspace) :] or "/"
        s = self.service
        q = parse_qs(u.query)
        cookies = self.cookies()
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            raise AppError(
                403, "INVALID_HOST", "Only the local application origin is allowed."
            )
        b = self._parse_and_validate_body(method, path, host, cookies, s)

        if self._handle_static_files(method, path, cookies, s):
            return

        if path == "/internal/v1/detections" and method == "POST":
            if not hmac.compare_digest(
                self.headers.get("X-Internal-Key", ""), s.internal_secret
            ):
                raise AppError(
                    401,
                    "INTERNAL_AUTH_REQUIRED",
                    "Internal authentication is required.",
                )
            self.validate("Detection", b)
            return self.reply(201, s.ingest_detection(b))
        if path == "/api/v1/session" and method == "POST":
            self.validate("SessionRequest", b)
            result, token = s.exchange_token(b["token"])
            return self.reply(
                200,
                result,
                [
                    (
                        "Set-Cookie",
                        f"owner_session={token}; Path=/; HttpOnly; SameSite=Strict",
                    )
                ],
            )
        if path == "/api/v1/health" and method == "GET":
            s.authenticate(cookies, operator=True)
            return self.reply(
                200,
                {
                    **s.health(),
                    "sandbox_available": self.server.sandbox_service is not None,
                    "presentation_mode": bool(getattr(s, "presentation_mode", False)),
                },
            )
        if path.startswith("/api/v1/operator/"):
            return self._dispatch_operator(method, path, q, b, cookies, s)
        if path.startswith("/api/v1/proposals/"):
            return self._dispatch_proposals(method, path, b, cookies, s)
        if path.startswith("/api/v1/businesses/"):
            return self._dispatch_businesses(method, path, b, cookies, s)

        raise AppError(404, "NOT_FOUND", "Endpoint not found.")

    def _dispatch_operator(self, method, path, q, b, cookies, s):
        auth = s.authenticate(cookies, operator=True)
        if method != "GET" and not hmac.compare_digest(
            auth["csrf"], digest(cookies["csrf_token"])
        ):
            raise AppError(403, "CSRF_REQUIRED", "Session request token changed.")
        if path == "/api/v1/operator/reset":
            manager = (
                self.server.sandbox_reset if self.workspace else self.server.reset
            )
            if method == "GET":
                return self.reply(200, manager.preview())
            if method == "POST":
                self.validate("ResetRequest", b)
                return self.reply(
                    200, manager.execute(b, self.headers.get("Idempotency-Key"))
                )
        if path == "/api/v1/operator/sandbox-state" and method == "GET":
            if s.mode != "sandbox":
                raise AppError(409, "SANDBOX_ONLY", "Open the sandbox workspace.")
            entity = s._read(s.source_id)
            return self.reply(
                200,
                {
                    "source_entity_id": s.source_id,
                    "target_entity_id": s.target_id,
                    "target_name": entity.get("name", s.target_id),
                    "hours": entity.get("hours") or {},
                    "checked_at": s.stamp(),
                    "write_status": s.sandbox_write,
                    "writes_enabled": s.allow_writes,
                },
            )
        if path.startswith("/api/v1/operator/fleet-runs") and self.workspace:
            raise AppError(
                409, "MOCK_ONLY", "Bulk scans belong to the mock workspace."
            )
        if path == "/api/v1/operator/fleet-runs":
            if method == "GET":
                return self.reply(200, self.server.fleet.get())
            if method == "POST":
                self.validate("FleetRequest", b)
                return self.reply(202, self.server.fleet.start(b))
        fleet_match = re.fullmatch(
            r"/api/v1/operator/fleet-runs/([^/]+)(/contacts)?", path
        )
        if fleet_match:
            jid, contacts_subpath = fleet_match.groups()
            if method == "GET" and not contacts_subpath:
                return self.reply(200, self.server.fleet.get(jid))
            if method == "POST" and contacts_subpath:
                self.validate("FleetContactRequest", b)
                return self.reply(202, self.server.fleet.prepare_contacts(jid, b))
        if path.endswith("/businesses") and method == "GET":
            limit = self._query_int(q, "limit", DEFAULT_PAGE_LIMIT, min_val=1, max_val=MAX_PAGE_LIMIT)
            offset = self._query_int(q, "offset", 0, min_val=0)
            return self.reply(200, s.businesses(self._query_str(q, "q", ""), offset, limit))
        if path.endswith("/cycles") and method == "POST":
            self.validate("CycleRequest", b)
            return self.reply(200, s.cycle(b))
        if path.endswith("/cases") and method == "GET":
            return self.reply(
                200,
                s.cases(q.get("entity_id", [None])[0], q.get("action", [None])[0]),
            )
        if path.endswith("/messages"):
            if method == "GET":
                return self.reply(
                    200,
                    s.messages(
                        self._query_str(q, "entity_id"),
                        self._query_int(q, "offset", 0, min_val=0),
                        self._query_int(q, "limit", DEFAULT_PAGE_LIMIT, min_val=1, max_val=MAX_PAGE_LIMIT),
                        self._query_str(q, "delivery_mode"),
                    ),
                )
            if method == "POST":
                self.validate("MessageCreate", b)
                return self.reply(
                    201, self.mutate(s, path, b, lambda: s.create_message(b))
                )
        if path.endswith("/export.csv") and method == "GET":
            return self.reply(
                200,
                export_text(s.data, s.root),
                [
                    (
                        "Content-Disposition",
                        'attachment; filename="connect_predictions_2026.csv"',
                    )
                ],
                "text/csv; charset=utf-8",
            )
        match = re.fullmatch(r"/api/v1/operator/issues/([^/]+)/resolve", path)
        if match and method == "POST":
            self.validate("Resolution", b)
            return self.reply(
                200, self.mutate(s, path, b, lambda: s.resolve(match[1], b))
            )
        raise AppError(404, "NOT_FOUND", "Endpoint not found.")

    def _dispatch_proposals(self, method, path, b, cookies, s):
        match = re.fullmatch(
            r"/api/v1/proposals/([^/]+)(?:/(interpret|decisions|result))?", path
        )
        if not match:
            raise AppError(404, "NOT_FOUND", "Endpoint not found.")
        pid, op = match.groups()
        if method == "GET":
            try:
                if self.headers.get("X-Operator-View") == "1":
                    s.authenticate(cookies, operator=True)
                    session = None
                else:
                    session = s.authenticate(cookies, pid=pid)
            except AppError:
                if cookies.get("owner_session"):
                    raise
                # Operator inspection is read-only. Owner writes NEVER fall back to operator.
                s.authenticate(cookies, operator=True)
            if op is None:
                return self.reply(200, s.get_proposal(pid))
            if op == "result":
                s.get_proposal(pid)
                return self.reply(200, s.result(pid))
        elif method == "POST":
            session = s.authenticate(cookies, pid=pid)
            if op == "interpret":
                self.validate("InterpretRequest", b)
                return self.reply(
                    200,
                    s.interpret(pid, b, multiple=len(session["proposal_ids"]) > 1),
                )
            if op == "decisions":
                self.validate("DecisionRequest", b)
                result = s.decide(pid, b, self.headers.get("Idempotency-Key"))
                return self.reply(200 if b["decision"] == "REJECT" else 202, result)
        raise AppError(404, "NOT_FOUND", "Endpoint not found.")

    def _dispatch_businesses(self, method, path, b, cookies, s):
        match = re.fullmatch(
            r"/api/v1/businesses/([^/]+)/(contact-preferences|standing-permissions)(?:/([^/]+))?",
            path,
        )
        if not match:
            raise AppError(404, "NOT_FOUND", "Endpoint not found.")
        eid, kind, permission = match.groups()
        s.authenticate(cookies, eid=eid)
        if kind == "contact-preferences":
            if method == "GET":
                return self.reply(200, s.preferences(eid))
            if method == "PATCH":
                self.validate("PreferenceUpdate", b)
                return self.reply(
                    200,
                    self.mutate(s, path, b, lambda: s.update_preferences(eid, b)),
                )
        if kind == "standing-permissions":
            if method == "GET" and not permission:
                return self.reply(200, s.permissions(eid))
            if method == "POST" and not permission:
                self.validate("PermissionCreate", b)
                return self.reply(
                    201,
                    self.mutate(s, path, b, lambda: s.create_permission(eid, b)),
                )
            if method == "DELETE" and permission:
                return self.reply(
                    200,
                    self.mutate(
                        s, path, {}, lambda: s.revoke_permission(eid, permission)
                    ),
                )
        raise AppError(404, "NOT_FOUND", "Endpoint not found.")

    def mutate(self, s, path, body, fn):
        key = self.headers.get("Idempotency-Key")
        request = {"path": path, "method": self.command, "body": body}
        with s.lock:
            old = s._idempotent(key, request)
            if old is not None:
                return old
            result = fn()
            # Responses carrying raw capabilities are not persisted. Mint a fresh one on replay.
            saved = {k: v for k, v in result.items() if k != "owner_entry_path"}
            s.store.data["idempotency"][key] = {
                "hash": fingerprint(request),
                "result": saved,
            }
            s.store.save()
            return result
