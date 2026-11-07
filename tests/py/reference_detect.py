"""TEST DOUBLE - not application code.

The repository has no Detect layer (see tests/DETECT_QA_REPORT.md, gap G1). This minimal, deterministic
implementation of the A-J contract exists for ONE reason: to prove that the contract tests in
test_detect_contract.py are executable and internally consistent. Run them against it with

    DETECT_IMPL=reference pytest tests/py/test_detect_contract.py

When the team adds a real `examples/detect.py` exposing the same two functions, the same tests run against it
with no env var (they skip while the module is absent). Thresholds below are placeholders: the PDF says they are
"not final", so tests avoid boundary values.

Contract
    build_profile(tables, entity_id, cutoff)                     -> dict   (steps B-C)
    run_case(tables, entity_id, target_date, cutoff, trigger=None) -> dict   (steps D-J, the handoff)
This module never returns a proposed/suggested hours value: choosing hours is Suggest's job.
"""
from __future__ import annotations

from datetime import date, datetime

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PERM_WORDS = ("lopettanut", "pysyvästi", "stängt för gott", "permanent", "lagt ned", "stengt for godt", "closed down")
STRONG_MIN_DAY_KEYS = 4        # placeholder threshold
PEER_MIN_N, PEER_CLOSED_SHARE, PEER_ENTERED_SHARE = 30, 0.7, 0.15
CENTRE_MIN_COMPARABLE, CENTRE_MIN_AGREEMENT = 3, 0.7
WARNING_WINDOW_DAYS = 150


def _s(h):
    if h.get("isRegularHours"):
        return "REGULAR"
    if h.get("isClosed") or not h.get("openIntervals"):
        return "closed"
    return ",".join(f"{i['start']}-{i['end']}" for i in h["openIntervals"])


def _ev(role, kind, source, content, applicable, entered, ref, differs=None, inference=False, **extra):
    return {"role": role, "kind": kind, "source": source, "content": content, "applicable_date": applicable,
            "entered_at": entered, "ref": ref, "differs_from_displayed": differs, "is_inference": inference, **extra}


def _latest_per_date(rows):
    best = {}
    for r in rows:
        if r["date"] not in best or r["entered_at"] > best[r["date"]]["entered_at"]:
            best[r["date"]] = r
    return list(best.values())


def _own(t, eid, cutoff):
    return _latest_per_date([r for r in t["holiday_history"]
                             if r["entity_id"] == eid and r["entered_at"] < cutoff.isoformat()])


def _confirmations(t, eid, cutoff):
    return [r for r in t["pilot_log"] if r["entity_id"] == eid and r.get("decision") in ("ACCEPTED", "EDITED")
            and r.get("decided_at") and r["decided_at"] < cutoff.isoformat() and r.get("final_hours")]


# ------------------------------------------------------------------------- B-C
def build_profile(t, eid, cutoff):
    own = _own(t, eid, cutoff)
    keys = sorted({r["day_key"] for r in own})
    conf = _confirmations(t, eid, cutoff)
    centre = t["entities"][eid].get("c_shoppingCenterEntityId")
    path = "strong" if (conf or len(keys) >= STRONG_MIN_DAY_KEYS) else ("partial" if own else "limited")
    return {"entity_id": eid, "path": path, "own_covered_day_keys": keys,
            "own_latest_entry": max((r["entered_at"] for r in own), default=None),
            "owner_confirmations": len(conf), "centre_id": centre, "as_of": cutoff.isoformat()}


# ------------------------------------------------------------------------- state
def displayed_state(t, eid, d, cutoff):
    hrs = t["entities"][eid]["hours"]
    regular = _s(hrs.get(DAYS[d.weekday()], {"isClosed": True}))
    exc = next((h for h in hrs.get("holidayHours", []) if h.get("date") == d.isoformat()), None)
    vers = [r["effective_from"] for r in t["regular_history"] if r["entity_id"] == eid
            and (r["effective_from"] == "before-2024" or r["effective_from"] < cutoff.isoformat())]
    ver = max(vers, key=lambda x: "0000" if x == "before-2024" else x, default=None)
    if exc:
        h = regular if exc.get("isRegularHours") else _s(exc)
        return {"hours": h, "source": "exception", "regular_hours": regular,
                "regular_schedule_version": ver, "exception_version": exc["date"]}
    return {"hours": regular, "source": "regular", "regular_hours": regular,
            "regular_schedule_version": ver, "exception_version": None}


