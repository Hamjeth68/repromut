# E1 external validation: scikit-learn 1.7.2 example scripts

Pre-registered in `PROTOCOL-E1-external.md` (commit `382e5fd`, pushed before any run).

- Screened (sampled order): 114 scripts; eligible sample: 30
- Screening outcomes: {'E3 prints no numeric result': 51, 'eligible': 30, 'E1 network/data download': 27, 'E2 failed/timeout': 4, 'E4 baseline not reproducible run-to-run': 2}
- **Naturally non-reproducible run-to-run (E4): 2 of 32 runnable, number-printing scripts**: cross_decomposition/plot_compare_cross_decomposition.py, datasets/plot_random_multilabel_dataset.py
- Median baseline runtime: 2.8 s

## Primary analysis (as registered: crash/timeout = changed)

Cases: 199; oracle says result changed in 76; crashed 9.

| Auditor | Recall (95% CI) | FPR (95% CI) | TP/FN/FP/TN |
|---|---|---|---|
| seed_only | 71.1% (60.0%–80.0%) | 1.6% (0.4%–5.7%) | 54/22/2/121 |
| static_manifest | 93.4% (85.5%–97.2%) | 6.5% (3.3%–12.3%) | 71/5/8/115 |
| dynamic | 98.7% (92.9%–99.8%) | 0.0% (0.0%–3.0%) | 75/1/0/123 |

| Operator | Intent | n | Result changed | seed-only flags | static flags | dynamic flags |
|---|---|---|---|---|---|---|
| seed_removed | positive | 28 | 27 | 28 | 28 | 26 |
| seed_changed | positive | 28 | 27 | 28 | 28 | 27 |
| split_changed | positive | 18 | 16 | 0 | 18 | 16 |
| cv_changed | positive | 3 | 1 | 0 | 3 | 1 |
| iterations_reduced | positive | 2 | 0 | 0 | 2 | 0 |
| comment_added | control | 30 | 2 | 0 | 0 | 2 |
| reformatted | control | 30 | 2 | 0 | 0 | 2 |
| threads_1 | control | 30 | 0 | 0 | 0 | 0 |
| workdir_moved | control | 30 | 1 | 0 | 0 | 1 |

- dynamic_vs_static_manifest: discordant 5 vs 1, exact McNemar p = 0.219

- dynamic_vs_seed_only: discordant 22 vs 1, exact McNemar p = 5.72e-06
- Dynamic/oracle disagreements: [{'script': 'feature_selection/plot_rfe_with_cross_validation.py', 'operator': 'seed_removed', 'oracle': True, 'dynamic': False}]

## Sensitivity analysis (deviation: crashed units re-run once with 1 worker)

Cases: 199; oracle says result changed in 69; crashed 0.

| Auditor | Recall (95% CI) | FPR (95% CI) | TP/FN/FP/TN |
|---|---|---|---|
| seed_only | 75.4% (64.0%–84.0%) | 3.1% (1.2%–7.6%) | 52/17/4/126 |
| static_manifest | 100.0% (94.7%–100.0%) | 7.7% (4.2%–13.6%) | 69/0/10/120 |
| dynamic | 98.6% (92.2%–99.7%) | 0.0% (0.0%–2.9%) | 68/1/0/130 |

| Operator | Intent | n | Result changed | seed-only flags | static flags | dynamic flags |
|---|---|---|---|---|---|---|
| seed_removed | positive | 28 | 26 | 28 | 28 | 25 |
| seed_changed | positive | 28 | 26 | 28 | 28 | 26 |
| split_changed | positive | 18 | 16 | 0 | 18 | 16 |
| cv_changed | positive | 3 | 1 | 0 | 3 | 1 |
| iterations_reduced | positive | 2 | 0 | 0 | 2 | 0 |
| comment_added | control | 30 | 0 | 0 | 0 | 0 |
| reformatted | control | 30 | 0 | 0 | 0 | 0 |
| threads_1 | control | 30 | 0 | 0 | 0 | 0 |
| workdir_moved | control | 30 | 0 | 0 | 0 | 0 |

- dynamic_vs_static_manifest: discordant 0 vs 1, exact McNemar p = 1

- dynamic_vs_seed_only: discordant 17 vs 1, exact McNemar p = 0.000145
- Dynamic/oracle disagreements: [{'script': 'feature_selection/plot_rfe_with_cross_validation.py', 'operator': 'seed_removed', 'oracle': True, 'dynamic': False}]
