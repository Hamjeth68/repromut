"""E2 final analysis: the pre-registered primary analysis plus the pre-declared sensitivity analyses.

Usage: python e2/harness/final_analysis.py <results_dir> <out_json>
Primary = repromut.e2.analysis.analyse on all case records (protocol sections 8-9).
Sensitivity (protocol section 11, plus D13 and the author-level check from LICENSE-REVIEW):
  tolerance rtol 1e-4 / 1e-8 (labels recomputed from stored outputs), D with k=1 / k=3,
  intermittent counted positive, crash/timeout counted positive, equivalent mutations as negatives,
  baseline-nondeterministic repositories included (per-run comparison), repository macro-average,
  pilot repositories excluded, one repository per author.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from repromut.e2 import analysis as AN
from repromut.e2 import outputs as O
from repromut.e2.oracle import Observed, label

PILOT = {"sagnik1511/Tabular-AutoML", "fmind/mlops-python-package"}


def load(d):
    bases, cases = {}, []
    for f in sorted(Path(d).glob("*.jsonl")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if r["case_id"] == "baseline":
                bases[r["repo"]] = r
            else:
                cases.append(r)
    return bases, cases


def obs(statuses, outs):
    return [Observed(s, O.from_jsonable(o) if o is not None else None) for s, o in zip(statuses, outs)]


def relabel(bases, cases, rtol, require_stable=True):
    out = []
    for r in cases:
        b = bases[r["repo"]]
        if "oracle_outputs" not in r:
            out.append(r)
            continue
        base = obs(b["statuses"], b["outputs"])
        runs = obs(r["oracle_statuses"], r["oracle_outputs"])
        if require_stable:
            lab, _ = label(base, runs, rtol=rtol)
        else:   # per-run comparison: a run "differs" only if it differs from every baseline run
            ok = [x for x in base if x.status == "ok"]
            if not ok or any(x.status != "ok" for x in runs):
                lab = r["label"]
            else:
                diff = [all(not O.equal(x.outputs, y.outputs, rtol, O.ATOL) for y in ok) for x in runs]
                lab = "stable_change" if all(diff) else ("unchanged" if not any(diff) else "intermittent_change")
        out.append({**r, "label": lab})
    return out


def with_flag(cases, key):
    return [{**r, "flags": {**r["flags"], "D": r["flags"][key]}} for r in cases]


def summary(cases, reps=10_000):
    res = AN.analyse(cases, reps=reps)
    keep = ("n_pos", "n_pos_repos", "n_neg", "recall_D", "recall_S1", "recall_diff", "recall_diff_ci",
            "fpr_D", "fpr_S1", "fpr_diff", "fpr_diff_ci", "fpr_D_wilson", "fpr_rule", "fpr_acceptable",
            "mcnemar_p_pos", "minimum_evidence", "verdict")
    return {k: res[k] for k in keep}


def secondary(cases):
    pos, neg = AN.primary_sets(cases)
    rate = lambda rows, a: (sum(bool(r["flags"][a]) for r in rows), len(rows))
    return {a: {"recall": rate(pos, a), "false_alarms": rate(neg, a)} for a in ("D", "S1", "S2", "C1", "C2")}


def main(d, out):
    bases, cases = load(d)
    res = {"primary": summary(cases), "auditors_counts": secondary(cases)}
    by_label = defaultdict(lambda: defaultdict(int))
    for r in cases:
        by_label[f"{r['intent']}:{r['family']}"][r["label"]] += 1
    res["labels_by_family"] = {k: dict(v) for k, v in by_label.items()}
    res["repositories"] = {repo: {"baseline_statuses": b["statuses"], "baseline_stable": b["stable"]}
                           for repo, b in bases.items()}
    S = {}
    S["tolerance_rtol_1e-4"] = summary(relabel(bases, cases, 1e-4), 2000)
    S["tolerance_rtol_1e-8"] = summary(relabel(bases, cases, 1e-8), 2000)
    S["D_k1"] = summary(with_flag(cases, "D_k1"), 2000)
    S["D_k3"] = summary(with_flag(cases, "D_k3"), 2000)
    S["intermittent_as_positive"] = summary([{**r, "label": "stable_change" if r["label"] == "intermittent_change" else r["label"]} for r in cases], 2000)
    S["crash_timeout_as_positive"] = summary([{**r, "label": "stable_change" if (r["intent"] == "positive" and r["label"] in ("crash", "timeout")) else r["label"]} for r in cases], 2000)
    S["equivalent_mutations_as_negatives"] = summary([{**r, "intent": "control" if (r["intent"] == "positive" and r["label"] == "unchanged") else r["intent"]} for r in cases], 2000)
    S["nondeterministic_repos_included"] = summary(relabel(bases, cases, O.RTOL, require_stable=False), 2000)
    S["pilot_repos_excluded"] = summary([r for r in cases if r["repo"] not in PILOT], 2000)
    seen, one = set(), []
    for r in cases:
        author = r["repo"].split("/")[0]
        if author == "AmirhosseinHonardoust" and r["repo"] != "AmirhosseinHonardoust/Subscription-Loyalty-Risk-Radar":
            continue      # keep the first in seeded order (P1 #170)
        one.append(r)
    S["one_repository_per_author"] = summary(one, 2000)
    pos, _ = AN.primary_sets(cases)
    per = defaultdict(list)
    for r in pos:
        per[r["repo"]].append(r)
    S["macro_average_recall"] = {a: float(np.mean([np.mean([bool(x["flags"][a]) for x in v]) for v in per.values()])) if per else None
                                 for a in ("D", "S1", "S2")}
    res["sensitivity"] = S
    Path(out).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({"primary": res["primary"], "auditors_counts": res["auditors_counts"]}, indent=1, default=float))
    for k, v in S.items():
        print(k, {kk: v[kk] for kk in ("n_pos", "n_neg", "recall_D", "recall_S1", "fpr_D", "verdict")} if "verdict" in v else v)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
