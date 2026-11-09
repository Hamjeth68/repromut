"""Summarise E2 case records (one JSONL per repository) into a Markdown table and per-auditor counts.

Usage: python e2/harness/summarise.py <results_dir> [--label pilot]
Descriptive only; the pre-registered analysis is repromut.e2.analysis.analyse().
"""
import json
import sys
from pathlib import Path

from repromut.e2 import analysis as AN


def load(results_dir: Path) -> tuple[list[dict], list[dict]]:
    bases, cases = [], []
    for f in sorted(results_dir.glob("*.jsonl")):
        if "attempt" in f.name:
            continue
        for line in f.read_text().splitlines():
            r = json.loads(line)
            (bases if r["case_id"] == "baseline" else cases).append(r)
    return bases, cases


def main(d: str) -> None:
    bases, cases = load(Path(d))
    print("| Repository | Baseline stable | Case | Intent | Oracle label | First divergence | S1 | S2 | D | C1 | C2 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    stable = {b["repo"]: b["stable"] for b in bases}
    yn = lambda v: "flag" if v else "-"
    for r in cases:
        f = r["flags"]
        print(f"| {r['repo']} | {'yes' if stable.get(r['repo']) else 'no'} | {r['case_id']} | {r['intent']} | {r['label']} | "
              f"{r['first_divergence'] or ''} | {yn(f['S1'])} | {yn(f['S2'])} | {yn(f['D'])} | {yn(f['C1'])} | {yn(f['C2'])} |")
    res = AN.analyse(cases, reps=10_000)
    print("\nPre-registered analysis on these records (pilot data; not the confirmatory result):")
    print(json.dumps({k: res[k] for k in ("n_pos", "n_pos_repos", "n_neg", "recall_D", "recall_S1", "fpr_D", "fpr_S1",
                                         "minimum_evidence", "verdict")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
