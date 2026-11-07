"""In-memory evidence tables for Detect tests. Same row shapes as the files under data/.

    entities        {entity_id: entity (entities.json shape)}
    regular_history [{"entity_id", "effective_from", "hours"}]                 regular_hours_history.jsonl
    holiday_history [{"entity_id","date","day_key","holidayHours","entered_at","source"}]  holiday_hours_history.jsonl
    pilot_log       [csv row dict]                                              pilot_decision_log_2025.csv
    calendar        [csv row dict]                                              calendar_special_days.csv
    peers           [csv row dict]                                              peer_benchmarks.csv
    reviews         [{"locationId","content","publisherDate"(ms)}]              reviews.json["response"]["reviews"]
    suggestions     [{"locationId","fieldName","suggestedContent","status","dateCreated"}]  publisher_suggestions.json
    events          [{"@id","start_time","end_time","location":{"address_locality"},"x_country","x_expected_attendance"}]
    analytics       {entity_id: {"search_views_daily": n}}                      summary of analytics_daily.parquet
"""
from __future__ import annotations

import copy
import csv
import json
import os
from datetime import date, datetime

from helpers import ROOT

CUTOFF = date(2026, 11, 6)            # information cutoff (same snapshot as the dataset)
TARGET = date(2026, 12, 24)           # Christmas Eve 2026
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# (date, day_key, day_class) for FI, 2025 season + 2026 targets (copied from calendar_special_days.csv)
_CAL = [
    ("2025-01-05", "EPIPHANY_EVE", "EVE_MINOR"), ("2025-12-06", "INDEPENDENCE_DAY", "SOFT"),
    ("2025-12-24", "XMAS_EVE", "EVE_MAJOR"), ("2025-12-25", "XMAS_DAY", "MAJOR"),
    ("2025-12-26", "BOXING_DAY", "SOFT"), ("2025-12-31", "NYE", "EVE_MINOR"),
    ("2026-01-05", "EPIPHANY_EVE", "EVE_MINOR"), ("2026-12-06", "INDEPENDENCE_DAY", "SOFT"),
    ("2026-12-24", "XMAS_EVE", "EVE_MAJOR"), ("2026-12-25", "XMAS_DAY", "MAJOR"),
    ("2026-12-26", "BOXING_DAY", "SOFT"), ("2026-12-31", "NYE", "EVE_MINOR"),
]


def week(hours="07:30-18:00"):
    a, b = hours.split("-")
    return {d: {"openIntervals": [{"start": a, "end": b}]} for d in DAYS}


def hours_obj(h):
    """'closed' | '07:30-13:00' -> Yext holidayHours payload (without date)."""
    if h == "closed":
        return {"isClosed": True}
    a, b = h.split("-")
    return {"openIntervals": [{"start": a, "end": b}]}


def empty_tables():
    return {"entities": {}, "regular_history": [], "holiday_history": [], "pilot_log": [], "peers": [],
            "reviews": [], "suggestions": [], "events": [], "analytics": {},
            "calendar": [{"country": "FI", "date": d, "weekday": "", "day_key": k, "day_class": c,
                          "day_type": "", "official_public_holiday": "0"} for d, k, c in _CAL]}


def add_entity(t, eid, regular="07:30-18:00", city="Helsinki", segment="cafe", centre=None, exceptions=None,
               name="Test Cafe", extra_hours=None):
    h = week(regular)
    h["holidayHours"] = [{"date": d, **hours_obj(v)} for d, v in (exceptions or {}).items()]
    h.update(extra_hours or {})
    t["entities"][eid] = {
        "meta": {"id": eid, "countryCode": "FI", "language": "fi"}, "name": name,
        "address": {"city": city, "countryCode": "FI"}, "c_segment": segment, "hours": h, "closed": False,
        **({"c_shoppingCenterEntityId": centre} if centre else {})}
    t["regular_history"].append({"entity_id": eid, "effective_from": "before-2024", "hours": week(regular)})
    return t["entities"][eid]


