"""Analyse external-validation study E1 (pre-registered in PROTOCOL-E1-external.md).

Usage: python paper/analyze_e1.py results/e1-sklearn-examples
Writes summary.json and summary.md into the results directory.
"""

import collections
import json
import statistics
import sys
from pathlib import Path

from repromut.stats import mcnemar_exact, wilson

METHODS = ("seed_only", "static_manifest", "dynamic")
OPS = ("seed_removed", "seed_changed", "split_changed", "cv_changed", "iterations_reduced",
       "comment_added", "reformatted", "threads_1", "workdir_moved")
TARGET = 30


def load(d: Path):
    scr = {json.loads(l)["order"]: json.loads(l) for l in (d / "screening.jsonl").read_text().splitlines()}
    chosen, i = [], 0
    while len(chosen) < TARGET:
        if scr[i]["eligible"]:
            chosen.append(scr[i])
        i += 1
    prefix = [scr[k] for k in range(i)]
    ids = {r["order"] for r in chosen}
    rows = [json.loads(l) for l in (d / "cases.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r["order"] in ids]
    rerun_f = d / "cases_crash_rerun.jsonl"
    rerun = {(r["order"], r["operator"]): r for r in
             (json.loads(l) for l in rerun_f.read_text().splitlines())} if rerun_f.exists() else {}
    return prefix, chosen, rows, rerun


def evaluate(rows):
    out = {"n": len(rows), "truth_changed": sum(r["oracle_changed"] for r in rows),
           "crashed": sum(r["crashed"] for r in rows), "methods": {}, "operators": {}}
    for m in METHODS:
        tp = sum(r[m] and r["oracle_changed"] for r in rows)
        fn = sum((not r[m]) and r["oracle_changed"] for r in rows)
        fp = sum(r[m] and not r["oracle_changed"] for r in rows)
        tn = sum((not r[m]) and not r["oracle_changed"] for r in rows)
        out["methods"][m] = {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
                             "recall": tp / (tp + fn), "recall_ci95": wilson(tp, tp + fn),
                             "fpr": fp / (fp + tn), "fpr_ci95": wilson(fp, fp + tn)}
    pos = [r for r in rows if r["oracle_changed"]]
    for other in ("static_manifest", "seed_only"):
        a = sum(r["dynamic"] and not r[other] for r in pos)
        b = sum(r[other] and not r["dynamic"] for r in pos)
        out[f"dynamic_vs_{other}"] = {"dynamic_only": a, "other_only": b, "mcnemar_p": mcnemar_exact(a, b)}
    for op in OPS:
        rs = [r for r in rows if r["operator"] == op]
        if rs:
            out["operators"][op] = {"n": len(rs), "intent": rs[0]["intent"],
                                    "changed": sum(r["oracle_changed"] for r in rs),
                                    **{m: sum(r[m] for r in rs) for m in METHODS}}
    out["dynamic_oracle_disagreements"] = [
        {"script": r["script"], "operator": r["operator"], "oracle": r["oracle_changed"], "dynamic": r["dynamic"]}
        for r in rows if r["dynamic"] != r["oracle_changed"]]
    return out


def pct(x):
    return f"{100 * x:.1f}%"


def md(summary):
    p, s = summary["primary"], summary["sensitivity"]
    L = ["# E1 external validation: scikit-learn 1.7.2 example scripts", "",
         "Pre-registered in `PROTOCOL-E1-external.md` (commit `382e5fd`, pushed before any run).", "",
         f"- Screened (sampled order): {summary['screened_prefix']} scripts; eligible sample: {TARGET}",
         f"- Screening outcomes: {summary['screening']}",
         f"- **Naturally non-reproducible run-to-run (E4): {summary['e4_count']} of "
         f"{summary['e4_denominator']} runnable, number-printing scripts**: {', '.join(summary['e4_scripts'])}",
         f"- Median baseline runtime: {summary['median_baseline_s']:.1f} s", ""]
    for title, ev in (("Primary analysis (as registered: crash/timeout = changed)", p),
                      ("Sensitivity analysis (deviation: crashed units re-run once with 1 worker)", s)):
        L += [f"## {title}", "",
              f"Cases: {ev['n']}; oracle says result changed in {ev['truth_changed']}; crashed {ev['crashed']}.", "",
              "| Auditor | Recall (95% CI) | FPR (95% CI) | TP/FN/FP/TN |", "|---|---|---|---|"]
        for m, c in ev["methods"].items():
            L.append(f"| {m} | {pct(c['recall'])} ({pct(c['recall_ci95'][0])}–{pct(c['recall_ci95'][1])}) "
                     f"| {pct(c['fpr'])} ({pct(c['fpr_ci95'][0])}–{pct(c['fpr_ci95'][1])}) "
                     f"| {c['tp']}/{c['fn']}/{c['fp']}/{c['tn']} |")
        L += ["", "| Operator | Intent | n | Result changed | seed-only flags | static flags | dynamic flags |",
              "|---|---|---|---|---|---|---|"]
        for op, o in ev["operators"].items():
            L.append(f"| {op} | {o['intent']} | {o['n']} | {o['changed']} | {o['seed_only']} "
                     f"| {o['static_manifest']} | {o['dynamic']} |")
        for k in ("dynamic_vs_static_manifest", "dynamic_vs_seed_only"):
            d = ev[k]
            L.append(f"\n- {k}: discordant {d['dynamic_only']} vs {d['other_only']}, exact McNemar p = {d['mcnemar_p']:.3g}")
        L.append(f"- Dynamic/oracle disagreements: {ev['dynamic_oracle_disagreements']}")
        L.append("")
    return "\n".join(L)


def main(d):
    d = Path(d)
    prefix, chosen, rows, rerun = load(d)
    reasons = collections.Counter((r["reason"].split(":")[0] or "eligible") for r in prefix)
    e4 = [r["script"] for r in prefix if r.get("naturally_nondeterministic")]
    runnable_numeric = sum(1 for r in prefix if r["eligible"] or r.get("naturally_nondeterministic"))
    sens_rows = [rerun.get((r["order"], r["operator"]), r) if r["crashed"] else r for r in rows]
    summary = {"screened_prefix": len(prefix), "screening": dict(reasons), "e4_scripts": e4,
               "e4_count": len(e4), "e4_denominator": runnable_numeric,
               "median_baseline_s": statistics.median(r["baseline_seconds"] for r in chosen),
               "primary": evaluate(rows), "sensitivity": evaluate(sens_rows),
               "rerun_units": len(rerun)}
    (d / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (d / "summary.md").write_text(md(summary))
    print(md(summary))


if __name__ == "__main__":
    main(sys.argv[1])
