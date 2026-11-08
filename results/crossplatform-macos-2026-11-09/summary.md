# ReproMut benchmark results

> **EXPLORATORY - development run, not preregistered.** Synthetic technical verification only; see docs/limitations.md.

- Experiments: 28; cases: 452 (272 result-changing, 180 controls)
- Oracle agreement with declared labels: 452/452
- Environment: Python 3.12.13, numpy 2.5.4, scikit-learn 1.9.1, macOS-27.2-arm64-arm-64bit

## Detection

| Method | TP/positives | Recall (95% CI) | FP/controls | FPR (95% CI) | Precision | F1 | Localised | Median time |
|---|---|---|---|---|---|---|---|---|
| no_audit | 0/272 | 0.0% (0.0%–1.4%) | 0/180 | 0.0% (0.0%–2.1%) | n/a | 0.000 | 0/0 | 2.7 ms |
| seed_only | 80/272 | 29.4% (24.3%–35.1%) | 0/180 | 0.0% (0.0%–2.1%) | 100.0% | 0.455 | 80/80 | 0.1 ms |
| static_manifest | 198/272 | 72.8% (67.2%–77.7%) | 12/180 | 6.7% (3.9%–11.3%) | 94.3% | 0.822 | 198/198 | 0.2 ms |
| dynamic | 272/272 | 100.0% (98.6%–100.0%) | 0/180 | 0.0% (0.0%–2.1%) | 100.0% | 1.000 | 272/272 | 6.0 ms |
| combined | 272/272 | 100.0% (98.6%–100.0%) | 12/180 | 6.7% (3.9%–11.3%) | 95.8% | 0.978 | 272/272 | 6.1 ms |

## Recall by mutation family

| Family | no_audit | seed_only | static_manifest | dynamic | combined |
|---|---|---|---|---|---|
| caching | 0/28 | 0/28 | 0/28 | 28/28 | 28/28 |
| config-mismatch | 0/24 | 0/24 | 24/24 | 24/24 | 24/24 |
| data-generation | 0/56 | 0/56 | 56/56 | 56/56 | 56/56 |
| data-order | 0/8 | 0/8 | 8/8 | 8/8 | 8/8 |
| dependency | 0/18 | 0/18 | 0/18 | 18/18 | 18/18 |
| hidden-config | 0/28 | 0/28 | 0/28 | 28/28 | 28/28 |
| numeric | 0/30 | 0/30 | 30/30 | 30/30 | 30/30 |
| random-state | 0/80 | 80/80 | 80/80 | 80/80 | 80/80 |

## Paired comparison: dynamic vs seed-only (positives)

- Recall difference: 70.6% (bootstrap 95% CI 65.1%–76.1%)
- Discordant: dynamic-only 192, seed-only-only 0; exact McNemar p = 3.19e-58

## Draft hypothesis thresholds (exploratory)

- Recall >= 90.0%: True
- Gain over seed-only >= 30.0%: True
- FPR < 5.0%: True

Note: the dynamic auditor and the oracle both execute the package, so high dynamic recall on deterministic mutations is expected by construction. The informative comparisons are the gaps between static and dynamic methods, the localisation accuracy, hash-vs-tolerance disagreements, and the cost of execution.
