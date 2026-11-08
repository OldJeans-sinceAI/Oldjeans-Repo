"""Frozen predictions; inference never reads labels, simulator truth or runtime state."""

import argparse, csv, io
from pathlib import Path
from .domain import DataStore, evaluate_context, parse_dt
from . import POLICY


def export_text(data=None, root=None):
 r = Path(root or Path(__file__).resolve().parents[1])
 data = data if data is not None and data.cutoff == POLICY["P14_evaluation"]["cutoff"] else DataStore(str(r / "data"), POLICY["P14_evaluation"]["cutoff"])
 s = io.StringIO()
 w = csv.writer(s)
 w.writerow(["entity_id", "date", "action", "hours"])
 with (r / "evaluation/targets_2026.csv").open() as f:
  for rw in csv.DictReader(f):
   c = data.context(rw["entity_id"], rw["date"], rw["day_key"], rw.get("day_type", "PUBLIC_HOLIDAY"))
   o = evaluate_context(c, parse_dt(POLICY["P14_evaluation"]["cutoff"]))
   act, ch = o["action"], o.get("change")
   if o.get("purpose") == "OPPORTUNITY": act = "NO_ACTION"
   w.writerow([rw["entity_id"], rw["date"], act, ch["hours"] if act == "SUGGEST" else ""])
 return s.getvalue()


def main():
 p = argparse.ArgumentParser()
 p.add_argument("--output", default="outputs/product/predictions_2026.csv")
 p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
 a = p.parse_args()
 t = export_text(root=a.root)
 o = Path(a.output)
 o.parent.mkdir(parents=True, exist_ok=True)
 o.write_text(t, encoding="utf-8")
 print(f"Wrote {len(t.splitlines()) - 1} frozen target predictions to {o}")


if __name__ == "__main__":
 main()
