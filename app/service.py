"""Application orchestration. Fixed Yext schema; local state is kept separately."""

from __future__ import annotations
import copy, hashlib, json, os, secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from . import POLICY
from .errors import (
    AppError,
    check_idempotency_key,
    digest,
    fingerprint,
    MAX_IDEMPOTENCY_KEY_LENGTH,
)
from .domain import (
    DataStore,
    evaluate_context,
    parse_dt,
    iso_utc,
    local_date,
    local_midnight_utc,
    compute_next_contact_at,
    detection_horizon,
    validate_change,
    merge_change_into_hours,
    read_back_value,
    change_target_value,
    relevant_state_hash,
    canonical_hours,
    day_to_hours_string,
    parse_intervals,
    DAYS,
    MINUTES_PER_DAY,
    _get_timezone,
    dispatch_datetime,
    is_proposal_active,
)

DEFAULT_YEXT_API_VERSION = "20261106"
DEFAULT_TIMEZONE = "Europe/Helsinki"
DEFAULT_CONTACT_WINDOW = "10-12"
DEFAULT_FREQUENCY = "TWICE_MONTHLY"
PROPOSAL_TTL_DAYS = 14
PERMISSION_MAX_TTL_DAYS = 365
SANDBOX_HOST_DOMAIN = "sbx-api.yextapis.com"
from .storage import StateStore
from .replies import OwnerReplies
from examples.yext_client import YextClient


def effective(hours, day):
    hours = hours or {}
    d = date.fromisoformat(day)
    if hours.get("reopenDate") and day < hours["reopenDate"]:
        return "closed"
    for row in hours.get("holidayHours", []):
        if row.get("date") == day:
            if row.get("isRegularHours"):
                break
            return canonical_hours(day_to_hours_string(row))
    row = hours.get(DAYS[d.weekday()])
    if not row:
        return "not_registered"
    return canonical_hours(day_to_hours_string(row))


def scope_value(hours, change):
    return (
        effective(hours, change["date"])
        if change["kind"] == "DATE_HOURS"
        else read_back_value(hours, change)
    )


def clean_proposal(p):
    return {k: copy.deepcopy(v) for k, v in p.items() if not k.startswith("_")}


