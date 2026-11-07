"""Copy only the team's interpreter source, never its .env or runtime data."""

from pathlib import Path
import argparse

p = argparse.ArgumentParser()
p.add_argument("source", type=Path)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
source = a.source.resolve() / "reply_engine.py"
(root / "app/teammate/reply_engine.py").write_bytes(source.read_bytes())
print("Updated team interpreter snapshot. Run product and team tests.")
