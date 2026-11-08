"""Frozen predictions; inference never reads labels, simulator truth or runtime state."""

import argparse
import csv
import io
from pathlib import Path
from .domain import DataStore, evaluate_context, parse_dt
from . import POLICY


def export_text(data=None, root=None):
	root_path = Path(root or Path(__file__).resolve().parents[1])
	data = (
		data
		if data is not None and data.cutoff == POLICY["P14_evaluation"]["cutoff"]
		else DataStore(str(root_path / "data"), POLICY["P14_evaluation"]["cutoff"])
	)
	output_stream = io.StringIO()
	csv_writer = csv.writer(output_stream)
	csv_writer.writerow(["entity_id", "date", "action", "hours"])
	with (root_path / "evaluation/targets_2026.csv").open(encoding="utf-8") as file:
		for row in csv.DictReader(file):
			context = data.context(
				row["entity_id"],
				row["date"],
				row["day_key"],
				row.get("day_type", "PUBLIC_HOLIDAY"),
			)
			result = evaluate_context(
				context, parse_dt(POLICY["P14_evaluation"]["cutoff"])
			)
			action, change = result["action"], result.get("change")
			if result.get("purpose") == "OPPORTUNITY":
				action = "NO_ACTION"
			csv_writer.writerow(
				[
					row["entity_id"],
					row["date"],
					action,
					change["hours"] if action == "SUGGEST" else "",
				]
			)
	return output_stream.getvalue()


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--output", default="outputs/product/predictions_2026.csv")
	parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
	args = parser.parse_args()
	prediction_text = export_text(root=args.root)
	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(prediction_text, encoding="utf-8")
	print(f"Wrote {len(prediction_text.splitlines()) - 1} frozen target predictions to {output_path}")


if __name__ == "__main__":
	main()
