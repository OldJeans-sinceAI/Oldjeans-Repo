"""Domain core: hours primitives, source loaders, Detect/Suggest engine, scheduling and NL.

Pure logic with no HTTP or persistence dependencies so it can be unit-tested with
hand-built fixtures (see tests/product/test_backend.py). The Detect/Suggest engine
runs on a `DetectContext` which `DataStore` builds from the real synthetic sources,
and which tests build directly to isolate a single acceptance scenario.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Optional

from . import POLICY

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
HOURS_CLOSED = "closed"
MINUTES_PER_DAY = 1440
EARTH_RADIUS_METERS = 6371000
DEFAULT_EPOCH_ISO = "1970-01-01T00:00:00Z"
WINDOW_START_HOURS = {"08-10": 8, "10-12": 10, "12-16": 12, "16-20": 16}
DEFAULT_WINDOW_START_HOUR = 10

# --------------------------------------------------------------------------- hours


class HoursError(ValueError):
    """Raised for a schedule string that fails syntactic or semantic validation (HTTP 422)."""


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _time_to_minutes(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:])


def _minutes_to_time(m: int) -> str:
    m %= MINUTES_PER_DAY
    return f"{m // 60:02d}:{m % 60:02d}"


def _format_interval_end(e: int) -> str:
    return "23:59" if e == MINUTES_PER_DAY - 1 else _minutes_to_time(e)


def parse_intervals(spec: str) -> list[tuple[int, int]]:
    """Parses a hours specification string into a list of (start_minutes, end_minutes) tuples.

    Rules & Edge Cases:
    - 'closed' or empty string -> []
    - Standard range '09:00-17:00' -> [(540, 1020)]
    - Overnight range (e.g., '22:00-02:00'): because end <= start, 1440 minutes (24h) is added
      to end_minutes -> [(1320, 1560)]. This allows overnight intervals to span across midnight
      for simple interval math.
    - 24-hour full day: '00:00-23:59' is treated specially without overnight offset -> [(0, 1439)].
    - Rejects invalid clock strings, zero-length intervals (e.g. '10:00-10:00'), and any
      overlapping intervals (including overnight tails wrapping into subsequent times).
    """
    s = (spec or "").strip().lower()
    if s == HOURS_CLOSED:
        return []
    if not s:
        raise HoursError("hours must be explicit")
    out: list[tuple[int, int]] = []
    for raw in s.split(","):
        part = raw.strip()
        if "-" not in part:
            raise HoursError(f"interval {part!r} is not HH:MM-HH:MM")
        a, b = part.split("-", 1)
        if not (_TIME_RE.match(a) and _TIME_RE.match(b)):
            raise HoursError(f"interval {part!r} has an invalid clock value")
        start_minutes, end_minutes = _time_to_minutes(a), _time_to_minutes(b)
        if start_minutes == end_minutes:
            raise HoursError(
                f"interval {part!r} is zero length; use 00:00-23:59 for 24 hours"
            )
        if end_minutes < start_minutes and not (a == "00:00" and b == "23:59"):
            end_minutes += MINUTES_PER_DAY  # overnight rollover into the next date
        out.append((start_minutes, end_minutes))
    # overlap check, including wrap of an overnight tail into the first interval
    ordered = sorted(out)
    for (start1, end1), (start2, end2) in zip(ordered, ordered[1:]):
        if start2 < end1:
            raise HoursError("intervals overlap")
    return out


def validate_hours(spec: str) -> str:
    """Validate and return the canonical hours string, or raise HoursError."""
    ivs = parse_intervals(spec)
    return canonical_hours(spec) if ivs else "closed"


def canonical_hours(spec: str) -> str:
    ivs = parse_intervals(spec)
    if not ivs:
        return HOURS_CLOSED
    parts = []
    for s, e in sorted(ivs):
        parts.append(f"{_minutes_to_time(s)}-{_format_interval_end(e)}")
    return ",".join(parts)


def hours_equal(a: str, b: str) -> bool:
    try:
        return sorted(parse_intervals(a)) == sorted(parse_intervals(b))
    except HoursError:
        return False


def same_open_state(a: str, b: str) -> bool:
    return (canonical_hours(a) == "closed") == (canonical_hours(b) == "closed")


def hours_string_to_day(spec: str) -> dict:
    """Canonical string -> Yext day/holiday object."""
    ivs = parse_intervals(spec)
    if not ivs:
        return {"isClosed": True}
    return {
        "openIntervals": [
            {"start": _minutes_to_time(s), "end": _format_interval_end(e)} for s, e in ivs
        ]
    }


def day_to_hours_string(obj: Optional[dict]) -> str:
    if not obj or obj.get("isClosed"):
        return HOURS_CLOSED
    ivs = obj.get("openIntervals") or []
    if not ivs:
        return HOURS_CLOSED
    return ",".join(f"{i['start']}-{i['end']}" for i in ivs)


def relevant_state_hash(value: str) -> str:
    return (
        "sha256:"
        + hashlib.sha256(canonical_hours_or_raw(value).encode()).hexdigest()[:32]
    )


def canonical_hours_or_raw(value: str) -> str:
    try:
        return canonical_hours(value)
    except HoursError:
        return (value or "").strip().lower()


# --------------------------------------------------------------- change application


def merge_change_into_hours(current_hours: dict, change: dict) -> dict:
    """Return a NEW full hours object with only the authorized change merged in.

    DATE_HOURS upserts one holidayHours date; WEEKLY_HOURS replaces only named weekdays;
    REOPEN_DATE sets only hours.reopenDate. Everything else is preserved verbatim.
    """
    hours = json.loads(json.dumps(current_hours or {}))
    kind = change["kind"]
    if kind == "DATE_HOURS":
        d = change["date"]
        hol = [h for h in hours.get("holidayHours", []) if h.get("date") != d]
        hol.append({"date": d, **hours_string_to_day(change["hours"])})
        hours["holidayHours"] = sorted(hol, key=lambda h: h["date"])
    elif kind == "WEEKLY_HOURS":
        for wd, spec in change["weekdays"].items():
            hours[wd] = hours_string_to_day(spec)
    elif kind == "REOPEN_DATE":
        hours["reopenDate"] = change["reopen_date"]
    else:
        raise HoursError(f"unknown change kind {kind}")
    return hours


def _format_weekly_hours(weekdays: dict) -> str:
    return ";".join(
        f"{wd}={canonical_hours(weekdays[wd])}"
        for wd in sorted(weekdays)
    )


def read_back_value(hours: dict, change: dict) -> str:
    """Extract the canonical stored value for a change so it can be compared to intent."""
    kind = change["kind"]
    if kind == "DATE_HOURS":
        for h in hours.get("holidayHours", []):
            if h.get("date") == change["date"]:
                if h.get("isRegularHours"):
                    return "REGULAR"
                return canonical_hours(day_to_hours_string(h))
        return "ABSENT"
    if kind == "WEEKLY_HOURS":
        return _format_weekly_hours(
            {wd: day_to_hours_string(hours.get(wd)) for wd in change["weekdays"]}
        )
    if kind == "REOPEN_DATE":
        return str(hours.get("reopenDate", ""))
    return ""


def change_target_value(change: dict) -> str:
    kind = change["kind"]
    if kind == "DATE_HOURS":
        return canonical_hours(change["hours"])
    if kind == "WEEKLY_HOURS":
        return _format_weekly_hours(change["weekdays"])
    if kind == "REOPEN_DATE":
        return change["reopen_date"]
    return ""


def validate_change(change: dict) -> dict:
    """Semantic validation of a Change union member. Raises HoursError (-> 422)."""
    kind = change.get("kind")
    if kind == "DATE_HOURS":
        date.fromisoformat(change["date"])
        change = dict(change, hours=canonical_hours(change["hours"]))
    elif kind == "WEEKLY_HOURS":
        date.fromisoformat(change["effective_from"])
        wds = change.get("weekdays") or {}
        if not wds:
            raise HoursError("weekdays must name at least one day")
        change = dict(
            change, weekdays={wd: canonical_hours(v) for wd, v in wds.items()}
        )
    elif kind == "REOPEN_DATE":
        date.fromisoformat(change["reopen_date"])
    else:
        raise HoursError(f"unknown change kind {kind!r}")
    return change


# ------------------------------------------------------------------- time helpers

_WINTER_OFFSETS = {"Europe/Helsinki": 2, "Europe/Stockholm": 1, "Europe/Oslo": 1}


def parse_dt(value: str) -> datetime:
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = (
        sin(radians(lat2 - lat1) / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    )
    return EARTH_RADIUS_METERS * 2 * atan2(sqrt(a), sqrt(max(0, 1 - a)))


def is_proposal_active(p: dict, now: datetime) -> bool:
    return p.get("decision_status") == "PENDING" and parse_dt(p["expires_at"]) > now


def _get_timezone(name: str):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        # Evaluation window (Nov-Jan) is entirely winter time; fixed offsets are safe.
        return timezone(timedelta(hours=_WINTER_OFFSETS.get(name, 0)))


def local_date(now: datetime, tzname: str) -> date:
    return now.astimezone(_get_timezone(tzname)).date()


def local_midnight_utc(d: date, tzname: str) -> datetime:
    naive = datetime(d.year, d.month, d.day, 0, 0, 0)
    return naive.replace(tzinfo=_get_timezone(tzname)).astimezone(timezone.utc)


# ------------------------------------------------------------------- scheduling


def window_start_hour(window: str) -> int:
    return WINDOW_START_HOURS.get(window, DEFAULT_WINDOW_START_HOUR)


def next_dispatch_date(d: date, frequency: str) -> date:
    """First regular dispatch strictly after `d`. On a dispatch day, the next one."""
    days = [1, 15] if frequency == "TWICE_MONTHLY" else [1]
    probe = d + timedelta(days=1)
    for _ in range(70):
        if probe.day in days:
            return probe
        probe += timedelta(days=1)
    return probe


def detection_horizon(now_local: date, frequency: str, buffer_days: int = 2) -> date:
    """today .. next dispatch + buffer_days (section 10 / P02). Christmas-safe."""
    return next_dispatch_date(now_local, frequency) + timedelta(days=buffer_days)


def dispatch_datetime(d: date, window: str, tzname: str) -> datetime:
    naive = datetime(d.year, d.month, d.day, window_start_hour(window), 0, 0)
    return naive.replace(tzinfo=_get_timezone(tzname)).astimezone(timezone.utc)


def compute_next_contact_at(
    now: datetime, tzname: str, window: str, frequency: str
) -> Optional[str]:
    if frequency == "PAUSED":
        return None
    today = local_date(now, tzname)
    days = [1, 15] if frequency == "TWICE_MONTHLY" else [1]
    if today.day in days:
        send = dispatch_datetime(today, window, tzname)
        end = send + timedelta(
            hours=int(window.split("-")[1]) - window_start_hour(window)
        )
        if now < end:
            return iso_utc(max(now, send))
        return iso_utc(dispatch_datetime(today + timedelta(days=1), window, tzname))
    return iso_utc(
        dispatch_datetime(next_dispatch_date(today, frequency), window, tzname)
    )


# ------------------------------------------------------------------- Detect/Suggest


@dataclass
class DetectContext:
    """Everything the engine needs about one (business, target date), cutoff-limited.

    Tests construct this directly; DataStore.context() builds it from real sources.
    """

    entity_id: str
    business_name: str
    timezone: str
    country: str
    segment: str
    target_date: str
    day_key: str
    day_type: str
    cutoff: str
    displayed_hours: str
    already_closed: bool = False
    # evidence inputs (all cutoff-limited by the loader)
    owner_confirmation: Optional[dict] = (
        None  # {hours, known_at, source_record} same-date, current-year
    )
    own_history: list = field(
        default_factory=list
    )  # [{date, hours, entered_at, source_record}]
    pilot_finals: list = field(
        default_factory=list
    )  # [{date, decision, final_hours, decided_at}]
    centre: Optional[dict] = (
        None  # {name, entity_id, target_hours, match_dates:int, agreement:float}
    )
    peer: Optional[dict] = None  # {closed_share, n_entity_days, corroborated:bool}
    closure_signals: list = field(
        default_factory=list
    )  # [{source_file, source_record, summary, known_at}]
    owner_permanent_closure: bool = False
    conflicts: list = field(
        default_factory=list
    )  # [{hours, source_record, known_at}] unresolved same-date
    comparable: list = field(default_factory=list)
    context_evidence: list = field(default_factory=list)
    opportunity: Optional[dict] = None
    source_gaps: list = field(default_factory=list)
    feedback: Optional[dict] = (
        None  # runtime-confirmed value for this exact date {hours, source_record, known_at}
    )
    analytics_views: Optional[float] = None
    search_percentile: Optional[float] = None


def _days_until(target: str, now: datetime, tzname: str) -> int:
    return (date.fromisoformat(target) - local_date(now, tzname)).days


def _evidence(
    evidence_id,
    source_file,
    source_record,
    role,
    summary,
    known_at=None,
    applicable_date=None,
) -> dict:
    out = {
        "evidence_id": evidence_id,
        "source_file": source_file,
        "source_record": source_record,
        "role": role,
        "summary": summary,
        "known_at": known_at or DEFAULT_EPOCH_ISO,
    }
    if applicable_date:
        out["applicable_date"] = applicable_date
    return out


def _priority(
    ctx: DetectContext, now: datetime, material: bool
) -> tuple[str, list[str]]:
    p = POLICY["P11_priority"]
    days = _days_until(ctx.target_date, now, ctx.timezone)
    reasons = []
    if material and 0 <= days <= p["urgent_days"]:
        return "URGENT", [f"Material issue with target {days} day(s) away"]
    if material and days <= p["high_days"]:
        reasons.append(f"Target within {p['high_days']} days")
        return "HIGH", reasons
    if (
        ctx.search_percentile is not None
        and ctx.search_percentile >= p["high_search_percentile"]
    ):
        return "HIGH", [
            f"Top-quartile trailing-{p['search_window_days']}d search views"
        ]
    return "ROUTINE", reasons or ["Routine cadence"]


def _candidate(
    hours: str,
    reason_code: str,
    confidence: str = "MEDIUM",
    purpose: str = "CORRECTION",
    profile: str = "PARTIAL",
) -> dict:
    return {
        "hours": hours,
        "confidence": confidence,
        "purpose": purpose,
        "reason_code": reason_code,
        "profile": profile,
    }


def _select_from_owner_confirmation(ctx: DetectContext, ev: list[dict]) -> Optional[dict]:
    if ctx.owner_confirmation:
        h = ctx.owner_confirmation["hours"]
        ev.append(
            _evidence(
                "ev-owner",
                "holiday_hours_history.jsonl",
                ctx.owner_confirmation.get("source_record", "owner-confirmation"),
                "DIRECT",
                "Current-year owner confirmation for this date.",
                ctx.owner_confirmation.get("known_at"),
                ctx.target_date,
            )
        )
        return _candidate(h, "OWNER_CONFIRMED", confidence="HIGH", profile="DIRECT")
    return None


def _select_from_feedback(ctx: DetectContext, ev: list[dict]) -> Optional[dict]:
    if ctx.feedback:
        ev.append(
            _evidence(
                "ev-feedback",
                "runtime/state.json",
                ctx.feedback.get("source_record", "confirmed-decision"),
                "DIRECT",
                "Owner previously confirmed these hours for this date.",
                ctx.feedback.get("known_at"),
                ctx.target_date,
            )
        )
        return _candidate(
            ctx.feedback["hours"],
            "FEEDBACK_REUSE",
            confidence="HIGH",
            profile="DIRECT",
        )
    return None


def _select_from_history(ctx: DetectContext, ev: list[dict]) -> Optional[dict]:
    own = sorted(
        ctx.own_history,
        key=lambda r: (r.get("date", ""), parse_dt(r.get("entered_at", "1970-01-01"))),
        reverse=True,
    )
    pilot = [
        p
        for p in ctx.pilot_finals
        if p.get("decision") in ("ACCEPTED", "EDITED") and p.get("final_hours")
    ]
    pilot.sort(
        key=lambda r: (r.get("date", ""), parse_dt(r.get("decided_at", "1970-01-01"))),
        reverse=True,
    )
    src = own[0] if own else None
    pil = pilot[0] if pilot else None
    best = None
    if src and pil:
        best = (
            src
            if (src.get("date", ""), parse_dt(src["entered_at"]))
            >= (pil.get("date", ""), parse_dt(pil["decided_at"]))
            else pil
        )
    else:
        best = src or pil
    if not best:
        return None
    if "final_hours" in best:
        h, sr, known = (
            best["final_hours"],
            best.get("suggestion_id", "pilot"),
            best.get("decided_at"),
        )
        fname, summary = (
            "pilot_decision_log_2025.csv",
            "Owner accepted/edited these hours for the same holiday in a previous season.",
        )
    else:
        h, sr, known = (
            best["hours"],
            best.get("source_record", "history"),
            best.get("entered_at"),
        )
        fname, summary = (
            "runtime/state.json"
            if str(sr).startswith("runtime:")
            else "holiday_hours_history.jsonl",
            "Own entry for the same day_key in a prior season.",
        )
    ev.append(
        _evidence(
            "ev-history", fname, sr, "DIRECT", summary, known, best.get("date")
        )
    )
    return _candidate(h, "HISTORY_PATTERN", profile="DIRECT")


def _select_from_centre(ctx: DetectContext, ev: list[dict]) -> Optional[dict]:
    P = POLICY["P09_evidence"]
    c = ctx.centre
    if (
        c
        and c.get("target_hours")
        and c.get("match_dates", 0) >= P["centre_min_dates"]
        and c.get("agreement", 0.0) >= P["centre_min_agreement"]
    ):
        ev.append(
            _evidence(
                "ev-centre",
                "holiday_hours_history.jsonl",
                c.get("entity_id", "centre"),
                "SUPPLEMENTARY",
                f"Shopping centre {c.get('name')} published these hours and "
                f"historically aligned ({c.get('match_dates')} dates, {c.get('agreement'):.0%}).",
                applicable_date=ctx.target_date,
            )
        )
        return _candidate(c["target_hours"], "CENTRE_ALIGNED")
    return None


def _select_from_comparable_or_opportunity(
    ctx: DetectContext, ev: list[dict]
) -> Optional[dict]:
    P = POLICY["P09_evidence"]
    groups = {}
    for row in ctx.comparable:
        groups.setdefault(row["hours"], []).append(row)
    eligible = [
        (h, rows)
        for h, rows in groups.items()
        if len({r["date"] for r in rows}) >= P["comparable_own_min_dates"]
    ]
    if len(eligible) == 1:
        h, rows = eligible[0]
        for row in rows:
            ev.append(
                _evidence(
                    "ev-comparable-" + row["date"],
                    "holiday_hours_history.jsonl",
                    row["source_record"],
                    "DIRECT",
                    "Own comparable holiday with the same day class and weekday/weekend baseline.",
                    row["entered_at"],
                    row["date"],
                )
            )
        return _candidate(h, "COMPARABLE_HOLIDAY")
    if ctx.opportunity:
        op = ctx.opportunity
        ev.extend(op["evidence"])
        return _candidate(
            op["hours"], "OWN_CONTEXT_PATTERN", purpose="OPPORTUNITY"
        )
    return None


def _select_from_peer(ctx: DetectContext, ev: list[dict]) -> Optional[dict]:
    P = POLICY["P09_evidence"]
    pr = ctx.peer
    if (
        pr
        and pr.get("n_entity_days", 0) >= P["peer_min_entity_days"]
        and pr.get("closed_share", 0.0) >= P["peer_closed_share"]
        and pr.get("corroborated")
    ):
        ev.append(
            _evidence(
                "ev-peer",
                "peer_benchmarks.csv",
                "peer-aggregate",
                "SUPPLEMENTARY",
                f"{pr['closed_share']:.0%} of comparable peers were closed, corroborated for this business.",
                applicable_date=ctx.target_date,
            )
        )
        return _candidate("closed", "PEER_CLOSED")
    return None


def _select_candidate(ctx: DetectContext, ev: list[dict]) -> Optional[dict]:
    """Return {hours, confidence, purpose, reason_code, profile} or None (section 8 order)."""
    return (
        _select_from_owner_confirmation(ctx, ev)
        or _select_from_feedback(ctx, ev)
        or _select_from_history(ctx, ev)
        or _select_from_centre(ctx, ev)
        or _select_from_comparable_or_opportunity(ctx, ev)
        or _select_from_peer(ctx, ev)
    )


def evaluate_context(ctx: DetectContext, now: datetime) -> dict:
    """Run Detect + Suggest for one context. Returns a dict with detection / case / proposal parts.

    Evaluation Workflow & Priority Hierarchy:
    1. Permanent Closure Signals: Checks review text / publisher flags. If signals suggest permanent
       closure, flags status as STATUS_CONCERN for human staff review.
    2. Already Closed Check: If business is already marked closed, retains current state (NO_ACTION).
    3. Conflict Detection: If multiple contradictory records exist for the target date, flags an
       AUTHORITATIVE_CONFLICT for staff review.
    4. Candidate Evidence Selection Cascade (Section 8 Policy Order):
       a. Owner confirmation for this exact date (Highest priority)
       b. Runtime feedback from previous decisions for this date
       c. Historical pattern for this specific holiday in past seasons
       d. Shopping centre opening schedule alignment
       e. Own context pattern / comparable holiday patterns
       f. Peer benchmark aggregated closed share (Lowest priority)
    5. Match Check: If candidate hours match currently displayed hours -> RETAIN (NO_ACTION).
    6. Proposal: Generate SUGGEST proposal with recommended change and priority ranking.
    """
    P10 = POLICY["P10_warning"]
    ev: list[dict] = list(ctx.context_evidence)
    gaps: list[str] = list(ctx.source_gaps)

    # --- current operating-status: possible permanent closure ---
    recent_signals = []
    cutoff_dt = parse_dt(ctx.cutoff)
    for sig in ctx.closure_signals:
        known = parse_dt(sig.get("known_at", "1970-01-01T00:00:00Z"))
        if (
            known < cutoff_dt
            and (cutoff_dt - known).days <= P10["closure_max_age_days"]
        ):
            recent_signals.append(sig)
    recent_signals = list(
        {
            (r.get("source_file"), r.get("source_record")): r for r in recent_signals
        }.values()
    )
    closure = (
        ctx.owner_permanent_closure
        or len(recent_signals) >= P10["independent_closure_signals"]
    )
    if closure and not ctx.already_closed:
        for sig in recent_signals or [
            {
                "source_file": "owner",
                "source_record": "owner-confirmation",
                "summary": "Owner confirmed permanent closure.",
            }
        ]:
            ev.append(
                _evidence(
                    "ev-closure",
                    sig.get("source_file", "reviews.json"),
                    sig.get("source_record", "signal"),
                    "COUNTER",
                    sig.get("summary", "Explicit closure signal."),
                    sig.get("known_at"),
                )
            )
        prio, preasons = _priority(ctx, now, material=True)
        prio = "HIGH" if prio == "ROUTINE" else prio
        return _result(
            "FLAG",
            "STATUS_CONCERN",
            "STAFF_REVIEW",
            "POSSIBLE_PERMANENT_CLOSURE",
            "Independent signals suggest this business may have closed for good.",
            ctx,
            ev,
            gaps,
            prio,
            preasons + ["Credible permanent-closure concern"],
            None,
            None,
        )

    if ctx.already_closed:
        return _result(
            "NO_ACTION",
            "SUPPORTED",
            "RETAIN",
            "ALREADY_CLOSED",
            "Business is already marked closed; no hours outreach is needed.",
            ctx,
            ev,
            gaps,
            "ROUTINE",
            ["Existing closure retained"],
        )
    # --- authoritative conflict between unresolved current-date records ---
    distinct = {canonical_hours_or_raw(c["hours"]) for c in ctx.conflicts}
    if len(distinct) >= 2:
        for c in ctx.conflicts:
            ev.append(
                _evidence(
                    "ev-conflict",
                    "holiday_hours_history.jsonl",
                    c.get("source_record", "record"),
                    "COUNTER",
                    f"Conflicting current-date record: {c['hours']}.",
                    c.get("known_at"),
                    ctx.target_date,
                )
            )
        prio, preasons = _priority(ctx, now, material=True)
        return _result(
            "FLAG",
            "POSSIBLE_ERROR",
            "STAFF_REVIEW",
            "AUTHORITATIVE_CONFLICT",
            "Two authoritative records disagree and cannot be ordered.",
            ctx,
            ev,
            gaps,
            prio,
            preasons + ["Unresolved authoritative conflict"],
            None,
            None,
        )

    # --- candidate selection ---
    cand = _select_candidate(ctx, ev)
    if cand is None:
        gaps.append(
            "No applicable owner confirmation or own same-day history at cutoff."
        )
        if ctx.analytics_views is None:
            gaps.append("Search analytics unavailable (treated as unknown, not zero).")
        prio, preasons = _priority(ctx, now, material=False)
        return _result(
            "NO_ACTION",
            "INSUFFICIENT",
            "DEFER",
            "INSUFFICIENT_EVIDENCE",
            "Not enough evidence to propose exact hours; deferred for recheck.",
            ctx,
            ev,
            gaps,
            "ROUTINE",
            ["Insufficient evidence"],
            recheck="New owner entry, publisher suggestion, or peer data for this day_key.",
            change=None,
        )

    cand_hours = canonical_hours(cand["hours"])
    displayed = canonical_hours_or_raw(ctx.displayed_hours)
    if cand_hours == displayed:
        return _result(
            "NO_ACTION",
            "SUPPORTED",
            "RETAIN",
            "CURRENT_HOURS_SUPPORTED",
            "Current hours already match the latest applicable evidence.",
            ctx,
            ev,
            gaps,
            "ROUTINE",
            ["Current hours supported"],
            None,
            None,
        )

    # material correction -> SUGGEST
    finding = (
        "MISSING_EXCEPTION"
        if ctx.displayed_hours
        and cand["reason_code"] == "HISTORY_PATTERN"
        and ctx.day_type
        in ("PUBLIC_HOLIDAY", "EVE", "OBSERVANCE", "COMMERCIAL", "BETWEEN_HOLIDAYS")
        else "POSSIBLE_ERROR"
    )
    if cand["purpose"] == "OPPORTUNITY":
        finding = "OPPORTUNITY"
    material = cand["purpose"] == "CORRECTION"
    prio, preasons = _priority(ctx, now, material)
    change = {"kind": "DATE_HOURS", "date": ctx.target_date, "hours": cand_hours}
    reason = _reason_text(cand, ctx, cand_hours, displayed)
    return _result(
        "SUGGEST",
        finding,
        "PROPOSAL_READY",
        cand["reason_code"],
        reason,
        ctx,
        ev,
        gaps,
        prio,
        preasons,
        change=change,
        cand=cand,
    )


def _reason_text(
    cand: dict, ctx: DetectContext, cand_hours: str, displayed: str
) -> str:
    human = "closed" if cand_hours == "closed" else cand_hours
    shown = "closed" if displayed == "closed" else displayed
    base = {
        "OWNER_CONFIRMED": f"You confirmed {human} for {ctx.target_date}; the listing still shows {shown}.",
        "FEEDBACK_REUSE": f"You previously confirmed {human} for this day; the listing still shows {shown}.",
        "HISTORY_PATTERN": f"A previous confirmed entry for this holiday was {human}, but no exception is entered for {ctx.target_date} "
        f"(currently {shown}).",
        "CENTRE_ALIGNED": f"The shopping centre is {human} that day and your history aligns; the listing shows {shown}.",
        "PEER_CLOSED": f"Comparable businesses are {human} that day; the listing shows {shown}.",
    }
    return base.get(cand["reason_code"], f"Suggested {human}; currently {shown}.")


def _result(
    action,
    finding,
    status,
    reason_code,
    summary,
    ctx,
    ev,
    gaps,
    priority,
    priority_reasons,
    change=None,
    cand=None,
    recheck=None,
) -> dict:
    detection = {
        "schema_version": 1,
        "detection_id": None,
        "entity_id": ctx.entity_id,
        "target_date": ctx.target_date,
        "timezone": ctx.timezone,
        "day_key": ctx.day_key,
        "cutoff": ctx.cutoff,
        "baseline": {
            "kind": "DATE_HOURS",
            "date": ctx.target_date,
            "hours": canonical_hours_or_raw(ctx.displayed_hours),
        },
        "baseline_hash": relevant_state_hash(ctx.displayed_hours),
        "finding": finding,
        "profile": (cand or {}).get(
            "profile", "LIMITED" if action == "NO_ACTION" else "PARTIAL"
        ),
        "evidence": ev,
        "gaps": gaps,
        "priority": priority,
        "priority_reasons": priority_reasons,
    }
    out = {
        "action": action,
        "status": status,
        "reason_code": reason_code,
        "summary": summary,
        "detection": detection,
        "change": change,
        "recheck": recheck,
    }
    if cand:
        out["confidence"] = cand["confidence"]
        out["purpose"] = cand["purpose"]
    return out


# ------------------------------------------------------------- NL interpretation

_YES = {
    "fi": ["kyllä", "ok", "hyväksy", "sopii", "joo"],
    "sv": ["ja", "godkänn", "ok"],
    "nb": ["ja", "godkjenn", "ok"],
    "en": ["yes", "approve", "ok", "sounds good", "confirm"],
    "ko": ["네", "승인", "좋아요"],
}
_NO = {
    "fi": ["ei", "ei kiitos", "hylkää"],
    "sv": ["nej", "avböj"],
    "nb": ["nei", "avslå"],
    "en": ["no", "reject", "no thanks", "decline"],
    "ko": ["아니요", "거절"],
}
_CLOSED = {
    "fi": ["kiinni", "suljettu"],
    "sv": ["stängt"],
    "nb": ["stengt"],
    "en": ["closed"],
    "ko": ["휴무", "닫"],
}
_RANGE_RE = re.compile(
    r"(\d{1,2})(?:[:.](\d{2}))?\s*(?:-|–|—|\bto\b)\s*(\d{1,2})(?:[:.](\d{2}))?"
)


def interpret_reply(text: str, language: str, proposal: dict) -> dict:
    """Deterministic NL preview. Never writes. Returns an InterpretResponse dict."""
    raw = (text or "").strip()
    low = raw.lower()
    version = proposal["version"]
    date_s = (
        proposal["change"].get("date")
        if proposal["change"]["kind"] == "DATE_HOURS"
        else None
    )

    if re.search(
        r"\b(maybe|about|around|perhaps|if|not|noin|ehkä|kanske|kanskje)\b|아마|대략|쯤|않",
        low,
    ):
        return _needs("Please confirm an exact, unconditional decision.", ["hours"])
    if re.search(r"\d{4}-\d{2}-\d{2}", low):
        mentioned = re.findall(r"\d{4}-\d{2}-\d{2}", low)
        if any(x != date_s for x in mentioned):
            return _needs("Reply dates do not match this proposal.", ["date"])
        low = re.sub(r"\d{4}-\d{2}-\d{2}", "", low).strip()
    ranges = _RANGE_RE.findall(low)
    # explicit closed edit
    if date_s and any(w in low for w in _CLOSED.get(language, []) + _CLOSED["en"]):
        return _ready_edit(
            proposal, version, date_s, "closed", f"Set {date_s} to closed."
        )
    if date_s and len(ranges) == 1:
        a, am, b, bm = ranges[0]
        hours = f"{int(a):02d}:{am or '00'}-{int(b):02d}:{bm or '00'}"
        try:
            hours = canonical_hours(hours)
        except HoursError:
            return _needs("Could not read a valid time range.", ["hours"])
        return _ready_edit(
            proposal, version, date_s, hours, f"Set {date_s} to {hours}."
        )
    if date_s and len(ranges) > 1 and "," in low:
        try:
            spec = canonical_hours(
                ",".join(
                    f"{int(a):02d}:{am or '00'}-{int(b):02d}:{bm or '00'}"
                    for a, am, b, bm in ranges
                )
            )
            return _ready_edit(
                proposal, version, date_s, spec, f"Set {date_s} to {spec}."
            )
        except HoursError:
            return _needs("The intervals overlap or are invalid.", ["hours"])
    if date_s and len(ranges) > 1:
        return _needs(
            "Multiple times mentioned; please confirm one range or use the editor.",
            ["hours"],
        )
    # vague
    if re.search(
        r"\b(maybe|about|around|noin|kanske|kanskje|대략|쯤)\b", low
    ) or re.search(r"a bit (earlier|later)", low):
        return _needs("The reply is ambiguous; please confirm exact hours.", ["hours"])
    # approve / reject
    if any(
        w == low or low.startswith(w + " ") or low == w
        for w in _NO.get(language, []) + _NO["en"]
    ):
        return {
            "status": "READY",
            "intent": "REJECT",
            "preview": "Reject this suggestion.",
            "decision_draft": {"proposal_version": version, "decision": "REJECT"},
            "missing_fields": [],
        }
    yes_words = _YES.get(language, []) + _YES["en"]
    if low.rstrip(".! ") in yes_words:
        if date_s is None:
            return _needs("Please confirm which date this applies to.", ["date"])
        return {
            "status": "READY",
            "intent": "APPROVE",
            "preview": "Approve the suggested hours.",
            "decision_draft": {"proposal_version": version, "decision": "APPROVE"},
            "missing_fields": [],
        }
    return {
        "status": "UNSUPPORTED",
        "intent": "UNKNOWN",
        "preview": "Could not interpret; use the buttons or state exact hours.",
        "missing_fields": [],
    }


def ready_edit(proposal, version, date_s, hours, preview) -> dict:
    return {
        "status": "READY",
        "intent": "EDIT",
        "preview": preview,
        "decision_draft": {
            "proposal_version": version,
            "decision": "EDIT",
            "edited_change": {"kind": "DATE_HOURS", "date": date_s, "hours": hours},
            "confirmed": True,
        },
        "missing_fields": [],
    }


def needs_clarification(preview, missing) -> dict:
    return {
        "status": "NEEDS_CLARIFICATION",
        "intent": "UNKNOWN",
        "preview": preview,
        "missing_fields": missing,
    }


_ready_edit = ready_edit
_needs = needs_clarification


# ------------------------------------------------------------------- DataStore


class DataError(RuntimeError):
    """Startup failure for a corrupt critical source (entities/calendar/contacts)."""


_PERM_WORDS = (
    "lopettanut",
    "pysyvästi",
    "stängt för gott",
    "permanent",
    "lagt ned",
    "stengt for godt",
    "closed down",
    "closed permanently",
    "out of business",
)


class DataStore:
    """Loads and indexes the synthetic sources. Never reads labels or sim_data."""

    def __init__(self, data_root: str, cutoff: str = None):
        self.root = data_root
        self.cutoff = cutoff or POLICY["P14_evaluation"]["cutoff"]
        self.cutoff_dt = parse_dt(self.cutoff)
        self._load()

    def _path(self, name: str) -> str:
        return os.path.join(self.root, name)

    def _load(self):
        self.unavailable = []

        def read(name, kind, critical=False):
            required = {
                "holiday_hours_history.jsonl": (
                    "entity_id",
                    "date",
                    "entered_at",
                    "holidayHours",
                ),
                "regular_hours_history.jsonl": ("entity_id", "effective_from", "hours"),
                "peer_benchmarks.csv": ("country", "city_tier", "segment", "day_key"),
                "cities.csv": ("city", "city_tier"),
                "pilot_decision_log_2025.csv": (
                    "entity_id",
                    "date",
                    "day_key",
                    "decision",
                ),
                "school_breaks.csv": ("country", "start", "end"),
                "weather_daily.csv": ("city", "date", "is_forecast"),
            }
            shapes = {
                "listings.json": ("listings",),
                "reviews.json": ("response", "reviews"),
                "publisher_suggestions.json": ("response", "suggestions"),
                "local_events.json": ("data",),
            }
            row_keys = {
                "listings.json": ("entityId", "publisherId"),
                "reviews.json": ("locationId", "id", "publisherDate"),
                "publisher_suggestions.json": ("locationId", "id", "fieldName"),
                "local_events.json": ("@id", "start_time"),
            }
            try:
                with open(self._path(name), encoding="utf-8") as f:
                    result = (
                        json.load(f)
                        if kind == "json"
                        else [json.loads(line) for line in f if line.strip()]
                        if kind == "jsonl"
                        else list(csv.DictReader(f))
                    )
                rows = result
                for part in shapes.get(name, ()):
                    rows = rows[part]
                keys = required.get(name, row_keys.get(name, ()))
                if keys and (
                    not isinstance(rows, list)
                    or any(
                        not isinstance(row, dict) or any(key not in row for key in keys)
                        for row in rows
                    )
                ):
                    raise ValueError()
                if name == "holiday_hours_history.jsonl":
                    for row in rows:
                        parse_dt(row["entered_at"])
                        date.fromisoformat(row["date"])
                return result
            except (OSError, ValueError, KeyError, TypeError):
                if critical:
                    raise DataError(name + " is missing or corrupt") from None
                self.unavailable.append(name)
                return {} if kind == "json" else []

        self._load_critical_sources(read)
    def _load_critical_sources(self, read):
        try:
            ents = read("entities.json", "json", True)["response"]["entities"]
            if not ents or any(
                not e.get("meta", {}).get("id")
                or not e.get("hours")
                or e["meta"].get("countryCode") not in ("FI", "SE", "NO")
                for e in ents
            ):
                raise ValueError()
            for entity in ents:
                for day in DAYS:
                    if day in entity["hours"]:
                        canonical_hours(day_to_hours_string(entity["hours"][day]))
            self.entities = {e["meta"]["id"]: e for e in ents}
            self.order = list(self.entities)
            self.calendar = read("calendar_special_days.csv", "csv", True)
            if not self.calendar or any(
                not all(
                    r.get(k)
                    for k in ("country", "date", "day_key", "day_type", "day_class")
                )
                for r in self.calendar
            ):
                raise ValueError()
            contacts = read("customer_contacts.csv", "csv", True)
            if not contacts or any(
                not all(
                    r.get(k)
                    for k in (
                        "entity_id",
                        "preferred_channel",
                        "preferred_language",
                        "best_contact_window",
                    )
                )
                for r in contacts
            ):
                raise ValueError()
            self.contacts = {r["entity_id"]: r for r in contacts}
        except (KeyError, ValueError, TypeError):
            raise DataError(
                "Malformed critical entities/calendar/contacts source"
            ) from None

        self.holiday = {}
        self.regular = {}
        self.pilot = {}
        self.listings = {}
        for r in read("holiday_hours_history.jsonl", "jsonl"):
            self.holiday.setdefault((r["entity_id"], r["date"]), []).append(r)
        self.history_entities = {eid for eid, _ in self.holiday}
        self.holiday_by_entity = {}
        for (eid, day), rows in self.holiday.items():
            self.holiday_by_entity.setdefault(eid, []).append((day, rows))
        for r in read("regular_hours_history.jsonl", "jsonl"):
            self.regular.setdefault(r["entity_id"], []).append(r)
        self.cal_by_date = {(r["country"], r["date"]): r for r in self.calendar}
        self.dates_by_key = {}
        for r in self.calendar:
            self.dates_by_key.setdefault((r["country"], r["day_key"]), []).append(
                r["date"]
            )
        self.bench = {
            (r["country"], r["city_tier"], r["segment"], r["day_key"]): r
            for r in read("peer_benchmarks.csv", "csv")
        }
        self.tiers = {r["city"]: r["city_tier"] for r in read("cities.csv", "csv")}
        for r in read("pilot_decision_log_2025.csv", "csv"):
            self.pilot.setdefault((r["entity_id"], r["day_key"]), []).append(r)
        for r in read("listings.json", "json").get("listings", []):
            self.listings.setdefault(r["entityId"], []).append(r)
        self.reviews = (
            read("reviews.json", "json").get("response", {}).get("reviews", [])
        )
        self.publisher_suggestions = (
            read("publisher_suggestions.json", "json")
            .get("response", {})
            .get("suggestions", [])
        )
        self.events = read("local_events.json", "json").get("data", [])
        self.events_by_day = {}
        for ev in self.events:
            self.events_by_day.setdefault(
                (ev.get("x_country"), ev.get("start_time", "")[:10]), []
            ).append(ev)
        self.school = read("school_breaks.csv", "csv")
        self.weather = read("weather_daily.csv", "csv")
        self.weather_normals = read("weather_normals.csv", "csv")
        self.weather_by_day = {(r["city"], r["date"]): r for r in self.weather}
        self._closure = None
        self._analytics = None
        self._neighbour_ids = {}

    # -- derived views ----------------------------------------------------
    def entity(self, eid: str) -> Optional[dict]:
        return self.entities.get(eid)

    def _effective_regular_hours_dict(
        self, eid: str, limit_date: str, inclusive: bool = True
    ) -> dict:
        eligible = [
            r
            for r in self.regular.get(eid, [])
            if r["effective_from"] == "before-2024"
            or (
                r["effective_from"] <= limit_date
                if inclusive
                else r["effective_from"] < limit_date
            )
        ]
        if not eligible:
            return self.entities[eid].get("hours", {})
        return max(
            eligible,
            key=lambda r: "0000-00-00"
            if r["effective_from"] == "before-2024"
            else r["effective_from"],
        )["hours"]

    def regular_hours(self, eid: str, d: date) -> str:
        hours_dict = self._effective_regular_hours_dict(
            eid, self.cutoff[:10], inclusive=False
        )
        return canonical_hours(
            day_to_hours_string(hours_dict.get(DAYS[d.weekday()]))
        )

    def holiday_entry(self, eid: str, d: date, as_of: datetime) -> Optional[str]:
        rows = [
            r
            for r in self.holiday.get((eid, d.isoformat()), [])
            if parse_dt(r["entered_at"]) < as_of
        ]
        if not rows:
            return None
        h = max(rows, key=lambda r: parse_dt(r["entered_at"]))["holidayHours"]
        return (
            "REGULAR"
            if h.get("isRegularHours")
            else canonical_hours(day_to_hours_string(h))
        )

    def displayed_hours(self, eid: str, d: date) -> str:
        e = self.holiday_entry(eid, d, self.cutoff_dt)
        if e is None or e == "REGULAR":
            return self.regular_hours(eid, d)
        return e

    def closure_signals(self, eid: str):
        if self._closure is None:
            self._build_closure()
        return self._closure.get(eid, [])

    def _build_closure(self):
        self._closure = {}
        for r in self.reviews:
            known = datetime.fromtimestamp(
                (r.get("publisherDate") or 0) / 1000, tz=timezone.utc
            )
            if timedelta(0) < self.cutoff_dt - known <= timedelta(days=150) and any(
                w in (r.get("content") or "").lower() for w in _PERM_WORDS
            ):
                self._closure.setdefault(r["locationId"], []).append(
                    dict(
                        source_file="reviews.json",
                        source_record=str(r["id"]),
                        summary=r.get("content", "")[:350],
                        known_at=iso_utc(known),
                    )
                )
        for row in self.publisher_suggestions:
            if row.get("fieldName") != "closed" or row.get("status") != "ACCEPTED":
                continue
            try:
                content = json.loads(row.get("suggestedContent", "{}"))
                known = parse_dt(row.get("dateResolved") or row["dateCreated"])
                closed = (
                    content is True
                    or isinstance(content, dict)
                    and content.get("closed") is True
                )
            except (ValueError, TypeError):
                continue
            if closed and timedelta(0) < self.cutoff_dt - known <= timedelta(days=150):
                self._closure.setdefault(row["locationId"], []).append(
                    dict(
                        source_file="publisher_suggestions.json",
                        source_record=row["id"],
                        summary="Accepted permanent closure suggestion.",
                        known_at=iso_utc(known),
                        owner=row.get("resolvedBy") == "OWNER",
                    )
                )

    def context(
        self, eid: str, target: str, day_key: str, day_type: str
    ) -> DetectContext:
        """Build a cutoff-limited DetectContext from the real sources (no feedback)."""
        e = self.entities[eid]
        country = e["meta"]["countryCode"]
        d = date.fromisoformat(target)
        displayed = self.displayed_hours(eid, d)

        own_history = []
        prior_dates = [
            x for x in self.dates_by_key.get((country, day_key), []) if x < target
        ]
        for pd in sorted(set(prior_dates), reverse=True):
            if (
                not 0
                <= d.year - date.fromisoformat(pd).year
                <= POLICY["P09_evidence"]["history_seasons"]
            ):
                continue
            val = self.holiday_entry(eid, date.fromisoformat(pd), self.cutoff_dt)
            if val:
                val = self.regular_hours(eid, d) if val == "REGULAR" else val
                rows = [
                    r
                    for r in self.holiday.get((eid, pd), [])
                    if parse_dt(r["entered_at"]) < self.cutoff_dt
                ]
                if not self.same_week(eid, pd, target):
                    continue
                entered = iso_utc(max(parse_dt(r["entered_at"]) for r in rows))
                own_history.append(
                    {
                        "date": pd,
                        "hours": val,
                        "entered_at": entered,
                        "source_record": f"{eid}/{pd}/latest-before-cutoff",
                    }
                )

        pilot_finals = []
        for r in self.pilot.get((eid, day_key), []):
            if (
                r.get("decided_at")
                and parse_dt(r["decided_at"]) < self.cutoff_dt
                and r["date"] < target
                and self.same_week(eid, r["date"], target)
            ):
                pilot_finals.append(
                    {
                        "date": r["date"],
                        "decision": r["decision"],
                        "final_hours": (r.get("final_hours") or "").strip(),
                        "decided_at": iso_utc(parse_dt(r["decided_at"])),
                        "suggestion_id": r.get("suggestion_id"),
                    }
                )

        centre = None
        mall = e.get("c_shoppingCenterEntityId")
        if mall and mall in self.entities:
            tval = self.holiday_entry(mall, d, self.cutoff_dt)
            if tval and tval != "REGULAR":
                match, agree = self._centre_alignment(eid, mall, country, day_key)
                centre = {
                    "name": self.entities[mall].get("name", mall),
                    "entity_id": mall,
                    "target_hours": tval,
                    "match_dates": match,
                    "agreement": agree,
                }

        peer = None
        tier = self.tiers.get(e.get("address", {}).get("city"))
        b = (
            self.bench.get((country, tier, e.get("c_segment"), day_key))
            if tier
            else None
        )
        if b:
            try:
                peer = {
                    "closed_share": float(b.get("closed_share_among_entered") or 0),
                    "n_entity_days": int(float(b.get("n_entity_days") or 0)),
                    "corroborated": False,
                }
            except ValueError:
                peer = None

        ctx = DetectContext(
            entity_id=eid,
            business_name=e.get("name", eid),
            timezone=e.get("timezone", "Europe/Helsinki"),
            country=country,
            segment=e.get("c_segment", ""),
            target_date=target,
            day_key=day_key,
            day_type=day_type,
            cutoff=self.cutoff,
            displayed_hours=displayed,
            already_closed=bool(e.get("closed")),
            own_history=own_history,
            pilot_finals=pilot_finals,
            centre=centre,
            peer=peer,
            closure_signals=self.closure_signals(eid),
            analytics_views=None,
            search_percentile=None,
        )
        current = [
            r
            for r in self.holiday.get((eid, target), [])
            if parse_dt(r["entered_at"]) < self.cutoff_dt
        ]
        if current:
            latest = max(parse_dt(r["entered_at"]) for r in current)
            same = [r for r in current if parse_dt(r["entered_at"]) == latest]
            vals = {
                self.regular_hours(eid, d)
                if r["holidayHours"].get("isRegularHours")
                else day_to_hours_string(r["holidayHours"])
                for r in same
            }
            if len(vals) > 1:
                ctx.conflicts = [
                    dict(
                        hours=v,
                        known_at=iso_utc(latest),
                        source_record=eid + "/" + target + "/" + str(i),
                    )
                    for i, v in enumerate(sorted(vals))
                ]
            else:
                ctx.owner_confirmation = dict(
                    hours=next(iter(vals)),
                    known_at=iso_utc(latest),
                    source_record=eid + "/" + target + "/latest",
                )
        ctx.owner_permanent_closure = any(x.get("owner") for x in ctx.closure_signals)
        target_cal = self.cal_by_date.get((country, target), {})
        for hd, rows in self.holiday_by_entity.get(eid, []):
            if hd >= target or d.year - date.fromisoformat(hd).year > 3:
                continue
            cal = self.cal_by_date.get((country, hd), {})
            if (
                not target_cal.get("day_class")
                or cal.get("day_class") != target_cal["day_class"]
                or (date.fromisoformat(hd).weekday() >= 5) != (d.weekday() >= 5)
            ):
                continue
            if not self.same_week(eid, hd, target):
                continue
            val = self.holiday_entry(eid, date.fromisoformat(hd), self.cutoff_dt)
            eligible = [r for r in rows if parse_dt(r["entered_at"]) < self.cutoff_dt]
            if val and val != "REGULAR" and eligible:
                ctx.comparable.append(
                    dict(
                        date=hd,
                        hours=val,
                        entered_at=iso_utc(
                            max(parse_dt(r["entered_at"]) for r in eligible)
                        ),
                        source_record=eid + "/" + hd,
                    )
                )
        ctx.source_gaps = ["SOURCE_UNAVAILABLE: " + name for name in self.unavailable]
        self.add_context(ctx, e)
        if not ctx.owner_confirmation and not ctx.own_history:
            self.neighbour_context(ctx, e)
        metrics = self.analytics().get(eid)
        if metrics:
            ctx.analytics_views, ctx.search_percentile = metrics
        return ctx

    def _centre_alignment(
        self, eid: str, mall: str, country: str, day_key: str
    ) -> tuple[int, float]:
        match = total = 0
        for pd in self.dates_by_key.get((country, day_key), []):
            if pd >= self.cutoff[:10]:
                continue
            m = self.holiday_entry(mall, date.fromisoformat(pd), self.cutoff_dt)
            o = self.holiday_entry(eid, date.fromisoformat(pd), self.cutoff_dt)
            if m and m != "REGULAR" and o and o != "REGULAR":
                total += 1
                if hours_equal(m, o):
                    match += 1
        return (total, match / total if total else 0.0)

    def contact(self, eid: str) -> dict:
        return self.contacts.get(eid, {})

    def publishers_for(self, eid: str) -> list[dict]:
        return self.listings.get(eid, [])

    def same_week(self, eid, old, target):
        limit = self.cutoff[:10]
        old_hours = self._effective_regular_hours_dict(
            eid, min(old, limit), inclusive=True
        )
        target_hours = self._effective_regular_hours_dict(
            eid, min(target, limit), inclusive=True
        )
        return all(
            day_to_hours_string(old_hours.get(w))
            == day_to_hours_string(target_hours.get(w))
            for w in DAYS
        )

    def add_context(self, ctx, e):
        # Context is always supplementary. It never supplies exact hours on its own.
        city = e.get("address", {}).get("city", "")
        geo = e.get("geocodedCoordinate") or e.get("displayCoordinate") or {}
        lat, lon = geo.get("latitude"), geo.get("longitude")

        def nearby(event):
            point = event.get("location", {}).get("position", {}).get("coordinates", [])
            if lat is None or lon is None or len(point) != 2:
                return False
            return haversine_distance(lat, lon, point[1], point[0]) <= 1000

        if ctx.segment in ("restaurant", "lunch_restaurant", "pizzeria", "bar_pub"):
            for event in self.events_by_day.get((ctx.country, ctx.target_date), []):
                if (
                    event.get("start_time", "")[:10] == ctx.target_date
                    and event.get("x_country") == ctx.country
                    and nearby(event)
                ):
                    self.event_pattern(ctx, e, event, nearby)
                    ctx.context_evidence.append(
                        _evidence(
                            "event-" + event["@id"],
                            "local_events.json",
                            event["@id"],
                            "CONTEXT",
                            "Nearby event may affect demand; exact hours need own comparable events.",
                            self.cutoff,
                            ctx.target_date,
                        )
                    )
        if ctx.segment in ("indoor_playground", "ski_rental"):
            for r in self.school:
                if (
                    r["country"] == ctx.country
                    and r["start"] <= ctx.target_date <= r["end"]
                ):
                    ctx.context_evidence.append(
                        _evidence(
                            "school-" + r["start"],
                            "school_breaks.csv",
                            r["start"],
                            "CONTEXT",
                            "Approximate school break; municipality and business relevance need confirmation.",
                            self.cutoff,
                            ctx.target_date,
                        )
                    )
        if ctx.segment in ("ski_rental", "seasonal_terrace"):
            for r in [self.weather_by_day.get((city, ctx.target_date), {})]:
                if (
                    r
                    and r["city"] == city
                    and r["date"] == ctx.target_date
                    and r.get("is_forecast") == "1"
                ):
                    ctx.context_evidence.append(
                        _evidence(
                            "weather-" + ctx.target_date,
                            "weather_daily.csv",
                            city + "/" + ctx.target_date,
                            "CONTEXT",
                            "Dated forecast available; rain or climate normals alone do not justify changing hours.",
                            self.cutoff,
                            ctx.target_date,
                        )
                    )

    def analytics(self):
        if self._analytics is not None:
            return self._analytics
        self._analytics = {}
        try:
            import pyarrow.parquet as pq

            end = self.cutoff_dt.date()
            start = end - timedelta(days=28)
            table = pq.read_table(
                self._path("analytics_daily.parquet"),
                columns=["entity_id", "date", "GOOGLE_SEARCH_VIEWS"],
                filters=[("date", ">=", start), ("date", "<", end)],
            )
            frame = table.to_pandas()
            groups = frame.groupby("entity_id")["GOOGLE_SEARCH_VIEWS"].sum(min_count=1)
            ranks = groups.rank(pct=True) * 100
            self._analytics = {
                eid: (float(v), float(ranks[eid]))
                for eid, v in groups.items()
                if v == v
            }
        except (ImportError, OSError, ValueError, KeyError):
            if "analytics_daily.parquet" not in self.unavailable:
                self.unavailable.append("analytics_daily.parquet")
        return self._analytics

    def event_pattern(self, ctx, e, event, nearby):
        # A dated exception on two similar local events supplies exact times; attendance alone does not.
        rows = []
        for previous in self.events:
            old = previous.get("start_time", "")[:10]
            if (
                not old
                or old >= min(ctx.target_date, self.cutoff[:10])
                or previous.get("x_country") != ctx.country
            ):
                continue
            if not set(previous.get("keywords", [])) & set(
                event.get("keywords", [])
            ) or not nearby(previous):
                continue
            if not self.same_week(ctx.entity_id, old, ctx.target_date):
                continue
            value = self.holiday_entry(
                ctx.entity_id, date.fromisoformat(old), self.cutoff_dt
            )
            if value and value not in ("closed", "REGULAR"):
                rows.append((old, value, previous["@id"]))
        unique = {day: (hours, ref) for day, hours, ref in rows}
        patterns = {}
        for day, (hours, ref) in unique.items():
            patterns.setdefault(hours, []).append((day, ref))
        eligible = [(hours, rows) for hours, rows in patterns.items() if len(rows) >= 2]
        if len(eligible) != 1:
            return
        hours, rows = eligible[0]
        duration = lambda v: sum(b - a for a, b in parse_intervals(v))
        if duration(hours) <= duration(ctx.displayed_hours):
            return
        ctx.opportunity = {
            "hours": hours,
            "evidence": [
                _evidence(
                    "event-pattern-" + day,
                    "holiday_hours_history.jsonl",
                    ctx.entity_id + "/" + day,
                    "DIRECT",
                    "Own confirmed exception on a similar nearby event (" + ref + ").",
                    self.cutoff,
                    day,
                )
                for day, ref in rows
            ],
        }

    def neighbour_context(self, ctx, entity):
        coord = entity.get("geocodedCoordinate", {})
        if not all(k in coord for k in ("latitude", "longitude")):
            return
        if ctx.entity_id not in self._neighbour_ids:
            found = []
            for eid, other in self.entities.items():
                point = other.get("geocodedCoordinate", {})
                if (
                    eid == ctx.entity_id
                    or other.get("c_segment") != ctx.segment
                    or other.get("meta", {}).get("countryCode") != ctx.country
                    or not all(k in point for k in ("latitude", "longitude"))
                ):
                    continue
                distance = haversine_distance(
                    coord["latitude"], coord["longitude"], point["latitude"], point["longitude"]
                )
                if distance <= 1000:
                    found.append((distance, eid))
            self._neighbour_ids[ctx.entity_id] = [eid for _, eid in sorted(found)]
        ids = self._neighbour_ids[ctx.entity_id]
        if len(ids) >= 3:
            ctx.context_evidence.append(
                _evidence(
                    "neighbours",
                    "entities.json",
                    ",".join(ids[:3]),
                    "SUPPLEMENTARY",
                    "At least three nearby same-segment businesses are available for comparison. Their independent schedules do not determine this business’s hours.",
                    self.cutoff,
                    ctx.target_date,
                )
            )
