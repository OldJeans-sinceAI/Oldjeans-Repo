"""Accuracy of the local Gemma model on LLM-generated labelled replies.

Always-on: harness self-tests with a scripted fake model.
Opt-in (skipped unless set): real model accuracy.
  GEMMA_EVAL_DATASET=path.jsonl [GEMMA_MODEL_PATH=...] [GEMMA_EVAL_MIN_ACCURACY=0.90]
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import eval_gemma_replies as ev  # noqa: E402
from app.teammate.local_engine import LocalGemmaEngine  # noqa: E402
from app.teammate.reply_engine import Reply  # noqa: E402

SAMPLE = ROOT / "tests/data/reply_eval_sample.jsonl"


class Scripted:
    """Fake engine answering from a reply->Reply table."""
    def __init__(self, table):
        self.table = table

    def interpret(self, ctx, text):
        return self.table.get(text, Reply("UNAVAILABLE", error_code="TIMEOUT"))


def perfect(rows):
    t = {}
    for r in rows:
        d = r["proposal"]["change"]["date"]
        if r["category"] == "accept":
            t[r["reply"]] = Reply("OK", "APPLY", "", d, True, False)
        elif r["category"] == "reject":
            t[r["reply"]] = Reply("OK", "REJECT", "", d, True, False)
        else:
            t[r["reply"]] = Reply("OK", "EDIT", r["expected_hours"], d, True, False)
    return t


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.rows = ev.load_dataset(SAMPLE)

    def test_perfect_engine_scores_100(self):
        rep = ev.evaluate(Scripted(perfect(self.rows)), self.rows)
        self.assertEqual(rep["accuracy"], 1.0)
        self.assertEqual(rep["total"], 12)
        self.assertEqual(rep["per_category"]["edit"]["n"], 4)

    def test_failure_modes_are_counted(self):
        t = perfect(self.rows)
        t["Looks good, go ahead"] = Reply("OK", "REJECT", "", "2026-12-24", True, False)  # wrong intent
        t["Please close at 15:00 instead"] = Reply("OK", "EDIT", "07:30-16:00", "2026-12-24", True, False)  # wrong hours
        t["Sopii hyvin, kiitos"] = Reply("OK", "APPLY", "", "2026-12-24", True, True)  # hedged
        t["Nei, ikke endre noe"] = Reply("OK", "REJECT", "", "2026-12-25", True, False)  # wrong date
        del t["Ei, älä muuta mitään"]  # unavailable
        rep = ev.evaluate(Scripted(t), self.rows)
        self.assertEqual(len(rep["failures"]), 5)
        self.assertAlmostEqual(rep["accuracy"], 7 / 12, places=3)
        self.assertAlmostEqual(rep["unavailable_rate"], 1 / 12, places=3)
        self.assertEqual(rep["confusion"]["accept"]["REJECT"], 1)

    def test_context_matches_production_and_leaks_no_ids(self):
        ctx = ev.context_for(self.rows[0])
        self.assertEqual(set(ctx), {"change", "timezone", "current_value"})

    def test_validation_rejects_bad_rows(self):
        base = json.loads(SAMPLE.read_text(encoding="utf-8").splitlines()[8])  # an edit row
        for mutate in (lambda r: r.pop("expected_hours"),
                       lambda r: r.update(category="maybe"),
                       lambda r: r.update(reply="  "),
                       lambda r: r["proposal"]["change"].update(date="24.12.2026"),
                       lambda r: r.update(expected_hours="3pm")):
            row = json.loads(json.dumps(base))
            mutate(row)
            with self.assertRaises((ValueError, KeyError)):
                ev.validate_row(row)


_DATA = os.getenv("GEMMA_EVAL_DATASET")
_MODEL = os.getenv("GEMMA_MODEL_PATH", "runtime/models/gemma-2-2b-reply.gguf")


@unittest.skipUnless(_DATA and os.path.isfile(_MODEL), "set GEMMA_EVAL_DATASET and provide the GGUF model")
class RealModelAccuracy(unittest.TestCase):
    def test_accuracy_threshold(self):
        engine = LocalGemmaEngine(_MODEL, timeout=10.0)
        self.assertTrue(engine.configured, "model failed to load")
        rep = ev.evaluate(engine, ev.load_dataset(_DATA))
        ev.print_report(rep)
        floor = float(os.getenv("GEMMA_EVAL_MIN_ACCURACY", "0.90"))
        self.assertGreaterEqual(rep["accuracy"], floor)
        # Safety: an unconditional APPLY must never be produced for a reject row.
        self.assertEqual(rep["confusion"].get("reject", {}).get("APPLY", 0), 0)
        self.assertEqual(rep["confusion"].get("edit", {}).get("APPLY", 0), 0)


if __name__ == "__main__":
    unittest.main()
