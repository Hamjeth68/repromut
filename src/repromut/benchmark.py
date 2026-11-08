"""End-to-end benchmark: build cases, run oracle and auditors, summarise."""

from __future__ import annotations

import json
import platform
import statistics
import tempfile
from pathlib import Path

import numpy as np
import scipy
import sklearn

from . import STAGES, __version__
from .auditors import (audit_combined, audit_dynamic, audit_none, audit_seed_only,
                       audit_static, make_record)
from .experiments import MASTER_SEED, build_catalog
from .mutations import POSITIVE, applicable
from .oracle import observe
from .runner import execute, write_package
from .stats import confusion, mcnemar_exact, paired_bootstrap_diff

METHODS = ("no_audit", "seed_only", "static_manifest", "dynamic", "combined")
HYPOTHESIS = {"min_recall": 0.90, "min_gain_over_seed_only": 0.30, "max_fpr": 0.05}


def environment_inventory() -> dict:
    return {
        "repromut": __version__, "python": platform.python_version(),
        "numpy": np.__version__, "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__, "platform": platform.platform(),
        "machine": platform.machine(), "master_seed": MASTER_SEED,
    }


def run_cases(smoke: bool = False, dynamic_repeats: int = 2, oracle_repeats: int = 3,
              progress=None) -> list[dict]:
    catalog = build_catalog()
    if smoke:
        catalog = [s for s in catalog if s.config["name"].endswith(
            ("bin-logreg-balanced", "reg-rf_reg-lownoise", "clu-kmeans-separated"))]
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="repromut-") as tmp:
        tmp = Path(tmp)
        for spec in catalog:
            name = spec.config["name"]
            baseline = execute(spec)
            record = make_record(spec.config, baseline)
            for mut in applicable(spec):
                mutant = mut.apply(spec)
                pkg = write_package(mutant, tmp / name / mut.id)
                obs = observe(mutant, baseline, repeats=oracle_repeats)
                st = audit_static(pkg, record)
                dy = audit_dynamic(pkg, record, repeats=dynamic_repeats)
                verdicts = [audit_none(pkg, record), audit_seed_only(pkg, record), st, dy,
                            audit_combined(pkg, record, static=st, dynamic=dy)]
                rows.append({
                    "experiment": name, "task": spec.config["task"],
                    "model": spec.config["model"]["name"], "mutation": mut.id,
                    "family": mut.family, "kind": mut.kind,
                    "declared_result_changing": mut.kind == POSITIVE,
                    "expected_stage": mut.expected_stage,
                    "oracle_result_changed": obs.result_changed,
                    "oracle_first_stage": obs.first_stage,
                    "verdicts": {v.method: {"flagged": v.flagged, "stage": v.stage,
                                            "reason": v.reason,
                                            "elapsed_s": round(v.elapsed_s, 6)}
                                 for v in verdicts},
                })
                if progress:
                    progress(len(rows))
    return rows


def summarise(rows: list[dict]) -> dict:
    truth = [r["declared_result_changing"] for r in rows]
    agree = sum(r["oracle_result_changed"] == r["declared_result_changing"] for r in rows)
    summary: dict = {
        "n_cases": len(rows),
        "n_positive": sum(truth),
        "n_control": len(rows) - sum(truth),
        "n_experiments": len({r["experiment"] for r in rows}),
        "oracle_agreement": {"agree": agree, "total": len(rows)},
        "methods": {},
    }
    for m in METHODS:
        flags = [r["verdicts"][m]["flagged"] for r in rows]
        c = confusion(flags, truth)
        tps = [r for r in rows if r["declared_result_changing"] and r["verdicts"][m]["flagged"]]
        loc = sum(r["verdicts"][m]["stage"] == r["expected_stage"] for r in tps)
        c["localization"] = {"correct": loc, "of_detected": len(tps)}
        fam: dict = {}
        for r in rows:
            if r["declared_result_changing"]:
                f = fam.setdefault(r["family"], [0, 0])
                f[0] += r["verdicts"][m]["flagged"]
                f[1] += 1
        c["recall_by_family"] = {k: {"detected": v[0], "total": v[1]} for k, v in sorted(fam.items())}
        times = [r["verdicts"][m]["elapsed_s"] for r in rows]
        c["elapsed_s"] = {"median": statistics.median(times), "max": max(times)}
        summary["methods"][m] = c

    pos = [r for r in rows if r["declared_result_changing"]]
    dyn = np.array([r["verdicts"]["dynamic"]["flagged"] for r in pos], float)
    seed = np.array([r["verdicts"]["seed_only"]["flagged"] for r in pos], float)
    diff, lo, hi = paired_bootstrap_diff(dyn, seed)
    summary["dynamic_vs_seed_only"] = {
        "recall_difference": diff, "ci95": [lo, hi],
        "dynamic_only": int(((dyn == 1) & (seed == 0)).sum()),
        "seed_only_only": int(((dyn == 0) & (seed == 1)).sum()),
        "mcnemar_exact_p": mcnemar_exact(int(((dyn == 1) & (seed == 0)).sum()),
                                         int(((dyn == 0) & (seed == 1)).sum())),
    }
    d = summary["methods"]["dynamic"]
    summary["hypothesis_check"] = {
        "status": "EXPLORATORY - development run, not preregistered",
        "thresholds": HYPOTHESIS,
        "recall_ok": d["recall"] >= HYPOTHESIS["min_recall"],
        "gain_ok": diff >= HYPOTHESIS["min_gain_over_seed_only"],
        "fpr_ok": d["fpr"] < HYPOTHESIS["max_fpr"],
    }
    return summary


