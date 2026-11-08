"""Frozen predictions; inference never reads labels, simulator truth or runtime state."""

import argparse, csv, io
from pathlib import Path
from .domain import DataStore, evaluate_context, parse_dt
from . import POLICY


def export_text(data=None, root=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    data = data if data is not None and data.cutoff == POLICY["P14_evaluation"]["cutoff"] else DataStore(str(root / "data"), POLICY["P14_evaluation"]["cutoff"])
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["entity_id", "date", "action", "hours"])
    with (root / "evaluation/targets_2026.csv").open() as f:
        for row in csv.DictReader(f):
            ctx = data.context(row["entity_id"], row["date"], row["day_key"], row.get("day_type", "PUBLIC_HOLIDAY"))
            out = evaluate_context(ctx, parse_dt(POLICY["P14_evaluation"]["cutoff"]))
            action = out["action"]
            change = out.get("change")
            if out.get("purpose") == "OPPORTUNITY":
                action = "NO_ACTION"
            writer.writerow([row["entity_id"], row["date"], action, change["hours"] if action == "SUGGEST" else ""])
    return stream.getvalue()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="outputs/product/predictions_2026.csv")
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    a = p.parse_args()
    text = export_text(root=a.root)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {len(text.splitlines()) - 1} frozen target predictions to {out}")


if __name__ == "__main__":
    main()