# ------------------------------------------------------------------------- evidence
def _direct(t, eid, key, d, cutoff, disp):
    out = []
    for r in _own(t, eid, cutoff):
        if r["day_key"] == key and r["date"] < d.isoformat():
            c = _s(r["holidayHours"])
            c = disp["regular_hours"] if c == "REGULAR" else c
            out.append(_ev("direct", "own_matching_holiday", "holiday_hours_history.jsonl", c, r["date"],
                           r["entered_at"], f"hol:{eid}:{r['date']}", c != disp["hours"]))
    for r in _confirmations(t, eid, cutoff):
        if r["day_key"] == key:
            out.append(_ev("direct", "owner_confirmation", "pilot_decision_log_2025.csv", r["final_hours"], r["date"],
                           r["decided_at"], f"pilot:{r['suggestion_id']}", r["final_hours"] != disp["hours"]))
    return sorted(out, key=lambda e: e["applicable_date"], reverse=True)


def _warnings(t, eid, d, cutoff, direct):
    out, ms = [], datetime(cutoff.year, cutoff.month, cutoff.day).timestamp() * 1000
    for r in t["reviews"]:
        if r["locationId"] == eid and ms - WARNING_WINDOW_DAYS * 86400000 < r["publisherDate"] < ms \
                and any(w in r["content"].lower() for w in PERM_WORDS):
            iso = datetime.fromtimestamp(r["publisherDate"] / 1000).isoformat()
            out.append(_ev("counter_warning", "closure_mention", "reviews.json", r["content"], None, iso,
                           f"review:{iso}"))
    for s in t["suggestions"]:
        if s["locationId"] != eid or s["status"] != "WAITING_ON_CUSTOMER" or s["dateCreated"] >= cutoff.isoformat():
            continue
        if s["fieldName"] == "closed":
            out.append(_ev("counter_warning", "closure_mention", "publisher_suggestions.json", s["suggestedContent"],
                           None, s["dateCreated"], f"ps:{s.get('id', s['dateCreated'])}"))
            continue
        import json
        for item in json.loads(s["suggestedContent"]).get("holidayHours", []):
            if item.get("date") == d.isoformat() and direct and _s(item) != direct[0]["content"]:
                out.append(_ev("counter_warning", "conflicting_hours_suggestion", "publisher_suggestions.json",
                               _s(item), d.isoformat(), s["dateCreated"], f"ps:{s.get('id', s['dateCreated'])}"))
    return out


def _other_holidays(t, eid, key, d, cutoff, disp):
    ent = t["entities"][eid]
    exc = []
    for r in _own(t, eid, cutoff):
        if r["day_key"] == key:
            continue
        reg = _s(ent["hours"].get(DAYS[date.fromisoformat(r["date"]).weekday()], {"isClosed": True}))
        if _s(r["holidayHours"]) not in (reg, "REGULAR"):
            exc.append(r)
    if len(exc) < 2:
        return []
    return [_ev("supplementary", "own_other_holidays", "holiday_hours_history.jsonl",
                f"{len(exc)} other holidays entered with non-regular hours", None,
                max(r["entered_at"] for r in exc), f"hol-pattern:{eid}", True, inference=True)]


def _centre(t, eid, d, cutoff, disp):
    cid = t["entities"][eid].get("c_shoppingCenterEntityId")
    if not cid or cid not in t["entities"]:
        return []
    exc = next((h for h in t["entities"][cid]["hours"].get("holidayHours", []) if h.get("date") == d.isoformat()), None)
    if not exc:
        return []
    mine = {r["date"]: _s(r["holidayHours"]) for r in _own(t, eid, cutoff)}
    theirs = {r["date"]: _s(r["holidayHours"]) for r in _own(t, cid, cutoff)}
    both = [x for x in mine if x in theirs]
    agree = (sum(mine[x] == theirs[x] for x in both) / len(both)) if both else None
    strength = "moderate" if (len(both) >= CENTRE_MIN_COMPARABLE and agree is not None
                              and agree >= CENTRE_MIN_AGREEMENT) else "weak"
    return [_ev("supplementary", "shopping_centre", "entities.json", _s(exc), d.isoformat(), t["entities"][cid]["meta"].get("timestamp"),
                f"centre:{cid}:{d.isoformat()}", _s(exc) != disp["hours"], strength=strength,
                centre_agreement=agree, comparable_dates=len(both))]