def _pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.1f}%"


def render_markdown(summary: dict, env: dict) -> str:
    L = ["# ReproMut benchmark results", "",
         f"> **{summary['hypothesis_check']['status']}.** Synthetic technical "
         "verification only; see docs/limitations.md.", "",
         f"- Experiments: {summary['n_experiments']}; cases: {summary['n_cases']} "
         f"({summary['n_positive']} result-changing, {summary['n_control']} controls)",
         f"- Oracle agreement with declared labels: {summary['oracle_agreement']['agree']}"
         f"/{summary['oracle_agreement']['total']}",
         f"- Environment: Python {env['python']}, numpy {env['numpy']}, "
         f"scikit-learn {env['scikit_learn']}, {env['platform']}", "",
         "## Detection", "",
         "| Method | TP/positives | Recall (95% CI) | FP/controls | FPR (95% CI) | Precision | F1 | Localised | Median time |",
         "|---|---|---|---|---|---|---|---|---|"]
    for m, c in summary["methods"].items():
        rl, rh = c["recall_ci95"]
        fl, fh = c["fpr_ci95"]
        loc = c["localization"]
        L.append(
            f"| {m} | {c['tp']}/{c['tp'] + c['fn']} | {_pct(c['recall'])} ({_pct(rl)}–{_pct(rh)}) "
            f"| {c['fp']}/{c['fp'] + c['tn']} | {_pct(c['fpr'])} ({_pct(fl)}–{_pct(fh)}) "
            f"| {_pct(c['precision'])} | {c['f1']:.3f} | {loc['correct']}/{loc['of_detected']} "
            f"| {c['elapsed_s']['median'] * 1000:.1f} ms |")
    fams = sorted(summary["methods"]["dynamic"]["recall_by_family"])
    L += ["", "## Recall by mutation family", "",
          "| Family | " + " | ".join(summary["methods"]) + " |",
          "|---|" + "---|" * len(summary["methods"])]
    for f in fams:
        cells = []
        for c in summary["methods"].values():
            r = c["recall_by_family"][f]
            cells.append(f"{r['detected']}/{r['total']}")
        L.append(f"| {f} | " + " | ".join(cells) + " |")
    p = summary["dynamic_vs_seed_only"]
    h = summary["hypothesis_check"]
    L += ["", "## Paired comparison: dynamic vs seed-only (positives)", "",
          f"- Recall difference: {_pct(p['recall_difference'])} "
          f"(bootstrap 95% CI {_pct(p['ci95'][0])}–{_pct(p['ci95'][1])})",
          f"- Discordant: dynamic-only {p['dynamic_only']}, seed-only-only {p['seed_only_only']}; "
          f"exact McNemar p = {p['mcnemar_exact_p']:.3g}", "",
          "## Draft hypothesis thresholds (exploratory)", "",
          f"- Recall >= {_pct(h['thresholds']['min_recall'])}: {h['recall_ok']}",
          f"- Gain over seed-only >= {_pct(h['thresholds']['min_gain_over_seed_only'])}: {h['gain_ok']}",
          f"- FPR < {_pct(h['thresholds']['max_fpr'])}: {h['fpr_ok']}", "",
          "Note: the dynamic auditor and the oracle both execute the package, so high dynamic "
          "recall on deterministic mutations is expected by construction. The informative "
          "comparisons are the gaps between static and dynamic methods, the localisation "
          "accuracy, hash-vs-tolerance disagreements, and the cost of execution.", ""]
    return "\n".join(L)


def run_benchmark(out_dir: Path, smoke: bool = False, dynamic_repeats: int = 2,
                  oracle_repeats: int = 3, progress=None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = environment_inventory()
    rows = run_cases(smoke, dynamic_repeats, oracle_repeats, progress)
    summary = summarise(rows)
    summary["environment"] = env
    summary["settings"] = {"smoke": smoke, "dynamic_repeats": dynamic_repeats,
                           "oracle_repeats": oracle_repeats, "stages": list(STAGES)}
    with (out_dir / "cases.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(summary, env))
    return summary
