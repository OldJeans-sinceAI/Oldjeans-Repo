"""Detect step: (1) data files the PDF relies on exist and have the documented shape, (2) the Kahvila Aurora
fixture really is in the data, (3) gap tests: PDF requirements that the repo does NOT implement yet.

(1)+(2) pass today. (3) are @expectedFailure = known gaps; when the team builds the feature the test flips to
'unexpected success' - then delete the marker. Nothing here changes application code.
"""
import csv
import glob
import json
import os
import re
import unittest
from datetime import date

import helpers
from helpers import ROOT

D = lambda *p: os.path.join(ROOT, "data", *p)  # noqa: E731
EX = os.path.join(ROOT, "examples")
SNAPSHOT = "2026-11-06"


def read_csv(name):
    with open(D(name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def source(*names):
    return "\n".join(open(os.path.join(EX, n), encoding="utf-8").read() for n in names)


def examples_src():
    return {os.path.basename(p): open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(EX, "*.py"))}


# ============================================================================ (1) data files
class RequiredDataFiles(unittest.TestCase):
    REQUIRED = ["calendar_special_days.csv", "entities.json", "regular_hours_history.jsonl",
                "holiday_hours_history.jsonl", "pilot_decision_log_2025.csv", "peer_benchmarks.csv",
                "analytics_daily.parquet", "reviews.json"]
    OPTIONAL_USED_BY_PDF = ["local_events.json", "school_breaks.csv", "weather_daily.csv", "weather_normals.csv",
                            "publisher_suggestions.json", "listings.json", "customer_contacts.csv"]

    def test_all_required_files_exist_and_are_non_empty(self):
        for n in self.REQUIRED + self.OPTIONAL_USED_BY_PDF:
            with self.subTest(file=n):
                self.assertTrue(os.path.isfile(D(n)), f"missing data/{n}")
                self.assertGreater(os.path.getsize(D(n)), 100)

    def test_calendar_special_days_columns_and_target_day(self):
        rows = read_csv("calendar_special_days.csv")
        for c in ("country", "date", "day_key", "day_class"):
            self.assertIn(c, rows[0])
        self.assertEqual({r["country"] for r in rows}, {"FI", "SE", "NO"})
        xmas = [r for r in rows if r["country"] == "FI" and r["date"] == "2026-12-24"]
        self.assertEqual([(r["day_key"], r["day_class"]) for r in xmas], [("XMAS_EVE", "EVE_MAJOR")])

    def test_entities_json_shape(self):
        d = json.load(open(D("entities.json"), encoding="utf-8"))
        ents = d["response"]["entities"]
        self.assertEqual(d["response"]["count"], len(ents))
        self.assertEqual(len(ents), 3032)
        for e in ents[:300]:
            self.assertIn("id", e["meta"])
            self.assertIn("hours", e)
            self.assertIn("c_segment", e)
        hol_keys = {k for e in ents for h in e["hours"].get("holidayHours", []) for k in h}
        self.assertLessEqual(hol_keys, {"date", "isClosed", "isRegularHours", "openIntervals"})
        self.assertTrue(any(e.get("c_shoppingCenterEntityId") for e in ents), "no shopping-centre links in data")

    def test_regular_hours_history_shape(self):
        n = 0
        for line in open(D("regular_hours_history.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            self.assertLessEqual({"entity_id", "effective_from", "hours"}, set(r))
            n += 1
        self.assertGreater(n, 3000)

    def test_holiday_hours_history_shape_and_no_future_entries(self):
        # EVENT and SCHOOL_BREAK are documented history day_keys (DATA_DICTIONARY) that have NO calendar row:
        # Detect step D must select those cases from local_events.json / school_breaks.csv, not from the calendar.
        cal_keys = {r["day_key"] for r in read_csv("calendar_special_days.csv")} | {"EVENT", "SCHOOL_BREAK"}
        latest, n = "", 0
        for line in open(D("holiday_hours_history.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            self.assertLessEqual({"entity_id", "date", "day_key", "holidayHours", "entered_at", "source"}, set(r))
            self.assertIn(r["day_key"], cal_keys)
            latest, n = max(latest, r["entered_at"]), n + 1
        self.assertGreater(n, 50000)
        self.assertLess(latest, SNAPSHOT + "T23:59:59", "history contains entries after the information cutoff")

    def test_pilot_decision_log_columns_and_vocabulary(self):
        rows = read_csv("pilot_decision_log_2025.csv")
        for c in ("entity_id", "date", "day_key", "decision", "final_hours", "decided_at", "suggested_hours"):
            self.assertIn(c, rows[0])
        self.assertLessEqual({r["decision"] for r in rows}, {"ACCEPTED", "EDITED", "REJECTED", "NO_RESPONSE"})
        edited = [r for r in rows if r["decision"] in ("ACCEPTED", "EDITED")]
        self.assertTrue(edited and all(r["final_hours"] for r in edited), "confirmed rows must carry final_hours")

    def test_peer_benchmarks_columns(self):
        rows = read_csv("peer_benchmarks.csv")
        for c in ("country", "city_tier", "segment", "day_key", "n_entity_days", "closed_share_among_entered",
                  "share_entered_closed", "median_open_special", "median_close_special"):
            self.assertIn(c, rows[0])

    def test_reviews_json_shape(self):
        r = json.load(open(D("reviews.json"), encoding="utf-8"))["response"]
        self.assertEqual(r["count"], len(r["reviews"]))
        self.assertLessEqual({"locationId", "content", "publisherDate"}, set(r["reviews"][0]))

    def test_analytics_parquet_is_a_parquet_file(self):
        with open(D("analytics_daily.parquet"), "rb") as f:
            head = f.read(4)
            f.seek(-4, os.SEEK_END)
            tail = f.read(4)
        self.assertEqual((head, tail), (b"PAR1", b"PAR1"))

    def test_analytics_parquet_columns(self):
        try:
            import pandas as pd
            df = pd.read_parquet(D("analytics_daily.parquet"))
        except ImportError:
            self.skipTest("pandas/pyarrow not installed")
        for c in ("date", "entity_id", "GOOGLE_SEARCH_VIEWS", "GOOGLE_PHONE_CALLS", "PROFILE_VIEWS"):
            self.assertIn(c, df.columns)

    def test_listings_json_is_the_publisher_source_for_apply(self):
        d = json.load(open(D("listings.json"), encoding="utf-8"))["listings"]
        self.assertLessEqual({"entityId", "publisherId", "publisherName", "status", "typicalUpdateSpeedSeconds"}, set(d[0]))
        self.assertEqual(len({l["publisherId"] for l in d}), 14)


# ============================================================================ (2) Aurora in the data
class KahvilaAuroraFixtureInData(unittest.TestCase):
    """Precondition of the PDF's worked example (p.7), asserted on the real files."""

    @classmethod
    def setUpClass(cls):
        cls.ent = next(e for e in json.load(open(D("entities.json"), encoding="utf-8"))["response"]["entities"]
                       if e["meta"]["id"] == "FI-D0001")
        cls.hist = [json.loads(l) for l in open(D("holiday_hours_history.jsonl"), encoding="utf-8") if '"FI-D0001"' in l]

    def test_has_regular_hours_for_the_target_weekday(self):
        self.assertEqual(self.ent["name"], "Kahvila Aurora")
        self.assertEqual(date(2026, 12, 24).strftime("%A"), "Thursday")
        self.assertEqual(self.ent["hours"]["thursday"], {"openIntervals": [{"start": "07:30", "end": "18:00"}]})

    def test_has_no_exception_for_2026_12_24(self):
        self.assertNotIn("2026-12-24", [h["date"] for h in self.ent["hours"].get("holidayHours", [])])

    def test_history_shows_07_30_13_00_last_year(self):
        row = [r for r in self.hist if r["date"] == "2025-12-24"]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0]["day_key"], "XMAS_EVE")
        self.assertEqual(row[0]["holidayHours"]["openIntervals"], [{"start": "07:30", "end": "13:00"}])
        self.assertLess(row[0]["entered_at"], SNAPSHOT)

    def test_is_a_target_case_in_the_case_linking_file(self):
        rows = list(csv.DictReader(open(os.path.join(ROOT, "evaluation", "targets_2026.csv"), encoding="utf-8")))
        self.assertIn(("FI-D0001", "2026-12-24", "XMAS_EVE"), {(r["entity_id"], r["date"], r["day_key"]) for r in rows})


# ============================================================================ (3) PDF vs code
class DetectLayerGaps(unittest.TestCase):
    """Each test states a PDF requirement. All are expectedFailure today (see tests/DETECT_QA_REPORT.md section 4)."""

    @staticmethod
    def defined(pattern):
        rx = re.compile(r"def\s+\w*(%s)\w*\s*\(" % pattern, re.I)
        return sorted(f"{f}:{m.group(0)}" for f, s in examples_src().items() for m in rx.finditer(s))

    @unittest.expectedFailure
    def test_G1_profile_refresh_B_and_pre_classification_C_exist(self):
        """B/C: per-business profile (coverage, freshness, links, conflicts) classified strong/partial/limited."""
        self.assertTrue(self.defined("profile|pre_?classif|classify"))

    @unittest.expectedFailure
    def test_G1b_strong_partial_limited_vocabulary_exists_in_code(self):
        src = "\n".join(examples_src().values()).lower()
        self.assertTrue(all(w in src for w in ("strong", "partial", "limited")))

    @unittest.expectedFailure
    def test_G2_routing_E_to_F_G_H_exists(self):
        """E: check profile against target date; route to fast / supplement / indirect path; F->G fallback."""
        self.assertTrue(self.defined("route|routing|supplement|indirect|fast_path"))

    @unittest.expectedFailure
    def test_G3_synthesis_I_with_five_finding_types_exists(self):
        src = "\n".join(examples_src().values()).lower()
        for t in ("insufficient", "material_conflict", "state_aligned", "possible_error", "opportunity"):
            self.assertIn(t, src)

    @unittest.expectedFailure
    def test_G4_handoff_J_payload_exists(self):
        self.assertTrue(self.defined("handoff|hand_off"))

    @unittest.expectedFailure
    def test_G5_detect_output_does_not_contain_proposed_hours(self):
        """'Detect does not choose the final proposed hours; Suggest does.' Today Baseline.explain() returns
        (action, HOURS, basis, evidence) from ONE function, so Detect and Suggest are fused."""
        from datetime import date as d
        from baseline import Baseline
        out = Baseline(2026).explain("FI-D0001", d(2026, 12, 24), "XMAS_EVE")
        self.assertEqual(len(out), 4)
        leaked = [x for x in out if isinstance(x, str) and re.fullmatch(r"(closed|\d\d:\d\d-\d\d:\d\d(,\d\d:\d\d-\d\d:\d\d)*)", x)]
        self.assertEqual(leaked, [], f"explain() hands hours downstream: {leaked}")

    @unittest.expectedFailure
    def test_G6_all_pdf_evidence_sources_are_consumed_by_the_engine(self):
        """PDF p.3-5: analytics, owner confirmations (pilot log), events, school breaks, weather."""
        src = source("baseline.py")
        for token in ("analytics_daily", "pilot_decision_log", "local_events", "school_breaks", "weather"):
            self.assertIn(token, src, f"baseline.py never reads {token}")

    @unittest.expectedFailure
    def test_G7_owner_confirmation_is_direct_evidence(self):
        """Pilot ACCEPTED/EDITED final_hours must outrank raw history (PDF p.3). Engine ignores the log entirely."""
        self.assertIn("final_hours", source("baseline.py"))

    @unittest.expectedFailure
    def test_G8_evidence_has_provenance_fields(self):
        """Support/counter-evidence needs content, provenance, applicable date, entry time, record reference.
        Baseline returns a bare tuple: evidence is a date/hours pair or a string."""
        from datetime import date as d
        from baseline import Baseline
        ev = Baseline(2026).explain("FI-D0001", d(2026, 12, 24), "XMAS_EVE")[3]
        self.assertIsInstance(ev, (list, dict))

    @unittest.expectedFailure
    def test_G9_closure_signals_are_a_warning_not_the_whole_decision(self):
        """PDF p.6: closure mentions are 'counter/warning' evidence that PAUSES a fast decision and goes to staff
        review as 'material conflict'. Baseline returns action='FLAG' and stops, with no evidence list or route name."""
        src = source("baseline.py")
        self.assertRegex(src.lower(), r"staff_review|material_conflict")

    @unittest.expectedFailure
    def test_G10_profile_refresh_is_triggered_by_data_changes_A(self):
        """A: refresh B-C only when source data changes, then reuse. Baseline.__init__ re-reads every file."""
        self.assertTrue(self.defined("refresh|invalidate|on_change|changed"))

    @unittest.expectedFailure
    def test_G11_displayed_state_from_history_equals_displayed_state_from_entities_json(self):
        """PDF p.3 reconstructs the displayed state from entities.json (dated exception, else weekday hours).
        baseline.py rebuilds it from regular/holiday HISTORY instead. 17 of 41,755 target rows disagree today
        (e.g. FI-00330 2026-11-08: history says 09:00-17:00, entities.json says 09:00-16:00)."""
        from baseline import DAYS, Baseline, day_str
        bl = Baseline(2026)
        bad = []
        for r in csv.DictReader(open(os.path.join(ROOT, "evaluation", "targets_2026.csv"), encoding="utf-8")):
            d, eid = date.fromisoformat(r["date"]), r["entity_id"]
            h = bl.ents[eid]["hours"]
            exc = next((x for x in h.get("holidayHours", []) if x["date"] == r["date"]), None)
            want = day_str(h.get(DAYS[d.weekday()])) if (exc is None or exc.get("isRegularHours")) else day_str(exc)
            if bl.displayed(eid, d) != want:
                bad.append((eid, r["date"]))
        self.assertEqual(bad, [], f"{len(bad)} rows disagree, e.g. {bad[:3]}")

    # -- things that DO hold (kept so a regression is visible)
    def test_engine_does_not_read_evaluation_answers(self):
        """PDF p.7: 'Detect does not use evaluation answers as inference evidence.'"""
        src = source("baseline.py", "quickstart.py", "yext_client.py")
        for forbidden in ("labels/", "dev_labels", "dev_truth", "truth_history", "dev_regular_hours_truth"):
            self.assertNotIn(forbidden, src)

    def test_engine_honours_the_information_cutoff(self):
        """History/entries are filtered to `< snapshot`, i.e. Detect knows only what was known at the cutoff."""
        src = source("baseline.py")
        self.assertIn('r["entered_at"] < as_of.isoformat()', src)
        self.assertIn("SNAP = {2026: date(2026, 11, 6)", src)


if __name__ == "__main__":
    unittest.main()