def _peers(t, eid, key):
    ent = t["entities"][eid]
    for r in t["peers"]:
        if r["country"] == ent["meta"]["countryCode"] and r["segment"] == ent["c_segment"] and r["day_key"] == key \
                and int(r["n_entity_days"]) >= PEER_MIN_N and float(r["closed_share_among_entered"] or 0) >= PEER_CLOSED_SHARE \
                and float(r["share_entered_closed"] or 0) >= PEER_ENTERED_SHARE:
            return [_ev("supplementary", "peer_benchmark", "peer_benchmarks.csv",
                        f"{float(r['closed_share_among_entered']):.0%} of peers that entered the day were closed", None, None,
                        f"peer:{r['segment']}:{key}", None, inference=True, n_entity_days=int(r["n_entity_days"]))]
    return []


def _events(t, eid, d):
    ent = t["entities"][eid]
    return [_ev("contextual", "event", "local_events.json", e["@id"], d.isoformat(), None, f"event:{e['@id']}", False)
            for e in t["events"] if e["start_time"][:10] == d.isoformat()
            and e["location"]["address_locality"] == ent["address"]["city"]]


# ------------------------------------------------------------------------- D-J
FINDING_ROUTE = {"possible_error_omission": "suggest_review", "new_trading_opportunity": "suggest_review",
                 "state_aligned": "retain", "insufficient_evidence": "defer", "material_conflict": "staff_review"}


def run_case(t, eid, target, cutoff, trigger=None):
    ent = t["entities"][eid]
    cal = next((r for r in t["calendar"] if r["country"] == ent["meta"]["countryCode"] and r["date"] == target.isoformat()), None)
    key = cal["day_key"] if cal else None
    prof = build_profile(t, eid, cutoff)
    disp = displayed_state(t, eid, target, cutoff)
    direct = _direct(t, eid, key, target, cutoff, disp)
    warns = _warnings(t, eid, target, cutoff, direct)
    # E: routing
    if prof["path"] == "limited":
        trace = ["H"]
    elif prof["path"] == "partial":
        trace = ["G"]
    elif direct and not warns:
        trace = ["F"]
    else:
        trace = ["F", "G"]
    supp, ctx = [], []
    if "G" in trace:
        supp += _centre(t, eid, target, cutoff, disp) + (_other_holidays(t, eid, key, target, cutoff, disp) if not direct else [])
    if "H" in trace:
        supp += _centre(t, eid, target, cutoff, disp) + _peers(t, eid, key)
    if "G" in trace or "H" in trace:
        ctx = _events(t, eid, target)
    evidence = direct + supp + ctx + warns
    # I: synthesis
    if warns:
        ftype = "material_conflict"
    elif direct:
        ftype = "possible_error_omission" if direct[0]["differs_from_displayed"] else "state_aligned"
        if ftype == "state_aligned" and any(e["differs_from_displayed"] for e in supp):
            ftype = "possible_error_omission"
    elif supp:
        ftype = "possible_error_omission" if any(e["differs_from_displayed"] is not False for e in supp) else "state_aligned"
    elif ctx:
        ftype = "new_trading_opportunity"
    else:
        ftype = "insufficient_evidence"
    strong = bool(direct) and not warns
    strength = "none" if not (direct or supp) else ("strong" if strong else
                                                    "moderate" if any(not e["is_inference"] for e in supp) else "weak")
    missing = ([] if direct else ["own evidence for this day_key"]) + \
              ([] if any(e["kind"] == "shopping_centre" for e in supp) else ["shopping-centre hours"]) 
    views = t["analytics"].get(eid, {}).get("search_views_daily", 0)
    days = (target - cutoff).days
    priority = "high" if (views >= 100 or days <= 7) else ("normal" if views >= 20 else "low")
    rechecks = ["owner records change (new holiday entry or confirmation)", "regular hours change"]
    if prof["centre_id"]:
        rechecks.append("centre hours change")
    if ctx or ftype == "new_trading_opportunity":
        rechecks.append("event information change")
    return {
        "case_identity": {"business_id": eid, "target_date": target.isoformat(), "information_cutoff": cutoff.isoformat(),
                          "day_key": key},
        "trigger": trigger or {"type": "holiday", "day_key": key, "day_class": cal["day_class"] if cal else None},
        "displayed_state": disp,
        "finding": {"type": ftype, "tags": ["opportunity"] if ftype == "new_trading_opportunity" else [],
                    "summary": {"possible_error_omission": "Possible error/omission", "state_aligned": "State and evidence align",
                                "insufficient_evidence": "Insufficient evidence", "material_conflict": "Material conflict / status concern",
                                "new_trading_opportunity": "New trading opportunity"}[ftype]},
        "evidence": evidence,
        "uncertainty": {"evidence_strength": strength, "missing": missing},
        "route": FINDING_ROUTE[ftype], "priority": priority,
        "recheck_triggers": rechecks,
        "path": {"profile": prof["path"], "trace": trace},
    }
