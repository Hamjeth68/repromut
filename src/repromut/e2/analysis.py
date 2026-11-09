"""Pre-registered analysis (protocol sections 8-9): paired D vs S1 with repository-cluster bootstrap."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from repromut.stats import mcnemar_exact, wilson

SEED = 20261109
REPS = 10_000
MIN_POS, MIN_POS_REPOS, MIN_NEG = 12, 4, 35  # MIN_NEG raised from 20 (DEVIATIONS S14)
FPR_POINT_MAX, FPR_UPPER_MAX = 0.05, 0.10


def primary_sets(records: list[dict]) -> tuple[list[dict], list[dict]]:
    pos = [r for r in records if r["intent"] == "positive" and r["label"] == "stable_change"]
    neg = [r for r in records if r["intent"] == "control" and r["label"] == "unchanged"]
    return pos, neg


def _rate(rows: list[dict], aud: str) -> float:
    return float(np.mean([bool(r["flags"][aud]) for r in rows])) if rows else float("nan")


def cluster_bootstrap(rows: list[dict], a: str, b: str, reps: int = REPS, seed: int = SEED) -> tuple[float, float, int]:
    """95% percentile CI of rate(a) - rate(b), resampling repositories with replacement.

    Returns (lo, hi, n_valid). Resamples with no rows are skipped and counted out of n_valid.
    """
    by = defaultdict(list)
    for r in rows:
        by[r["repo"]].append((bool(r["flags"][a]), bool(r["flags"][b])))
    repos = sorted(by)
    if not repos:
        return float("nan"), float("nan"), 0
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(reps):
        pick = rng.integers(0, len(repos), len(repos))
        pairs = [p for i in pick for p in by[repos[i]]]
        if not pairs:
            continue
        arr = np.array(pairs, dtype=float)
        diffs.append(arr[:, 0].mean() - arr[:, 1].mean())
    if not diffs:
        return float("nan"), float("nan"), 0
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi), len(diffs)


def analyse(records: list[dict], a: str = "D", b: str = "S1", reps: int = REPS, seed: int = SEED) -> dict:
    pos, neg = primary_sets(records)
    pos_repos = {r["repo"] for r in pos}
    rec_a, rec_b = _rate(pos, a), _rate(pos, b)
    fpr_a, fpr_b = _rate(neg, a), _rate(neg, b)
    rlo, rhi, rn = cluster_bootstrap(pos, a, b, reps, seed)
    flo, fhi, fn = cluster_bootstrap(neg, a, b, reps, seed + 1)
    fp_a = sum(bool(r["flags"][a]) for r in neg)
    fp_b = sum(bool(r["flags"][b]) for r in neg)
    out = {
        "n_pos": len(pos), "n_pos_repos": len(pos_repos), "n_neg": len(neg),
        f"recall_{a}": rec_a, f"recall_{b}": rec_b, "recall_diff": rec_a - rec_b,
        "recall_diff_ci": [rlo, rhi], "recall_boot_valid": rn,
        f"fpr_{a}": fpr_a, f"fpr_{b}": fpr_b, "fpr_diff": fpr_a - fpr_b,
        "fpr_diff_ci": [flo, fhi], "fpr_boot_valid": fn,
        f"fpr_{a}_wilson": list(wilson(fp_a, len(neg))) if neg else [float("nan")] * 2,
        "mcnemar_p_pos": mcnemar_exact(sum(r["flags"][a] and not r["flags"][b] for r in pos),
                                        sum(r["flags"][b] and not r["flags"][a] for r in pos)) if pos else float("nan"),
    }
    enough = len(pos) >= MIN_POS and len(pos_repos) >= MIN_POS_REPOS and len(neg) >= MIN_NEG
    if fp_a == 0 and fp_b == 0 and neg:
        fpr_ok = out[f"fpr_{a}_wilson"][1] <= FPR_UPPER_MAX
        out["fpr_rule"] = "wilson_upper_bound (zero false positives in both arms)"
    else:
        fpr_ok = (out["fpr_diff"] <= FPR_POINT_MAX) and (not np.isnan(fhi) and fhi <= FPR_UPPER_MAX)
        out["fpr_rule"] = "point<=5pp and cluster-bootstrap upper<=10pp"
    out["fpr_acceptable"] = bool(fpr_ok)
    out["minimum_evidence"] = bool(enough)
    if not enough:
        out["verdict"] = "inconclusive"
    elif rlo > 0 and fpr_ok:
        out["verdict"] = "supported"
    else:
        out["verdict"] = "not_supported"
    return out