class Service:
    def __init__(
        self,
        root=None,
        state_dir=None,
        mode="mock",
        now=None,
        client=None,
        data=None,
        source_id=None,
        target_id=None,
        allow_writes=None,
    ):
        self.root = Path(root or Path(__file__).resolve().parents[1])
        self.mode = mode
        self.replies = OwnerReplies()
        self.fixed_now = parse_dt(now) if isinstance(now, str) else now
        self.data = data or DataStore(
            os.environ.get("DATA_ROOT", str(self.root / "data")),
            iso_utc(self.fixed_now or datetime.now(timezone.utc)),
        )
        self.state_dir = Path(
            state_dir or os.environ.get("STATE_DIR", str(self.root / "runtime"))
        )
        self.store = StateStore(str(self.state_dir / "state.json"))
        self.auth = StateStore(str(self.state_dir / "auth.json"))
        self.lock = self.store.lock
        self.reset_blocked = False
        self.client = client or YextClient(
            v=os.environ.get("YEXT_API_VERSION", DEFAULT_YEXT_API_VERSION)
        )
        self.source_id = source_id or os.getenv("SANDBOX_SOURCE_ENTITY_ID", "")
        self.target_id = target_id or os.getenv("YEXT_ENTITY_ID", "")
        self.allow_writes = (
            allow_writes
            if allow_writes is not None
            else os.getenv("ALLOW_SANDBOX_WRITES", "").lower() == "true"
        )
        self.internal_secret = os.getenv(
            "APP_INTERNAL_SECRET"
        ) or secrets.token_urlsafe(32)
        self.sandbox_read = "NOT_APPLICABLE" if mode == "mock" else "UNTESTED"
        self.sandbox_write = "NOT_APPLICABLE" if mode == "mock" else "UNTESTED"
        self.target_name = None
        if mode == "sandbox":
            if not self.source_id or not self.target_id:
                raise AppError(
                    503,
                    "SANDBOX_MAPPING_REQUIRED",
                    "Configure source and target entity IDs.",
                )

            if (
                client is None
                and urlparse(self.client.base).hostname != SANDBOX_HOST_DOMAIN
            ):
                raise AppError(
                    503,
                    "SANDBOX_HOST_REQUIRED",
                    "Only the Yext sandbox host is allowed.",
                )
            try:
                target = self.client.get_entity(self.target_id)
                self.target_name = target.get("name", self.target_id)
                self.sandbox_read = "PASS"
                successful = [
                    op
                    for op in self.store.data["operations"].values()
                    if op["status"] == "SUCCEEDED"
                    and (self.store.get("proposals", op["proposal_id"]) or {})
                    .get("_result", {})
                    .get("target_entity_id")
                    == self.target_id
                ]
                if successful and read_back_value(
                    target.get("hours") or {}, successful[-1]["change"]
                ) == change_target_value(successful[-1]["change"]):
                    self.sandbox_write = "VERIFIED"
            except Exception:
                raise AppError(
                    503,
                    "SANDBOX_READ_FAILED",
                    "Cannot read configured sandbox entity; no mock fallback.",
                ) from None
        self.source_error = False
        self._source_version = self._source_signature()
        self._import_mock_permissions()

    def _source_signature(self):
        if not isinstance(self.data, DataStore):
            return None
        return tuple(
            sorted(
                (p.name, p.stat().st_mtime_ns, p.stat().st_size)
                for p in Path(self.data.root).iterdir()
                if p.is_file()
            )
        )

    def _refresh_sources(self):
        version = self._source_signature()
        if version is None or version == self._source_version:
            return False
        try:
            refreshed = DataStore(self.data.root, self.stamp())
        except Exception:
            self.source_error = True
            raise AppError(
                503, "SOURCE_UNAVAILABLE", "Updated source data could not be validated."
            ) from None
        self.data = refreshed
        self._source_version = version
        self.source_error = False
        return True

    def now(self):
        return self.fixed_now or datetime.now(timezone.utc)

    def stamp(self):
        return iso_utc(self.now())

    def health(self):
        return dict(
            status="NOT_READY"
            if self.source_error
            else "DEGRADED"
            if getattr(self.data, "unavailable", [])
            else "READY",
            mode=self.mode,
            schema_version=1,
            policy_version=POLICY["version"],
            data_ready=not self.source_error,
            sandbox_read=self.sandbox_read,
            sandbox_write=self.sandbox_write,
            clock_mode="SIMULATED" if self.fixed_now else "REAL",
            reply_interpreter=self.replies.health(),
        )

    def _entity(self, eid):
        e = self.data.entity(eid)
        if not e:
            raise AppError(404, "BUSINESS_NOT_FOUND", "Business not found.")
        return e

    def _timezone(self, eid):
        return self._entity(eid).get("timezone", DEFAULT_TIMEZONE)

    def target(self, eid):
        if self.mode == "sandbox":
            if eid != self.source_id:
                raise AppError(
                    422,
                    "UNMAPPED_BUSINESS",
                    "Only the configured business may write to this sandbox entity.",
                )
            return self.target_id
        return eid

    def _read(self, eid):
        try:
            return self.client.get_entity(self.target(eid))
        except AppError:
            raise
        except Exception:
            raise AppError(
                503,
                "YEXT_UNAVAILABLE",
                "Yext read failed. No changes were confirmed.",
                True,
            ) from None

    def _import_mock_permissions(self):
        if self.mode != "mock":
            return
        with self.lock:
            changed = False
            for eid, c in self.data.contacts.items():
                if str(c.get("standing_permission_holidays")) != "1":
                    continue
                pid = "synthetic-" + eid
                if pid not in self.store.data["permissions"]:
                    e = self.data.entity(eid)
                    if not e:
                        continue
                    keys = sorted(
                        {
                            r["day_key"]
                            for r in self.data.calendar
                            if r["country"] == e["meta"]["countryCode"]
                            and r["day_type"] == "PUBLIC_HOLIDAY"
                        }
                    )
                    self.store.data["permissions"][pid] = dict(
                        permission_id=pid,
                        entity_id=eid,
                        day_keys=keys,
                        change_kind="DATE_HOURS",
                        purpose="CORRECTION",
                        expires_at=iso_utc(self.now() + timedelta(days=365)),
                        status="ACTIVE",
                        mode="mock",
                        source="SYNTHETIC_CONTACTS",
                        created_at=self.stamp(),
                    )
                    changed = True
            if changed:
                self.store.save()

    def businesses(self, q="", offset=0, limit=50):
        items = []
        for eid in self.data.order:
            if self.mode == "sandbox" and eid != self.source_id:
                continue
            if eid not in self.data.contacts:
                continue
            e = self.data.entities[eid]
            if q.lower() not in (eid + " " + e.get("name", "")).lower():
                continue
            c = self.data.contact(eid)
            has = bool(
                getattr(self.data, "history_entities", set())
                and eid in self.data.history_entities
            )
            if not hasattr(self.data, "history_entities"):
                has = any(k[0] == eid for k in self.data.holiday)
            items.append(
                dict(
                    entity_id=eid,
                    business_name=e.get("name", eid),
                    country=e["meta"]["countryCode"],
                    timezone=self._timezone(eid),
                    segment=e.get("c_segment", ""),
                    profile="DIRECT"
                    if has
                    else (
                        "PARTIAL" if e.get("c_shoppingCenterEntityId") else "LIMITED"
                    ),
                    preferred_channel=c.get("preferred_channel", "EMAIL"),
                    preferred_language=c.get("preferred_language", "en"),
                    source_opted_out=c.get("opted_out_of_suggestions") == "1",
                )
            )
        return dict(
            items=items[offset : offset + limit],
            total=len(items),
            offset=offset,
            limit=limit,
        )

    def preferences(self, eid):
        e = self._entity(eid)
        c = self.data.contact(eid)
        saved = self.store.data["preferences"].get(eid, {})
        freq = saved.get("frequency", DEFAULT_FREQUENCY)
        opt = c.get("opted_out_of_suggestions") == "1"
        return dict(
            entity_id=eid,
            version=saved.get("version", 1),
            frequency=freq,
            source=saved.get("source", "DEFAULT"),
            preferred_channel=c.get("preferred_channel", "EMAIL"),
            preferred_language=c.get("preferred_language", "en"),
            best_contact_window=c.get("best_contact_window", DEFAULT_CONTACT_WINDOW),
            source_opted_out=opt,
            next_contact_at=None
            if opt
            else compute_next_contact_at(
                self.now(),
                self._timezone(eid),
                c.get("best_contact_window", DEFAULT_CONTACT_WINDOW),
                freq,
            ),
            updated_at=saved.get("updated_at", self.stamp()),
        )

    def update_preferences(self, eid, body):
        with self.lock:
            p = self.preferences(eid)
            if body["version"] != p["version"]:
                raise AppError(409, "STALE_VERSION", "Contact preferences changed.")
            p.update(
                version=p["version"] + 1,
                frequency=body["frequency"],
                source="OWNER_SELECTED",
                updated_at=self.stamp(),
            )
            self.store.data["preferences"][eid] = p
            for m in self.store.data["messages"].values():
                if m["entity_id"] == eid and m["status"] == "QUEUED":
                    if p["frequency"] == "PAUSED":
                        m.update(status="BLOCKED_PAUSED", scheduled_at=None)
                    else:
                        m["scheduled_at"] = self.preferences(eid)["next_contact_at"]
            self.store.save()
            return self.preferences(eid)

    def permissions(self, eid):
        return {
            "items": [
                copy.deepcopy(p)
                for p in self.store.data["permissions"].values()
                if p["entity_id"] == eid
            ]
        }

    def create_permission(self, eid, b):
        exp = parse_dt(b["expires_at"])
        if not self.now() < exp <= self.now() + timedelta(days=PERMISSION_MAX_TTL_DAYS):
            raise AppError(
                422, "INVALID_EXPIRY", "Permission must expire within 365 days."
            )
        e = self._entity(eid)
        allowed = {
            r["day_key"]
            for r in self.data.calendar
            if r["country"] == e["meta"]["countryCode"]
        }
        if not set(b["day_keys"]) <= allowed:
            raise AppError(
                422, "UNKNOWN_DAY_KEY", "Permission must name known holidays."
            )
        with self.lock:
            pid = self.store.next_id("permission")
            p = dict(
                permission_id=pid,
                entity_id=eid,
                day_keys=b["day_keys"],
                change_kind="DATE_HOURS",
                purpose="CORRECTION",
                expires_at=b["expires_at"],
                status="ACTIVE",
                mode=self.mode,
                source="OWNER",
                created_at=self.stamp(),
            )
            self.store.put("permissions", pid, p)
            self.store.save()
            return copy.deepcopy(p)

    def revoke_permission(self, eid, pid):
        with self.lock:
            p = self.store.get("permissions", pid)
            if not p or p["entity_id"] != eid:
                raise AppError(404, "PERMISSION_NOT_FOUND", "Permission not found.")
            p["status"] = "REVOKED"
            self.store.save()
            return copy.deepcopy(p)

    def matching_permission(self, p):
        pref = self.preferences(p["entity_id"])
        if (
            pref["source_opted_out"]
            or pref["frequency"] == "PAUSED"
            or p["change"]["kind"] != "DATE_HOURS"
            or p["purpose"] != "CORRECTION"
        ):
            return None
        return next(
            (
                x
                for x in self.store.data["permissions"].values()
                if x["entity_id"] == p["entity_id"]
                and x["mode"] == self.mode
                and x["status"] == "ACTIVE"
                and parse_dt(x["expires_at"]) > self.now()
                and p["day_key"] in x["day_keys"]
                and (self.mode == "mock" or x["source"] == "OWNER")
            ),
            None,
        )

    def _feedback(self, eid, day, key):
        rows = []
        for p in self.store.data["proposals"].values():
            r = p.get("_result", {})
            if (
                p["entity_id"] == eid
                and p["day_key"] == key
                and p["decision_status"] in ("APPROVED", "EDITED")
                and r.get("final_change", {}).get("kind") == "DATE_HOURS"
            ):
                if r["final_change"]["date"] <= day:
                    rows.append(p)
        return max(rows, key=lambda p: p.get("_decided_at", ""), default=None)

    def _context(self, eid, target_date, live=None):
        e = self._entity(eid)
        cal = self.data.cal_by_date.get((e["meta"]["countryCode"], target_date), {})
        ctx = self.data.context(
            eid, target_date, cal.get("day_key", "REGULAR"), cal.get("day_type", "REGULAR")
        )
        if live is not None:
            ctx.displayed_hours = effective(live.get("hours", {}), target_date)
            ctx.already_closed = bool(live.get("closed"))
        feedback = self._feedback(eid, target_date, ctx.day_key)
        if feedback:
            ch = feedback["_result"]["final_change"]
            record = dict(
                hours=ch["hours"],
                source_record=feedback["proposal_id"],
                known_at=feedback["_decided_at"],
            )
            if ch["date"] == target_date:
                ctx.feedback = record
                if ctx.owner_confirmation and parse_dt(record["known_at"]) > parse_dt(
                    ctx.owner_confirmation["known_at"]
                ):
                    ctx.owner_confirmation = None
            elif self._same_weekly_baseline(feedback, live):
                ctx.own_history.append(
                    dict(
                        date=ch["date"],
                        hours=ch["hours"],
                        entered_at=feedback["_decided_at"],
                        source_record="runtime:" + feedback["proposal_id"],
                    )
                )
        return ctx

    def _same_weekly_baseline(self, p, live):
        return not live or p.get("_weekly_hash") == fingerprint(
            {d: live.get("hours", {}).get(d) for d in DAYS}
        )

    def cycle(self, b, *, apply_permissions=True, live_entities=None):
        with self.lock:
            self._refresh_sources()
            cycle_id = self.store.next_id("cycle")
            if b.get("now"):
                if not self.fixed_now:
                    raise AppError(
                        422,
                        "CLOCK_OVERRIDE_DISABLED",
                        "Clock injection is available only in simulated mode.",
                    )
                self.fixed_now = parse_dt(b["now"])
            ids = b.get("entity_ids") or list(self.data.contacts)
            cases = []
            counts = {"SUGGEST": 0, "FLAG": 0, "NO_ACTION": 0}
            for eid in ids:
                e = self._entity(eid)
                if self.mode == "sandbox" and eid != self.source_id:
                    continue
                live = (
                    copy.deepcopy(live_entities[eid])
                    if live_entities is not None
                    else self._read(eid)
                )
                if b["scope"] == "EXPLICIT_DATES":
                    dates = b["dates"]
                else:
                    today = local_date(self.now(), e.get("timezone", "Europe/Helsinki"))
                    end = detection_horizon(today, self.preferences(eid)["frequency"])
                    dates = sorted(
                        {
                            r["date"]
                            for r in self.data.calendar
                            if r["country"] == e["meta"]["countryCode"]
                            and str(today) <= r["date"] <= str(end)
                        }
                        | {str(today)}
                    )
                for target in dates:
                    ctx = self._context(eid, target, live)
                    out = evaluate_context(ctx, self.now())
                    c = self._persist_case(out, live)
                    cases.append(c["case_id"])
                    counts[c["action"]] += 1
            watched = self.store.data.setdefault("watchlist", {})
            for eid in ids:
                watched[eid] = str(
                    local_date(
                        self.now(), self._entity(eid).get("timezone", "Europe/Helsinki")
                    )
                )
            self.store.save()
            for cid in cases:
                c = self.store.get("cases", cid)
                p = self.store.get("proposals", c.get("proposal_id", ""))
                if (
                    apply_permissions
                    and p
                    and is_proposal_active(p, self.now())
                    and self.matching_permission(p)
                ):
                    permission = self.matching_permission(p)
                    self.decide(
                        p["proposal_id"],
                        {"proposal_version": p["version"], "decision": "APPROVE"},
                        "auto-" + p["proposal_id"] + "-" + str(p["version"]),
                        standing=permission["permission_id"],
                    )
            return dict(
                cycle_id=cycle_id,
                case_ids=cases,
                counts=counts,
                completed_at=self.stamp(),
            )

    def _persist_case(self, out, live):
        d = out["detection"]
        eid = d["entity_id"]
        day = d["target_date"]
        caseid = "case-" + fingerprint([eid, day])[:20]
        detid = "det-" + fingerprint([eid, day, d["evidence"], d["baseline"]])[:20]
        d["detection_id"] = detid
        self.store.put("detections", detid, d)
        c = dict(
            case_id=caseid,
            detection_id=detid,
            entity_id=eid,
            business_name=self._entity(eid).get("name", eid),
            target_date=day,
            action=out["action"],
            reason_code=out["reason_code"],
            summary=out["summary"],
            status=out["status"],
            priority=d["priority"],
            evidence=d["evidence"],
            gaps=d["gaps"],
            affected_dates=[day],
        )
        if out.get("recheck"):
            c["recheck_trigger"] = out["recheck"]
        oldcase = self.store.get("cases", caseid)
        old = self.store.get("proposals", (oldcase or {}).get("proposal_id", ""))
        signature = fingerprint([out["change"], d["evidence"], d["baseline"]])
        if out["action"] == "SUGGEST":
            if (
                old
                and old["decision_status"] == "REJECTED"
                and old.get("_fingerprint") == signature
            ):
                c.update(
                    action="NO_ACTION",
                    status="DEFER",
                    reason_code="OWNER_REJECTED_UNCHANGED",
                    summary="Owner rejected this unchanged proposal; wait for new evidence.",
                    recheck_trigger="New evidence or explicit owner request.",
                )
            elif (
                old
                and old["decision_status"]
                in ("APPROVED", "EDITED", "STANDING_AUTHORIZED")
                and old.get("_result", {}).get("final_change") == out["change"]
            ):
                c["proposal_id"] = old["proposal_id"]
            elif (
                old
                and old.get("_fingerprint") == signature
                and old["decision_status"] not in ("SUPERSEDED", "EXPIRED")
            ):
                c["proposal_id"] = old["proposal_id"]
            else:
                if old and old["decision_status"] == "PENDING":
                    old["decision_status"] = "SUPERSEDED"
                pid = self.store.next_id("proposal")
                tz = d["timezone"]
                end = min(
                    self.now() + timedelta(days=PROPOSAL_TTL_DAYS),
                    local_midnight_utc(date.fromisoformat(day), tz),
                )
                baseline = copy.deepcopy(d["baseline"])
                target_hours = live.get("hours") or {}
                if self.mode == "sandbox" and baseline["kind"] == "DATE_HOURS":
                    baseline["hours"] = effective(target_hours, day)
                p = dict(
                    schema_version=1,
                    proposal_id=pid,
                    version=(old["version"] + 1 if old else 1),
                    case_id=caseid,
                    entity_id=eid,
                    business_name=self._entity(eid).get("name", eid),
                    timezone=tz,
                    day_key=d["day_key"],
                    action="SUGGEST",
                    purpose=out.get("purpose", "CORRECTION"),
                    baseline=baseline,
                    change=out["change"],
                    baseline_hash=relevant_state_hash(
                        scope_value(target_hours, out["change"])
                    ),
                    reason_code=out["reason_code"],
                    reason=out["summary"],
                    evidence=d["evidence"],
                    confidence=out.get("confidence", "MEDIUM"),
                    priority=d["priority"],
                    created_at=self.stamp(),
                    expires_at=iso_utc(end),
                    decision_status="PENDING",
                    allowed_decisions=["APPROVE", "EDIT", "REJECT"],
                    mode=self.mode,
                    _fingerprint=signature,
                    _weekly_hash=fingerprint({wd: target_hours.get(wd) for wd in DAYS}),
                )
                if self.mode == "sandbox":
                    p["target_entity_id"] = self.target_id
                    p["target_business_name"] = self.target_name or self.target_id
                if end <= self.now():
                    p["decision_status"] = "EXPIRED"
                    p["allowed_decisions"] = []
                self.store.put("proposals", pid, p)
                c["proposal_id"] = pid
        if c["action"] == "FLAG":
            issue = "issue-" + fingerprint([eid, c["reason_code"]])[:20]
            c["issue_id"] = issue
            prior = self.store.get("issues", issue) or dict(
                issue_id=issue,
                entity_id=eid,
                reason_code=c["reason_code"],
                status="OPEN",
                affected_dates=[],
            )
            prior["affected_dates"] = sorted(set(prior["affected_dates"] + [day]))
            c["affected_dates"] = prior["affected_dates"]
            self.store.put("issues", issue, prior)
            for existing in self.store.data["cases"].values():
                if existing.get("issue_id") == issue:
                    existing["affected_dates"] = prior["affected_dates"]
        self.store.put("cases", caseid, c)
        return copy.deepcopy(c)

    def _evaluate_direct_schedule_detection(self, d, live):
        direct = [
            x
            for x in d["evidence"]
            if x["role"] == "DIRECT"
            and x["source_file"] == "regular_hours_history.jsonl"
            and parse_dt(x["known_at"]) <= self.now()
        ]
        rows = [
            r
            for r in self.data.regular.get(d["entity_id"], [])
            if any(r["effective_from"] in x["source_record"] for x in direct)
        ]
        if not rows:
            raise AppError(
                422,
                "DIRECT_SOURCE_REQUIRED",
                "A matching own schedule record is required for this change.",
            )
        row = max(rows, key=lambda r: r["effective_from"])
        baseline = copy.deepcopy(d["baseline"])
        if baseline["kind"] == "WEEKLY_HOURS":
            change = dict(
                kind="WEEKLY_HOURS",
                effective_from=baseline["effective_from"],
                weekdays={
                    wd: day_to_hours_string(row["hours"].get(wd))
                    for wd in baseline["weekdays"]
                },
            )
            baseline["weekdays"] = {
                wd: day_to_hours_string(live.get("hours", {}).get(wd))
                for wd in baseline["weekdays"]
            }
        else:
            if not row["hours"].get("reopenDate"):
                raise AppError(
                    422,
                    "REOPEN_SOURCE_REQUIRED",
                    "Source must specify an exact reopening date.",
                )
            change = dict(
                kind="REOPEN_DATE", reopen_date=row["hours"]["reopenDate"]
            )
        validate_change(change)
        det = copy.deepcopy(d)
        det["baseline"] = baseline
        return dict(
            action="SUGGEST",
            status="PROPOSAL_READY",
            reason_code="DIRECT_SCHEDULE",
            summary="Own confirmed schedule supports this scoped change.",
            detection=det,
            change=change,
            confidence="HIGH",
            purpose="CORRECTION",
            recheck=None,
        )

    def ingest_detection(self, d):
        self._refresh_sources()
        # Internal callers provide structured evidence, never a client-chosen destination.
        e = self._entity(d["entity_id"])
        if d["timezone"] != e.get("timezone", "Europe/Helsinki"):
            raise AppError(
                422, "WRONG_TIMEZONE", "Detection timezone differs from business."
            )
        live = self._read(d["entity_id"])
        ctx = self._context(d["entity_id"], d["target_date"], live)
        out = evaluate_context(ctx, self.now())
        if d["baseline"]["kind"] in ("WEEKLY_HOURS", "REOPEN_DATE"):
            out = self._evaluate_direct_schedule_detection(d, live)
        elif (
            d["finding"] == "STATUS_CONCERN"
            and len([x for x in d["evidence"] if x["role"] == "COUNTER"]) >= 2
        ):
            ctx.closure_signals = [
                dict(
                    source_file=x["source_file"],
                    source_record=x["source_record"],
                    summary=x["summary"],
                    known_at=x["known_at"],
                )
                for x in d["evidence"]
                if x["role"] == "COUNTER"
            ]
            out = evaluate_context(ctx, self.now())
        with self.lock:
            c = self._persist_case(out, live)
            self.store.save()
            return c

    def cases(self, entity_id=None, action=None):
        return {
            "items": [
                copy.deepcopy(c)
                for c in self.store.data["cases"].values()
                if (not entity_id or c["entity_id"] == entity_id)
                and (not action or c["action"] == action)
            ]
        }

    def proposal(self, pid):
        p = self.store.get("proposals", pid)
        if not p:
            raise AppError(404, "PROPOSAL_NOT_FOUND", "Proposal not found.")
        return p

    def get_proposal(self, pid):
        p = self.proposal(pid)
        if p["decision_status"] == "PENDING" and self.now() >= parse_dt(
            p["expires_at"]
        ):
            with self.lock:
                p["decision_status"] = "EXPIRED"
                p["allowed_decisions"] = []
                self.store.save()
        return clean_proposal(p)

    def result(self, pid):
        p = self.proposal(pid)
        r = copy.deepcopy(
            p.get("_result")
            or dict(
                proposal_id=pid,
                proposal_version=p["version"],
                decision_status=p["decision_status"],
                application_status="NOT_STARTED",
                mode=self.mode,
                source_entity_id=p["entity_id"],
                publishers=[],
            )
        )
        r["decision_status"] = p["decision_status"]
        return r

    def _idempotent(self, key, body):
        check_idempotency_key(key)
        old = self.store.data["idempotency"].get(key)
        if old and old["hash"] != fingerprint(body):
            raise AppError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "This key was used for a different request.",
            )
        return (
            self.result(old["proposal_id"])
            if old and old.get("proposal_id")
            else copy.deepcopy(old.get("result"))
            if old
            else None
        )

    def decide(self, pid, b, key, standing=None):
        with self.lock:
            self._refresh_sources()
            body = {"proposal_id": pid, **b}
            old = self._idempotent(key, body)
            if old:
                return old
            p = self.proposal(pid)
            if self.mode == "sandbox" and p.get("target_entity_id") != self.target_id:
                raise AppError(
                    409,
                    "SANDBOX_TARGET_CHANGED",
                    "The sandbox target changed; create a fresh proposal.",
                )
            if (
                b["proposal_version"] != p["version"]
                or p["decision_status"] == "SUPERSEDED"
            ):
                raise AppError(409, "STALE_VERSION", "Proposal version changed.")
            if p["decision_status"] == "EXPIRED" or self.now() >= parse_dt(
                p["expires_at"]
            ):
                raise AppError(410, "PROPOSAL_EXPIRED", "Proposal expired.")
            if p["decision_status"] != "PENDING":
                raise AppError(
                    409, "ALREADY_DECIDED", "This proposal already has a decision."
                )
            decision = b["decision"]
            change = copy.deepcopy(b.get("edited_change", p["change"]))
            self._validate_decision_change(p, change)
            if decision != "REJECT":
                self._validate_decision_prerequisites(p, change)
            status = (
                "STANDING_AUTHORIZED"
                if standing
                else {"APPROVE": "APPROVED", "EDIT": "EDITED", "REJECT": "REJECTED"}[
                    decision
                ]
            )
            r = dict(
                proposal_id=pid,
                proposal_version=p["version"],
                decision_status=status,
                application_status="NOT_STARTED",
                mode=self.mode,
                source_entity_id=p["entity_id"],
                publishers=[],
            )
            p["decision_status"] = status
            p["_decided_at"] = self.stamp()
            p["_result"] = r
            p["allowed_decisions"] = []
            if decision != "REJECT":
                opid = self.store.next_id("operation")
                r.update(
                    operation_id=opid,
                    application_status="PENDING",
                    final_change=change,
                    target_entity_id=self.target(p["entity_id"]),
                )
                op = dict(
                    operation_id=opid,
                    proposal_id=pid,
                    change=change,
                    baseline_hash=p["baseline_hash"],
                    status="PENDING",
                    attempts=0,
                    created_at=self.stamp(),
                    permission_id=standing,
                )
                self.store.put("operations", opid, op)
                if change["kind"] == "WEEKLY_HOURS" and date.fromisoformat(
                    change["effective_from"]
                ) > local_date(self.now(), p["timezone"]):
                    due = iso_utc(
                        local_midnight_utc(
                            date.fromisoformat(change["effective_from"]), p["timezone"]
                        )
                    )
                    op["status"] = "SCHEDULED"
                    r["application_status"] = "SCHEDULED"
                    self.store.put(
                        "jobs",
                        opid,
                        dict(operation_id=opid, due_at=due, status="PENDING"),
                    )
            self.store.put(
                "decisions",
                pid,
                dict(
                    proposal_id=pid,
                    decision=status,
                    change=change if decision != "REJECT" else None,
                    decided_at=self.stamp(),
                ),
            )
            self.store.data["idempotency"][key] = {
                "hash": fingerprint(body),
                "result": copy.deepcopy(r),
                "proposal_id": pid,
            }
            self.store.save()  # intent durable BEFORE any remote write
            if r["application_status"] == "PENDING":
                self._apply(op)
            result = self.result(pid)
            self.store.data["idempotency"][key]["result"] = result
            self.store.save()
            return result

    def _validate_decision_change(self, p, change):
        validate_change(change)
        if change["kind"] == "REOPEN_DATE" and date.fromisoformat(
            change["reopen_date"]
        ) <= local_date(self.now(), p["timezone"]):
            raise AppError(
                422, "INVALID_REOPEN_DATE", "Choose a future reopening date."
            )
        if change["kind"] != p["change"]["kind"]:
            raise AppError(
                422, "SCOPE_CHANGE", "An edit cannot change the proposal type."
            )
        scopekey = {
            "DATE_HOURS": "date",
            "WEEKLY_HOURS": "effective_from",
            "REOPEN_DATE": None,
        }[change["kind"]]
        if scopekey and change[scopekey] != p["change"][scopekey]:
            raise AppError(
                422, "SCOPE_CHANGE", "An edit cannot change the target date."
            )
        if change["kind"] == "WEEKLY_HOURS" and set(change["weekdays"]) != set(
            p["change"]["weekdays"]
        ):
            raise AppError(
                422, "SCOPE_CHANGE", "An edit cannot expand weekday scope."
            )

    def _validate_decision_prerequisites(self, p, change):
        if self.mode == "sandbox" and not self.allow_writes:
            raise AppError(
                403,
                "SANDBOX_WRITES_DISABLED",
                "Sandbox writes are not enabled.",
            )
        latest = self._read(p["entity_id"])
        if (
            relevant_state_hash(
                scope_value(latest.get("hours", {}), p["change"])
            )
            != p["baseline_hash"]
        ):
            raise AppError(
                409,
                "STALE_BASELINE",
                "Current hours changed since the proposal.",
            )
        if p["change"]["kind"] == "DATE_HOURS" and not p.get(
            "_external_supported"
        ):
            current = evaluate_context(
                self._context(p["entity_id"], p["change"]["date"], latest),
                self.now(),
            )
            if (
                current["action"] == "FLAG"
                or current.get("change") != p["change"]
            ):
                raise AppError(
                    409,
                    "EVIDENCE_CHANGED",
                    "Supporting evidence changed; run a fresh review.",
                )
        self._validate_adjacent(latest.get("hours", {}), change)

    def _validate_adjacent(self, hours, change):
        merged = merge_change_into_hours(hours, change)
        if change["kind"] == "DATE_HOURS":
            d = date.fromisoformat(change["date"])
            checks = [d - timedelta(days=1), d]
            for day in checks:
                first_value = effective(merged, str(day))
                next_value = effective(merged, str(day + timedelta(days=1)))
                first = (
                    []
                    if first_value == "not_registered"
                    else parse_intervals(first_value)
                )
                nxt = (
                    []
                    if next_value == "not_registered"
                    else parse_intervals(next_value)
                )
                if (
                    first
                    and nxt
                    and max(b for _, b in first) > MINUTES_PER_DAY + min(a for a, _ in nxt)
                ):
                    raise AppError(
                        422,
                        "OVERNIGHT_OVERLAP",
                        "Hours overlap opening on the adjacent date.",
                    )
        elif change["kind"] == "WEEKLY_HOURS":
            for i, d in enumerate(DAYS):
                if (
                    d not in change["weekdays"]
                    and DAYS[(i + 1) % 7] not in change["weekdays"]
                ):
                    continue
                a = parse_intervals(day_to_hours_string(merged.get(d)))
                b = parse_intervals(day_to_hours_string(merged.get(DAYS[(i + 1) % 7])))
                if a and b and max(e for _, e in a) > MINUTES_PER_DAY + min(s for s, _ in b):
                    raise AppError(
                        422, "OVERNIGHT_OVERLAP", "Weekly hours overlap the next day."
                    )

    def _apply(self, op):
        p = self.proposal(op["proposal_id"])
        r = p["_result"]
        change = op["change"]

        def fail(status, code, retryable=False):
            op["status"] = status
            r.update(application_status=status, error_code=code, retryable=retryable)
            self.store.save()

        err_code = self._check_apply_preconditions(op, p)
        if err_code:
            return fail("REVIEW_REQUIRED", err_code)
        for _ in range(3):
            try:
                latest = self._read(p["entity_id"])
                h = latest.get("hours") or {}
            except AppError:
                return fail("FAILED", "YEXT_READ_FAILED", True)
            if read_back_value(h, change) == change_target_value(change):
                return self._verified(op)
            if relevant_state_hash(scope_value(h, p["change"])) != op["baseline_hash"]:
                return fail("CONFLICT", "STALE_BASELINE")
            if latest.get("closed"):
                return fail("REVIEW_REQUIRED", "OPERATING_STATUS_CHANGED")
            if op["attempts"] >= 3:
                return fail("FAILED", "WRITE_RETRY_LIMIT", True)
            self._validate_adjacent(h, change)
            op["attempts"] += 1
            self.store.save()
            try:
                self.client._req(
                    "PUT",
                    "entities/" + self.target(p["entity_id"]),
                    body={"hours": merge_change_into_hours(h, change)},
                )
            except Exception as exc:
                if any(
                    marker in str(exc)
                    for marker in ("-> 401:", "-> 403:", "-> 400:", "-> 422:")
                ):
                    if self.mode == "sandbox":
                        self.sandbox_write = "FAILED"
                    return fail("FAILED", "YEXT_PERMISSION_OR_VALIDATION_FAILED", False)
                # A timeout is uncertain; read before any repeat write. Permission failures remain failures.
                if self.mode == "sandbox":
                    self.sandbox_write = "FAILED"
            try:
                check = self._read(p["entity_id"]).get("hours") or {}
            except AppError:
                return fail("FAILED", "READBACK_UNAVAILABLE", True)
            if read_back_value(check, change) == change_target_value(change):
                return self._verified(op)
            if (
                relevant_state_hash(scope_value(check, p["change"]))
                != op["baseline_hash"]
            ):
                return fail("CONFLICT", "UNEXPECTED_REMOTE_STATE")
        fail("FAILED", "WRITE_NOT_VERIFIED", True)

    def _check_apply_preconditions(self, op, p):
        if op.get("permission_id"):
            perm = self.matching_permission(p)
            if not perm or perm["permission_id"] != op["permission_id"]:
                return "PERMISSION_REVOKED"
        if self.mode == "sandbox" and not self.allow_writes:
            return "SANDBOX_WRITES_DISABLED"
        if self.mode == "sandbox" and p.get("target_entity_id") != self.target_id:
            return "SANDBOX_TARGET_CHANGED"
        return None

    def _verified(self, op):
        p = self.proposal(op["proposal_id"])
        r = p["_result"]
        op["status"] = "SUCCEEDED"
        r.update(
            application_status="SUCCEEDED", verified_at=self.stamp(), retryable=False
        )
        r.pop("error_code", None)
        r["publishers"] = []
        for row in self.data.publishers_for(p["entity_id"]):
            entry = dict(
                publisher_id=row["publisherId"],
                publisher_name=row.get("publisherName", row["publisherId"]),
                listing_status=row.get("status", "UNKNOWN"),
                basis="MOCK_DATASET_ESTIMATE",
                publication_status="UNKNOWN",
            )
            delay = row.get("typicalUpdateSpeedSeconds")
            if row.get("status") == "LIVE" and isinstance(delay, int) and delay >= 0:
                entry.update(
                    publication_status="ESTIMATED",
                    typical_update_seconds=delay,
                    expected_live_by=iso_utc(self.now() + timedelta(seconds=delay)),
                )
            r["publishers"].append(entry)
        if self.mode == "sandbox":
            self.sandbox_write = "VERIFIED"
        self.store.save()

    def tick(self):
        with self.lock:
            if self.reset_blocked:
                return
            source_changed = self._refresh_sources()

            for eid, last in list(self.store.data.get("watchlist", {}).items()):
                zone = self._entity(eid).get("timezone", "Europe/Helsinki")
                local = self.now().astimezone(_get_timezone(zone))
                if source_changed or (str(local.date()) != last and local.hour >= 9):
                    self.cycle(dict(scope="OPERATIONAL", entity_ids=[eid]))
            for p in self.store.data["proposals"].values():
                if (
                    p["decision_status"] == "PENDING"
                    and parse_dt(p["expires_at"]) <= self.now()
                ):
                    p["decision_status"] = "EXPIRED"
                    p["allowed_decisions"] = []
            for m in self.store.data["messages"].values():
                self._tick_message(m)
            for op in list(self.store.data["operations"].values()):
                self._tick_operation(op)
            self.store.save()

    def _tick_message(self, m):
        if (
            m["status"] != "QUEUED"
            or not m["scheduled_at"]
            or parse_dt(m["scheduled_at"]) > self.now()
        ):
            return
        pref = self.preferences(m["entity_id"])
        if pref["source_opted_out"]:
            m["status"] = "BLOCKED_OPT_OUT"
        elif pref["frequency"] == "PAUSED":
            m["status"] = "BLOCKED_PAUSED"
        elif any(
            self.proposal(pid)["decision_status"] == "EXPIRED"
            for pid in m["proposal_ids"]
        ):
            m["status"] = "EXPIRED"
        else:
            zone = self._entity(m["entity_id"]).get(
                "timezone", "Europe/Helsinki"
            )
            local = self.now().astimezone(_get_timezone(zone))
            window = pref["best_contact_window"]
            start, end = map(int, window.split("-"))
            if local.hour < start:
                m["scheduled_at"] = iso_utc(
                    dispatch_datetime(local.date(), window, zone)
                )
            elif local.hour >= end:
                m["scheduled_at"] = iso_utc(
                    dispatch_datetime(
                        local.date() + timedelta(days=1), window, zone
                    )
                )
            else:
                m["status"] = "DELIVERED_SIMULATED"

    def _tick_operation(self, op):
        if op["status"] == "PENDING" or (
            op["status"] == "FAILED"
            and self.proposal(op["proposal_id"])
            .get("_result", {})
            .get("error_code")
            == "READBACK_UNAVAILABLE"
        ):
            self._apply(op)
        elif op["status"] == "SCHEDULED":
            job = self.store.get("jobs", op["operation_id"])
            due = parse_dt(job["due_at"])
            if due <= self.now():
                if self.now() - due > timedelta(hours=24):
                    op["status"] = "REVIEW_REQUIRED"
                    self.proposal(op["proposal_id"])["_result"].update(
                        application_status="REVIEW_REQUIRED",
                        error_code="MISSED_JOB",
                    )
                else:
                    self._apply(op)
                job["status"] = op["status"]

    def interpret(self, pid, b, multiple=False):
        p = copy.deepcopy(self.get_proposal(pid))
        if p["decision_status"] != "PENDING":
            raise AppError(
                410 if p["decision_status"] == "EXPIRED" else 409,
                "PROPOSAL_NOT_PENDING",
                "This proposal is no longer awaiting a decision.",
            )
        if multiple and b["text"].strip().lower() in (
            "yes",
            "ok",
            "ja",
            "kyllä",
            "네",
            "joo",
        ):
            return dict(
                status="NEEDS_CLARIFICATION",
                intent="UNKNOWN",
                preview="Choose the date this reply applies to.",
                missing_fields=["date"],
            )
        low = b["text"].lower().strip()
        pref = self.preferences(p["entity_id"])
        freq = None
        if low in (
            "pause messages",
            "pause",
            "keskeytä viestit",
            "pausa meddelanden",
            "pause meldinger",
            "연락 정지",
        ):
            freq = "PAUSED"
        if low in (
            "monthly",
            "once a month",
            "kerran kuussa",
            "en gång i månaden",
            "en gang i måneden",
            "매월",
        ):
            freq = "MONTHLY"
        if low in (
            "twice monthly",
            "kahdesti kuussa",
            "två gånger i månaden",
            "to ganger i måneden",
            "월 2회",
        ):
            freq = "TWICE_MONTHLY"
        if freq:
            return dict(
                status="READY",
                intent="SET_FREQUENCY",
                preview="Set contact frequency to " + freq + ".",
                preference_draft={"version": pref["version"], "frequency": freq},
                missing_fields=[],
            )
        phrases = (
            "allow future holiday corrections",
            "jatkossa saa korjata",
            "tillåt framtida helgdagsändringar",
            "tillat fremtidige helligdagsendringer",
            "앞으로 공휴일 수정 허용",
        )
        if low in phrases:
            return dict(
                status="READY",
                intent="SET_STANDING_PERMISSION",
                preview="Allow validated date-specific corrections only for "
                + p["day_key"]
                + " for one year.",
                permission_draft=dict(
                    day_keys=[p["day_key"]],
                    change_kind="DATE_HOURS",
                    purpose="CORRECTION",
                    expires_at=iso_utc(self.now() + timedelta(days=364)),
                    confirmed=True,
                ),
                missing_fields=[],
            )
        return self.replies.interpret(b["text"], b["language"], p, multiple=multiple)

    def _message_text(self, eid, proposals, language):
        lex = {
            "fi": (
                "Hei",
                "Nykyiset aukioloajat",
                "Ehdotamme",
                "Hyväksy / Muokkaa / Ei kiitos",
                "kiinni",
                "Aiemmin vahvistamasi saman pyhäpäivän aukioloajat tukevat tätä ehdotusta.",
                "Kauppakeskuksen ajat ja aiempi toimintanne tukevat ehdotusta.",
                "Tämän päivän vahvistus poikkeaa nykyisistä tiedoista.",
            ),
            "sv": (
                "Hej",
                "Nuvarande öppettider",
                "Vi föreslår",
                "Godkänn / Ändra / Nej tack",
                "stängt",
                "Dina tidigare bekräftade tider för samma helgdag stöder förslaget.",
                "Köpcentrets tider och er tidigare praxis stöder förslaget.",
                "En bekräftelse för dagen skiljer sig från nuvarande tider.",
            ),
            "nb": (
                "Hei",
                "Nåværende åpningstider",
                "Vi foreslår",
                "Godkjenn / Endre / Nei takk",
                "stengt",
                "Tidligere bekreftede tider for samme helligdag støtter forslaget.",
                "Senterets tider og deres tidligere praksis støtter forslaget.",
                "En bekreftelse for dagen avviker fra nåværende tider.",
            ),
            "en": (
                "Hi",
                "Currently shown",
                "We propose",
                "Approve / Edit / No thanks",
                "closed",
                "Your confirmed hours for this holiday in a previous season support these times.",
                "The centre’s dated schedule and your own past alignment support these times.",
                "A current confirmation for this date differs from the listed hours.",
            ),
        }[language]
        lines = [lex[0] + " " + self._entity(eid).get("name", eid) + "!"]
        for p in proposals:
            day = p["change"].get(
                "date",
                p["change"].get("effective_from", p["change"].get("reopen_date")),
            )
            shown = p["baseline"].get("hours", "—")
            if shown == "not_registered":
                shown = {
                    "fi": "ei ilmoitettu",
                    "sv": "ej angivet",
                    "nb": "ikke oppgitt",
                    "en": "not registered",
                }[language]
            proposed = p["change"].get("hours", day)
            shown = lex[4] if shown == "closed" else shown
            proposed = lex[4] if proposed == "closed" else proposed
            reason = (
                lex[6]
                if p["reason_code"] == "CENTRE_ALIGNED"
                else lex[7]
                if p["reason_code"] in ("OWNER_CONFIRMED", "FEEDBACK_REUSE")
                else lex[5]
            )
            cal = self.data.cal_by_date.get(
                (self._entity(eid)["meta"]["countryCode"], day), {}
            )
            holiday = cal.get(
                "name_en" if language == "en" else "name_local",
                p["day_key"].replace("_", " "),
            )
            lines.append(
                f"{day} ({holiday})\n{lex[1]}: {shown}.\n{reason}\n{lex[2]}: {proposed}."
            )
        return "\n\n".join(lines + [lex[3]])

    def create_message(self, b, *, persist=True, include_entry=True):
        with self.lock:
            eid = b["entity_id"]
            pref = self.preferences(eid)
            ps = [self.proposal(x) for x in b["proposal_ids"]]
            if any(p["entity_id"] != eid for p in ps):
                raise AppError(
                    403, "CROSS_ENTITY", "Message scope does not match the business."
                )
            if any(not is_proposal_active(p, self.now()) for p in ps):
                raise AppError(
                    410,
                    "PROPOSAL_EXPIRED",
                    "Only current undecided proposals can be contacted.",
                )
            status = (
                "BLOCKED_OPT_OUT"
                if pref["source_opted_out"]
                else "BLOCKED_PAUSED"
                if pref["frequency"] == "PAUSED"
                else "DELIVERED_SIMULATED"
                if b["delivery_mode"] == "PREVIEW"
                else "QUEUED"
            )
            scheduled = (
                None
                if b["delivery_mode"] == "PREVIEW" or status.startswith("BLOCKED")
                else pref["next_contact_at"]
            )
            if scheduled:
                for proposal in ps:
                    if parse_dt(scheduled) >= parse_dt(proposal["expires_at"]):
                        case = self.store.get("cases", proposal["case_id"])
                        gap = "CONTACT_WINDOW_GAP: proposal expires before the next permitted dispatch."
                        if case and gap not in case["gaps"]:
                            case["gaps"].append(gap)
            for m in self.store.data["messages"].values():
                if (
                    m["entity_id"] == eid
                    and sorted(m["proposal_ids"]) == sorted(b["proposal_ids"])
                    and m["delivery_mode"] == b["delivery_mode"]
                    and m["status"] == status
                ):
                    return (
                        self._message_view(m)
                        if include_entry
                        else self._english_message(m)
                    )
            mid = self.store.next_id("message")
            m = dict(
                message_id=mid,
                entity_id=eid,
                proposal_ids=b["proposal_ids"],
                channel=pref["preferred_channel"],
                language="en",
                text=self._message_text(eid, ps, "en"),
                status=status,
                delivery_mode=b["delivery_mode"],
                simulated=True,
                scheduled_at=scheduled,
            )
            self.store.put("messages", mid, m)
            if persist:
                self.store.save()
            return self._message_view(m) if include_entry else copy.deepcopy(m)

    def _english_message(self, message):
        """English demo presentation; preserve source contacts and old message records."""
        out = copy.deepcopy(message)
        if out["language"] != "en":
            proposals = [
                self.store.get("proposals", pid) for pid in out["proposal_ids"]
            ]
            out["text"] = (
                self._message_text(out["entity_id"], proposals, "en")
                if all(proposals)
                else "This proposal is no longer available. Open the review queue for current suggestions."
            )
        out["language"] = "en"
        return out

    def _message_view(self, m, *, persist=True):
        out = self._english_message(m)
        contact = self.data.contact(m["entity_id"])
        out["sender"] = "Fonecta Connect · Demo"
        out["recipient"] = (
            contact.get("email", "")
            if m["channel"] == "EMAIL"
            else contact.get("mobile", "")
            if m["channel"] in ("SMS", "WHATSAPP")
            else m["entity_id"] + " · app"
        )
        out["subject"] = (
            "Confirm your special opening hours" if m["channel"] == "EMAIL" else ""
        )
        if m["status"] == "DELIVERED_SIMULATED":
            out["owner_entry_path"] = "/customer#token=" + self.mint_token(
                m["entity_id"], m["proposal_ids"], persist=persist
            )
        return out

    def messages(self, entity_id=None, offset=0, limit=50, delivery_mode=None):
        with self.lock:
            rows = [
                m
                for m in self.store.data["messages"].values()
                if (not entity_id or m["entity_id"] == entity_id)
                and (not delivery_mode or m["delivery_mode"] == delivery_mode)
            ]
            # Persist the page's entry tokens atomically once, before returning links.
            # Keep auth locked so concurrent sessions cannot save a partial page.
            with self.auth.lock:
                items = [
                    self._message_view(m, persist=False)
                    for m in rows[offset : offset + limit]
                ]
                if any("owner_entry_path" in m for m in items):
                    self.auth.save()
            return {
                "items": items,
                "total": len(rows),
                "offset": offset,
                "limit": limit,
            }

    def resolve(self, iid, b):
        with self.lock:
            issue = self.store.get("issues", iid)
            if not issue:
                raise AppError(404, "ISSUE_NOT_FOUND", "Issue not found.")
            issue.update(
                status=b["resolution"],
                note=b["note"],
                resolution_evidence=b["evidence"],
                resolved_at=self.stamp(),
            )
            self.store.save()
            return dict(
                issue_id=iid,
                status=b["resolution"],
                recheck_case_ids=[
                    c["case_id"]
                    for c in self.store.data["cases"].values()
                    if c.get("issue_id") == iid
                ],
            )

    def operator_session(self):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.auth.lock:
            self.auth.data["operator_sessions"][digest(token)] = {
                "csrf": digest(csrf),
                "expires_at": iso_utc(datetime.now(timezone.utc) + timedelta(hours=12)),
            }
            self.auth.save()
        return token, csrf

    def mint_token(self, eid, pids, *, persist=True):
        token = secrets.token_urlsafe(32)
        expires = iso_utc(self.now() + timedelta(days=14))
        entry = dict(
            entity_id=eid,
            proposal_ids=pids,
            versions={pid: self.proposal(pid)["version"] for pid in pids},
            permissions=["decide", "preferences", "standing_permissions", "results"],
            expires_at=expires,
        )
        with self.auth.lock:
            self.auth.data["owner_tokens"][digest(token)] = entry
            if persist:
                self.auth.save()
        return token

    def exchange_token(self, token):
        with self.auth.lock:
            entry = self.auth.data["owner_tokens"].get(digest(token))
            if not entry or parse_dt(entry["expires_at"]) <= self.now():
                raise AppError(401, "INVALID_TOKEN", "Invalid or expired owner entry.")
            session = secrets.token_urlsafe(32)
            self.auth.data["owner_sessions"][digest(session)] = copy.deepcopy(entry)
            self.auth.save()
            return {
                k: copy.deepcopy(entry[k])
                for k in ("entity_id", "proposal_ids", "permissions", "expires_at")
            }, session

    def authenticate(self, cookies, operator=False, eid=None, pid=None):
        if operator:
            s = self.auth.data["operator_sessions"].get(
                digest(cookies.get("operator_session", ""))
            )
            if not s or parse_dt(s["expires_at"]) <= datetime.now(timezone.utc):
                raise AppError(
                    401, "OPERATOR_REQUIRED", "Open the local operator page first."
                )
            return s
        s = self.auth.data["owner_sessions"].get(
            digest(cookies.get("owner_session", ""))
        )
        if not s or parse_dt(s["expires_at"]) <= self.now():
            raise AppError(
                401, "OWNER_SESSION_REQUIRED", "A valid owner session is required."
            )
        if eid and s["entity_id"] != eid or pid and pid not in s["proposal_ids"]:
            raise AppError(
                403,
                "CROSS_ENTITY",
                "This session cannot access the requested business or proposal.",
            )
        if pid and s["versions"].get(pid) != self.proposal(pid)["version"]:
            raise AppError(
                409, "STALE_VERSION", "Owner session has an older proposal version."
            )
        return s
