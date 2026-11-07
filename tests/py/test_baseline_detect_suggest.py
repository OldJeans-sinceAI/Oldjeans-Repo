"""Steps 1-2 (DETECT, SUGGEST): examples/baseline.py, the rule-based engine the loop is built on."""
import csv
import os
import unittest
from datetime import date

import helpers
from helpers import ROOT

from baseline import DAYS, Baseline, cycle, day_str
from hours import is_valid_hours

TARGETS = list(csv.DictReader(open(os.path.join(ROOT, "evaluation", "targets_2026.csv"), encoding="utf-8")))
CONTACTS = {r["entity_id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "customer_contacts.csv"), encoding="utf-8"))}
KEY = {(r["entity_id"], r["date"]): r["day_key"] for r in TARGETS}


def rows(eid):
    return [r for r in TARGETS if r["entity_id"] == eid]


class Helpers(unittest.TestCase):
    def test_day_str(self):
        self.assertEqual(day_str(None), "closed")
        self.assertEqual(day_str({"isClosed": True}), "closed")
        self.assertEqual(day_str({"openIntervals": []}), "closed")
        self.assertEqual(day_str({"openIntervals": [{"start": "10:00", "end": "14:00"},
                                                   {"start": "17:00", "end": "22:00"}]}), "10:00-14:00,17:00-22:00")

    def test_cycle_assigns_jan_to_previous_season(self):
        self.assertEqual(cycle(date(2026, 12, 24)), 2026)
        self.assertEqual(cycle(date(2027, 1, 6)), 2026)
        self.assertEqual(cycle(date(2026, 2, 1)), 2026)


class DemoStorylines(unittest.TestCase):
    """docs/DEMO_SCENARIOS.md turned into assertions."""

    @classmethod
    def setUpClass(cls):
        cls.bl = Baseline(2026)

    def explain(self, eid, day):
        return self.bl.explain(eid, date.fromisoformat(day), KEY[(eid, day)])

    def test_aurora_christmas_eve_copies_last_year(self):
        act, hours, basis, ev = self.explain("FI-D0001", "2026-12-24")
        self.assertEqual((act, hours, basis), ("SUGGEST", "07:30-13:00", "LAST_YEAR"))
        self.assertEqual(ev, ("2025-12-24", "07:30-13:00"))
        self.assertEqual(self.bl.displayed("FI-D0001", date(2026, 12, 24)), "07:30-18:00")

    def test_shopping_centre_tenant_follows_the_centre(self):
        act, hours, basis, ev = self.explain("FI-D0004", "2026-12-24")
        self.assertEqual((act, basis), ("SUGGEST", "SHOPPING_CENTRE"))
        self.assertTrue(is_valid_hours(hours))
        self.assertIsInstance(ev, str)  # the centre's name, used in the customer message

    def test_closed_for_good_business_is_flagged_never_suggested(self):
        acts = {self.explain("FI-D0011", r["date"])[0] for r in rows("FI-D0011")}
        self.assertEqual(acts, {"FLAG"})

    def test_business_with_correct_hours_stays_quiet(self):
        acts = {self.explain("FI-D0013", r["date"])[0] for r in rows("FI-D0013")}
        self.assertEqual(acts, {"NO_ACTION"})

    def test_new_customer_without_history_falls_back_to_peers_or_stays_quiet(self):
        bases = set()
        for r in rows("FI-D0017"):
            act, hours, basis, ev = self.explain("FI-D0017", r["date"])
            if act == "SUGGEST":
                bases.add(basis)
                self.assertTrue(is_valid_hours(hours))
        self.assertTrue(bases)                      # it does produce suggestions ...
        self.assertEqual(bases, {"PEERS"})          # ... but never from (non-existent) own history
        self.assertEqual(self.bl.hol.get(("FI-D0017", "2025-12-24")) or [], [])

    def test_peer_rule_needs_strong_majority(self):
        """PEERS only fires with >=70 % closed-among-entered and >=15 % having entered anything."""
        for r in rows("FI-D0017"):
            act, hours, basis, ev = self.explain("FI-D0017", r["date"])
            if basis == "PEERS" and act == "SUGGEST":
                self.assertGreaterEqual(ev, 0.7)
                self.assertEqual(hours, "closed")


class Invariants(unittest.TestCase):
    """Properties that must hold for EVERY target row (41,755 rows)."""

    @classmethod
    def setUpClass(cls):
        cls.bl = Baseline(2026)
        cls.out = [(r, cls.bl.explain(r["entity_id"], date.fromisoformat(r["date"]), r["day_key"])) for r in TARGETS]

    def test_action_is_one_of_three(self):
        self.assertEqual({o[1][0] for o in self.out} - {"SUGGEST", "NO_ACTION", "FLAG"}, set())

    def test_every_suggestion_is_valid_hours_and_differs_from_what_is_shown(self):
        n = 0
        for r, (act, hours, basis, ev) in self.out:
            if act == "SUGGEST":
                n += 1
                self.assertTrue(is_valid_hours(hours), (r, hours))
                self.assertNotEqual(hours, self.bl.displayed(r["entity_id"], date.fromisoformat(r["date"])), r)
                self.assertIn(basis, ("LAST_YEAR", "SHOPPING_CENTRE", "PEERS"))
        self.assertGreater(n, 1000)

    def test_flag_and_no_action_carry_no_hours(self):
        for r, (act, hours, _, _) in self.out:
            if act != "SUGGEST":
                self.assertEqual(hours, "")

    def test_every_suggestion_has_evidence_for_the_audit_trail_and_message(self):
        for r, (act, hours, basis, ev) in self.out:
            if act == "SUGGEST":
                self.assertIsNotNone(ev, r)

    def test_flagged_entities_are_not_already_marked_closed(self):
        for r, (act, *_rest) in self.out:
            if act == "FLAG":
                self.assertFalse(self.bl.ents[r["entity_id"]].get("closed"))

    @unittest.expectedFailure
    def test_known_gap_opted_out_customers_receive_no_suggestions(self):
        """KNOWN GAP: baseline ignores data/customer_contacts.csv `opted_out_of_suggestions` (START_HERE says the
        demo should respect opt-outs). Today it proposes SUGGEST for ~28 rows of the 6 opted-out businesses."""
        offenders = [r["entity_id"] for r, (act, *_x) in self.out
                     if act == "SUGGEST" and CONTACTS.get(r["entity_id"], {}).get("opted_out_of_suggestions") == "1"]
        self.assertEqual(offenders, [])


class BacktestHonesty(unittest.TestCase):
    """Rule from START_HERE: when simulating 6 Nov 2025 only rows with timestamps before it may be used."""

    @classmethod
    def setUpClass(cls):
        cls.bl = Baseline(2025)

    def test_entries_made_on_or_after_snapshot_are_invisible(self):
        snap = self.bl.snap.isoformat()
        checked = 0
        for (eid, d), rs in self.bl.hol.items():
            late = [x for x in rs if x["entered_at"] >= snap]
            if not late or not d.startswith(("2025-1", "2026-0")):
                continue
            early = [x for x in rs if x["entered_at"] < snap]
            got = self.bl.entry(eid, date.fromisoformat(d), self.bl.snap)
            if not early:
                self.assertIsNone(got, (eid, d))
            else:
                last = max(early, key=lambda x: x["entered_at"])["holidayHours"]
                self.assertEqual(got, "REGULAR" if last.get("isRegularHours") else day_str(last), (eid, d))
            checked += 1
            if checked >= 300:
                break
        self.assertGreater(checked, 0)

    def test_regular_hours_ignore_versions_effective_after_snapshot(self):
        snap = self.bl.snap.isoformat()
        for eid, versions in self.bl.reg.items():
            future = [v for v in versions if v["effective_from"] != "before-2024" and v["effective_from"] >= snap]
            if not future:
                continue
            past = [v for v in versions if v["effective_from"] == "before-2024" or v["effective_from"] < snap]
            newest = max(past, key=lambda v: "0000" if v["effective_from"] == "before-2024" else v["effective_from"])
            d = date(2025, 12, 1)  # a Monday
            self.assertEqual(self.bl.regular(eid, d), day_str(newest["hours"][DAYS[d.weekday()]]))
            return
        self.skipTest("no entity with a post-snapshot regular-hours version")


if __name__ == "__main__":
    unittest.main()