def add_hol(t, eid, d, day_key, hours, entered_at=None, source="OWNER_UI"):
    t["holiday_history"].append({
        "entity_id": eid, "date": d, "day_key": day_key, "holidayHours": {"date": d, **hours_obj(hours)},
        "entered_at": entered_at or f"{d[:4]}-{int(d[5:7]):02d}-01T10:00:00", "source": source})


def rich_history(t, eid, xmas_eve="07:30-13:00"):
    """Own history on several 2025 holidays (strong coverage). Pass xmas_eve=None to omit the target day_key."""
    if xmas_eve:
        add_hol(t, eid, "2025-12-24", "XMAS_EVE", xmas_eve, "2025-12-21T20:00:00")
    add_hol(t, eid, "2025-12-31", "NYE", "09:00-14:00", "2025-12-20T10:00:00")
    add_hol(t, eid, "2025-12-25", "XMAS_DAY", "closed", "2025-12-10T10:00:00")
    add_hol(t, eid, "2025-12-26", "BOXING_DAY", "closed", "2025-12-10T10:00:00")
    add_hol(t, eid, "2025-12-06", "INDEPENDENCE_DAY", "closed", "2025-11-20T10:00:00")
    add_hol(t, eid, "2025-01-05", "EPIPHANY_EVE", "09:00-15:00", "2024-12-20T10:00:00")


def thin_history(t, eid):
    """Two entries, neither for XMAS_EVE (partial direct evidence)."""
    add_hol(t, eid, "2025-12-31", "NYE", "09:00-14:00", "2025-12-20T10:00:00")
    add_hol(t, eid, "2025-12-06", "INDEPENDENCE_DAY", "closed", "2025-11-20T10:00:00")


def add_peer(t, day_key="XMAS_EVE", segment="cafe", n=120, closed_among_entered=0.9, entered_closed=0.4):
    t["peers"].append({"country": "FI", "city_tier": "capital", "segment": segment, "day_key": day_key,
                       "n_entity_days": str(n), "share_entered_closed": str(entered_closed),
                       "closed_share_among_entered": str(closed_among_entered)})


def add_review(t, eid, text, when=datetime(2026, 10, 20)):
    t["reviews"].append({"locationId": eid, "content": text, "publisherDate": int(when.timestamp() * 1000)})


def tables_for_golden_aurora():
    """Kahvila Aurora as in the Detect PDF p.7, but fully in memory."""
    t = empty_tables()
    add_entity(t, "FI-D0001", regular="07:30-18:00", name="Kahvila Aurora")
    rich_history(t, "FI-D0001")
    return t


# ----------------------------------------------------------------------------- real data
_REAL = None


def real_tables():
    """Load the real files from data/ (cached). Skips analytics parquet (pyarrow is optional)."""
    global _REAL
    if _REAL is not None:
        return copy.copy(_REAL)
    D = lambda *p: os.path.join(ROOT, "data", *p)  # noqa: E731
    rd = lambda n: list(csv.DictReader(open(D(n), encoding="utf-8")))  # noqa: E731
    _REAL = {
        "entities": {e["meta"]["id"]: e for e in json.load(open(D("entities.json"), encoding="utf-8"))["response"]["entities"]},
        "regular_history": [json.loads(x) for x in open(D("regular_hours_history.jsonl"), encoding="utf-8")],
        "holiday_history": [json.loads(x) for x in open(D("holiday_hours_history.jsonl"), encoding="utf-8")],
        "pilot_log": rd("pilot_decision_log_2025.csv"), "calendar": rd("calendar_special_days.csv"),
        "peers": rd("peer_benchmarks.csv"),
        "reviews": json.load(open(D("reviews.json"), encoding="utf-8"))["response"]["reviews"],
        "suggestions": json.load(open(D("publisher_suggestions.json"), encoding="utf-8"))["response"]["suggestions"],
        "events": json.load(open(D("local_events.json"), encoding="utf-8"))["data"], "analytics": {},
    }
    return copy.copy(_REAL)
