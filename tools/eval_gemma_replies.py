"""Measure how often the reply engine classifies labelled owner replies correctly.

Dataset: JSONL, one object per line (see docs/reply_dataset_prompt.md):
  {"id": str, "language": "en|fi|sv|nb|ko", "category": "accept|reject|edit",
   "reply": str,
   "proposal": {"timezone": str, "current_value": str|null,
                "change": {"kind": "DATE_HOURS", "date": "YYYY-MM-DD", "hours": "HH:MM-HH:MM"}
                       or {"kind": "REOPEN_DATE", "date": "YYYY-MM-DD"}},
   "expected_hours": "HH:MM-HH:MM[,HH:MM-HH:MM]" | "closed"   # required for edit only
  }

A row is a SUCCESS only if the engine's answer would give the right READY draft in
OwnerReplies: right intent, scope_match true, needs_clarification false, date empty or
the target date, and (edit) exactly the expected hours. Anything UNAVAILABLE is a failure.

Usage: python tools/eval_gemma_replies.py data.jsonl [--model path.gguf]
         [--min-accuracy 0.9] [--report report.json]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict

CATEGORIES = {"accept": "APPLY", "reject": "REJECT", "edit": "EDIT"}
HOURS_RE = r"\d{2}:\d{2}-\d{2}:\d{2}"
EXPECTED_HOURS_RE = re.compile(rf"closed|{HOURS_RE}(,{HOURS_RE})*")


class DatasetError(ValueError):
    pass


def load_dataset(path):
    rows, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                validate_row(row)
            except (ValueError, KeyError, TypeError) as exc:
                raise DatasetError(f"{path}:{n}: {exc}") from None
            if row["id"] in seen:
                raise DatasetError(f"{path}:{n}: duplicate id {row['id']!r}")
            seen.add(row["id"])
            rows.append(row)
    if not rows:
        raise DatasetError(f"{path}: no rows")
    return rows


def validate_row(row):
    if not isinstance(row, dict):
        raise ValueError("row must be an object")
    for key in ("id", "language", "category", "reply", "proposal"):
        if key not in row:
            raise ValueError(f"missing {key!r}")
    if row["category"] not in CATEGORIES:
        raise ValueError(f"category must be one of {sorted(CATEGORIES)}")
    if not isinstance(row["reply"], str) or not row["reply"].strip():
        raise ValueError("reply must be a non-empty string")
    p = row["proposal"]
    change = p["change"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", change["date"]):
        raise ValueError("change.date must be YYYY-MM-DD")
    if change["kind"] == "DATE_HOURS":
        if not re.fullmatch(HOURS_RE, change["hours"]):
            raise ValueError("DATE_HOURS needs change.hours as HH:MM-HH:MM")
    elif change["kind"] != "REOPEN_DATE":
        raise ValueError("change.kind must be DATE_HOURS or REOPEN_DATE")
    if not p.get("timezone"):
        raise ValueError("proposal.timezone required")
    if row["category"] == "edit":
        if change["kind"] != "DATE_HOURS":
            raise ValueError("edit rows must use a DATE_HOURS proposal")
        if not EXPECTED_HOURS_RE.fullmatch(row.get("expected_hours", "")):
            raise ValueError("edit rows need expected_hours (HH:MM-HH:MM[,..] or closed)")


def context_for(row):
    p = row["proposal"]
    # Exactly what OwnerReplies sends to the engine (no entity_id / version).
    return {
        "change": p["change"],
        "timezone": p["timezone"],
        "current_value": p.get("current_value"),
    }


def judge(row, reply):
    """Return (success, predicted_label, reason)."""
    if reply.status != "OK":
        return False, "UNAVAILABLE", f"engine unavailable: {reply.error_code}"
    want = CATEGORIES[row["category"]]
    if reply.intent != want:
        return False, reply.intent, f"intent {reply.intent}, expected {want}"
    # Right intent but hedged: OwnerReplies would downgrade it to NEEDS_CLARIFICATION.
    if reply.needs_clarification:
        return False, "CLARIFY", "needs_clarification=true"
    if not reply.scope_match:
        return False, "CLARIFY", "scope_match=false"
    target = row["proposal"]["change"]["date"]
    if reply.date and reply.date != target:
        return False, reply.intent, f"date {reply.date} != {target}"
    if want == "EDIT" and reply.hours.replace(" ", "") != row["expected_hours"]:
        return False, reply.intent, f"hours {reply.hours!r} != {row['expected_hours']!r}"
    if want in ("APPLY", "REJECT") and reply.hours:
        return False, reply.intent, f"unexpected hours {reply.hours!r}"
    return True, reply.intent, "ok"


def evaluate(engine, rows):
    results, latencies = [], []
    for row in rows:
        reply = engine.interpret(context_for(row), row["reply"])
        ok, predicted, reason = judge(row, reply)
        latencies.append(reply.latency_ms)
        results.append({"id": row["id"], "language": row["language"],
                        "category": row["category"], "reply": row["reply"],
                        "predicted": predicted, "success": ok, "reason": reason})
    return build_report(results, latencies)


def rate(items):
    return round(sum(r["success"] for r in items) / len(items), 4) if items else None


def build_report(results, latencies):
    by_cat, by_lang = defaultdict(list), defaultdict(list)
    confusion = defaultdict(Counter)
    for r in results:
        by_cat[r["category"]].append(r)
        by_lang[r["language"]].append(r)
        confusion[r["category"]][r["predicted"]] += 1
    lat = sorted(latencies)
    return {
        "total": len(results),
        "accuracy": rate(results),
        "unavailable_rate": round(sum(r["predicted"] == "UNAVAILABLE" for r in results) / len(results), 4),
        "per_category": {k: {"n": len(v), "accuracy": rate(v)} for k, v in sorted(by_cat.items())},
        "per_language": {k: {"n": len(v), "accuracy": rate(v)} for k, v in sorted(by_lang.items())},
        "confusion": {k: dict(v) for k, v in sorted(confusion.items())},
        "latency_ms": {"p50": lat[len(lat) // 2], "p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))],
                       "mean": round(statistics.fmean(lat))},
        "failures": [r for r in results if not r["success"]],
    }


def print_report(rep):
    print(f"\nOverall: {rep['accuracy']:.1%} of {rep['total']}  (unavailable {rep['unavailable_rate']:.1%})")
    for title, key in (("Category", "per_category"), ("Language", "per_language")):
        for k, v in rep[key].items():
            print(f"  {title:8} {k:8} {v['accuracy']:.1%}  (n={v['n']})")
    print("Confusion (rows=true category, cols=predicted intent):")
    for k, v in rep["confusion"].items():
        print(f"  {k:7}", dict(v))
    l = rep["latency_ms"]
    print(f"Latency ms: p50={l['p50']} p95={l['p95']} mean={l['mean']}")
    for f in rep["failures"][:15]:
        print(f"  FAIL [{f['category']}/{f['language']}] {f['reply']!r}: {f['reason']}")
    if len(rep["failures"]) > 15:
        print(f"  ... {len(rep['failures']) - 15} more in --report")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--model", default="runtime/models/gemma-2-2b-reply.gguf")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--min-accuracy", type=float, default=None)
    ap.add_argument("--report")
    args = ap.parse_args(argv)
    sys.path.insert(0, ".")
    from app.teammate.local_engine import LocalGemmaEngine

    engine = LocalGemmaEngine(args.model, timeout=args.timeout)
    if not engine.configured:
        sys.exit(f"Could not load model {args.model} (file missing or llama-cpp-python not installed)")
    rep = evaluate(engine, load_dataset(args.dataset))
    print_report(rep)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
    if args.min_accuracy is not None and rep["accuracy"] < args.min_accuracy:
        sys.exit(f"FAILED: accuracy {rep['accuracy']:.1%} < required {args.min_accuracy:.1%}")


if __name__ == "__main__":
    main()
