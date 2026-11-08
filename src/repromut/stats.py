"""Small, dependency-light statistics used in reporting."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """Two-sided exact McNemar p-value from discordant counts."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    return float(sps.binomtest(a_only, n, 0.5, alternative="two-sided").pvalue)


def paired_bootstrap_diff(a: np.ndarray, b: np.ndarray, reps: int = 2000,
                          seed: int = 0) -> tuple[float, float, float]:
    """Mean difference a-b with a percentile bootstrap 95% CI over paired cases."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != b.shape or a.size == 0:
        raise ValueError("paired arrays must be non-empty and equal length")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(reps, a.size))
    diffs = a[idx].mean(axis=1) - b[idx].mean(axis=1)
    return (float(a.mean() - b.mean()), float(np.percentile(diffs, 2.5)),
            float(np.percentile(diffs, 97.5)))


def confusion(flags: list[bool], truth: list[bool]) -> dict:
    tp = sum(f and t for f, t in zip(flags, truth))
    fn = sum((not f) and t for f, t in zip(flags, truth))
    fp = sum(f and (not t) for f, t in zip(flags, truth))
    tn = sum((not f) and (not t) for f, t in zip(flags, truth))
    recall = tp / (tp + fn) if tp + fn else float("nan")
    precision = tp / (tp + fp) if tp + fp else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if tp and not math.isnan(precision) else 0.0)
    fpr = fp / (fp + tn) if fp + tn else float("nan")
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "recall": recall,
            "recall_ci95": wilson(tp, tp + fn), "precision": precision,
            "precision_ci95": wilson(tp, tp + fp), "f1": f1, "fpr": fpr,
            "fpr_ci95": wilson(fp, fp + tn)}
