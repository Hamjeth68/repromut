"""Compare two benchmark runs case by case, ignoring timing fields.

Usage: python compare.py [RUN_A_cases.jsonl] [RUN_B_cases.jsonl]
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "dev-2026-11-08" / "cases.jsonl"
B = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "cases.jsonl"


def load(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        for verdict in row["verdicts"].values():
            verdict.pop("elapsed_s", None)
    return rows


a, b = load(A), load(B)
differing = [(x["experiment"], x["mutation"]) for x, y in zip(a, b) if x != y]
print(f"cases: {len(a)} vs {len(b)}; differing (timings excluded): {len(differing)}")
for item in differing[:20]:
    print("  ", item)
sys.exit(0 if len(a) == len(b) and not differing else 1)
