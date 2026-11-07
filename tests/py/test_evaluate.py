"""evaluation/evaluate.py - the objective part of the 'Suggestion quality' criterion. Uses tiny synthetic CSVs."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

import helpers
from helpers import ROOT

import evaluate as ev

LABEL_COLS = ["entity_id", "date", "day_key", "event_id", "truth_hours", "displayed_hours_at_snapshot", "needs_action",
              "expected_action", "mismatch_type", "expected_search_views"]


def label(eid, truth, shown, exp, mismatch="", views="10", d="2026-12-24"):
    return dict(entity_id=eid, date=d, day_key="XMAS_EVE", event_id="", truth_hours=truth,
                displayed_hours_at_snapshot=shown, needs_action="1" if exp != "NO_ACTION" else "0",
                expected_action=exp, mismatch_type=mismatch, expected_search_views=views)


class TmpFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def write(self, name, header, rows):
        p = os.path.join(self.dir, name)
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(rows)
        return p

    def score(self, labels, preds):
        lp = self.write("labels.csv", LABEL_COLS, labels)
        pp = self.write("preds.csv", ["entity_id", "date", "action", "hours", "confidence"], preds)
        return ev.score(ev.load_predictions(pp), lp)


def pred(eid, action, hours="", d="2026-12-24"):
    return dict(entity_id=eid, date=d, action=action, hours=hours, confidence="0.9")


class ScoringRules(TmpFiles):
    NEEDS = dict(truth="10:00-15:00", shown="09:00-18:00", exp="SUGGEST", mismatch="DIFFERENT_HOURS")

    def pts(self, truth, shown, exp, action, hours, mismatch=""):
        r = self.score([label("A", truth, shown, exp, mismatch)], [pred("A", action, hours)])
        return r["score_0_100"], r["breakdown"]

    def test_exact_is_full_points(self):
        s, b = self.pts("10:00-15:00", "09:00-18:00", "SUGGEST", "SUGGEST", "10:00-15:00", "DIFFERENT_HOURS")
        self.assertEqual((s, b["exact"]), (100.0, 1))

    def test_near_within_30_min_is_0_6(self):
        s, b = self.pts("10:00-15:00", "09:00-18:00", "SUGGEST", "SUGGEST", "10:30-15:00", "DIFFERENT_HOURS")
        self.assertEqual((s, b["near"]), (60.0, 1))

    def test_same_state_but_far_is_0_2(self):
        s, b = self.pts("10:00-15:00", "09:00-18:00", "SUGGEST", "SUGGEST", "11:00-15:00", "DIFFERENT_HOURS")
        self.assertEqual((s, b["same_state_off"]), (20.0, 1))

    def test_wrong_state_costs_a_full_point_and_the_headline_floors_at_zero(self):
        s, b = self.pts("10:00-15:00", "09:00-18:00", "SUGGEST", "SUGGEST", "closed", "DIFFERENT_HOURS")
        self.assertEqual((s, b["harmful_wrong_state"]), (0.0, 1))
        # one exact (+1) and one wrong-state (-1) cancel out exactly -> 0, proving the penalty is -1 not 0
        labels = [label("A", "10:00-15:00", "09:00-18:00", "SUGGEST", "DIFFERENT_HOURS"),
                  label("B", "10:00-15:00", "09:00-18:00", "SUGGEST", "DIFFERENT_HOURS")]
        r = self.score(labels, [pred("A", "SUGGEST", "10:00-15:00"), pred("B", "SUGGEST", "closed")])
        self.assertEqual(r["score_0_100"], 0.0)
        # and one exact + one silent miss = 50
        r = self.score(labels, [pred("A", "SUGGEST", "10:00-15:00")])
        self.assertEqual(r["score_0_100"], 50.0)

    def test_flag_on_change_and_missed(self):
        self.assertEqual(self.pts("10:00-15:00", "09:00-18:00", "SUGGEST", "FLAG", "")[0], 5.0)
        s, b = self.pts("10:00-15:00", "09:00-18:00", "SUGGEST", "NO_ACTION", "")
        self.assertEqual((s, b["missed"]), (0.0, 1))

    def test_already_correct_cases(self):
        labels = [label("A", "closed", "closed", "NO_ACTION"), label("B", "10:00-15:00", "10:00-15:00", "NO_ACTION"),
                  label("C", "closed", "closed", "NO_ACTION"), label("D", "10:00-15:00", "10:00-15:00", "NO_ACTION"),
                  label("E", "x", "x", "SUGGEST", "DIFFERENT_HOURS")]
        labels[4]["truth_hours"] = labels[4]["displayed_hours_at_snapshot"] = "10:00-15:00"
        preds = [pred("A", "SUGGEST", "closed"),          # redundant confirm  -0.1
                 pred("B", "SUGGEST", "11:00-15:00"),     # spam wrong hours   -0.5
                 pred("C", "SUGGEST", "10:00-15:00"),     # wrong state        -1
                 pred("D", "FLAG", "")]                   # unneeded flag      -0.1
        r = self.score(labels, preds)
        for k in ("redundant_confirm", "spam_wrong_hours", "harmful_wrong_state", "unneeded_flag"):
            self.assertEqual(r["breakdown"][k], 1, k)
        self.assertEqual(r["score_0_100"], 0.0)

    def test_silence_is_free(self):
        r = self.score([label("A", "closed", "closed", "NO_ACTION")], [])
        self.assertEqual(r["breakdown"], {"correct_silence": 1})

    def test_closed_for_good_flag_scores_and_suggesting_open_is_harmful(self):
        lab = [label("A", "closed", "09:00-18:00", "FLAG")]
        self.assertEqual(self.score(lab, [pred("A", "FLAG")])["score_0_100"], 100.0)
        self.assertEqual(self.score(lab, [pred("A", "SUGGEST", "closed")])["breakdown"]["suggest_to_closed_business"], 1)
        self.assertEqual(self.score(lab, [pred("A", "SUGGEST", "09:00-18:00")])["score_0_100"], 0.0)
        self.assertEqual(self.score(lab, [])["breakdown"]["missed_closed_business"], 1)

    def test_search_view_protection_weights_by_views(self):
        labels = [label("A", "closed", "09:00-18:00", "SUGGEST", "SHOWN_OPEN_ACTUALLY_CLOSED", views="30"),
                  label("B", "closed", "09:00-18:00", "SUGGEST", "SHOWN_OPEN_ACTUALLY_CLOSED", views="10")]
        r = self.score(labels, [pred("A", "SUGGEST", "closed")])
        self.assertEqual(r["search_views_protected_pct"], 75.0)
        self.assertEqual(r["closed_door_views_prevented_pct"], 75.0)

    def test_precision_recall_and_contact_load(self):
        labels = [label("A", "closed", "09:00-18:00", "SUGGEST", "SHOWN_OPEN_ACTUALLY_CLOSED"),
                  label("A", "closed", "09:00-18:00", "SUGGEST", "SHOWN_OPEN_ACTUALLY_CLOSED", d="2026-12-25"),
                  label("B", "closed", "09:00-18:00", "SUGGEST", "SHOWN_OPEN_ACTUALLY_CLOSED")]
        preds = [pred("A", "SUGGEST", "closed"), pred("A", "SUGGEST", "closed", d="2026-12-25"),
                 pred("B", "SUGGEST", "10:00-12:00")]
        r = self.score(labels, preds)
        self.assertEqual(r["businesses_contacted"], 2)
        self.assertEqual(r["avg_dates_per_contacted_business"], 1.5)
        self.assertAlmostEqual(r["precision_exact"], 0.667, places=3)
        self.assertAlmostEqual(r["recall_exact"], 0.667, places=3)

    def test_predictions_not_in_labels_are_ignored_and_counted(self):
        r = self.score([label("A", "closed", "09:00-18:00", "SUGGEST")], [pred("ZZZ", "SUGGEST", "closed")])
        self.assertEqual(r["ignored_prediction_rows_not_in_labels"], 1)
        self.assertEqual(r["suggestions_made"], 0)


class PredictionValidation(TmpFiles):
    def load(self, rows, header=("entity_id", "date", "action", "hours")):
        return ev.load_predictions(self.write("p.csv", list(header), rows))

    def test_bad_action_hours_and_duplicates_abort(self):
        for rows in ([dict(entity_id="A", date="2026-12-24", action="MAYBE", hours="")],
                     [dict(entity_id="A", date="2026-12-24", action="SUGGEST", hours="9-17")],
                     [dict(entity_id="A", date="2026-12-24", action="FLAG", hours=""),
                      dict(entity_id="A", date="2026-12-24", action="FLAG", hours="")]):
            with self.assertRaises(SystemExit):
                self.load(rows)

    @unittest.expectedFailure
    def test_known_gap_suggest_with_empty_hours_should_be_rejected(self):
        """KNOWN GAP: docs say hours are REQUIRED for SUGGEST, but norm('') -> 'closed', so a SUGGEST row with a blank
        hours cell is silently scored as 'suggest closed' (and is harmful if the business is open)."""
        with self.assertRaises(SystemExit):
            self.load([dict(entity_id="A", date="2026-12-24", action="SUGGEST", hours="")])

    def test_missing_required_columns_abort(self):
        with self.assertRaises(SystemExit):
            self.load([dict(entity_id="A", date="2026-12-24")], header=("entity_id", "date"))

    def test_hours_are_normalised(self):
        p = self.load([dict(entity_id="A", date="d", action="suggest", hours=" Kiinni "),
                       dict(entity_id="B", date="d", action="SUGGEST", hours="10:00-14:00, 17:00-22:00")])
        self.assertEqual(p[("A", "d")][:2], ("SUGGEST", "closed"))
        self.assertEqual(p[("B", "d")][1], "10:00-14:00,17:00-22:00")

    def test_norm_and_near(self):
        self.assertEqual([ev.norm(x) for x in (None, "", "stängt", "stengt")], ["closed"] * 4)
        self.assertTrue(ev.near("10:00-15:00", "10:30-14:30"))
        self.assertFalse(ev.near("10:00-15:00", "10:31-15:00"))
        self.assertTrue(ev.near("closed", "closed"))
        self.assertFalse(ev.near("closed", "10:00-15:00"))


class Cli(unittest.TestCase):
    def test_cli_json_on_real_dev_labels_with_empty_predictions_scores_zero(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "p.csv")
        open(p, "w").write("entity_id,date,action,hours\n")
        out = subprocess.run([sys.executable, os.path.join(ROOT, "evaluation", "evaluate.py"), "--predictions", p, "--json"],
                             capture_output=True, text=True, check=True).stdout
        res = json.loads(out)
        self.assertEqual(res["score_0_100"], 0.0)
        self.assertEqual(res["rows"], 11100)
        self.assertEqual(res["rows_needing_action"], 5398)

    def test_baseline_reference_score_is_stable(self):
        """Regression guard for the published baseline (START_HERE.md: 54.5 / precision 0.90 / harmful 224)."""
        from baseline import Baseline
        from datetime import date
        bl, preds = Baseline(2026), {}
        for r in csv.DictReader(open(os.path.join(ROOT, "evaluation", "targets_2026.csv"), encoding="utf-8")):
            a, h = bl.predict(r["entity_id"], date.fromisoformat(r["date"]), r["day_key"])
            if a != "NO_ACTION":
                preds[(r["entity_id"], r["date"])] = (a, h, 0.6)
        res = ev.score(preds, os.path.join(ROOT, "labels", "dev_labels_2026.csv"))
        self.assertAlmostEqual(res["score_0_100"], 54.49, places=1)
        self.assertEqual(res["harmful_suggestions"], 224)
        self.assertAlmostEqual(res["precision_exact"], 0.901, places=2)


if __name__ == "__main__":
    unittest.main()
