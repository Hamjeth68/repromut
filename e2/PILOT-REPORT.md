# E2 pilot report

**Status: pilot-tested.** Two repositories were run under the registered protocol (local commit `5dbf087`) on 2026-11-09. Section 10 of the protocol requires pilot results to be reported separately; they are **not** confirmatory evidence. The full study has not started.

## What ran

| | Tabular-AutoML (P1 #14) | fmind/mlops-python-package (P1 #58) |
|---|---|---|
| Python / image | 3.10-slim; hash-locked `requirements.txt` (scikit-learn 1.0.2, LightGBM built from source in the build stage) | 3.14-slim; `uv sync --frozen --no-editable` from the committed `uv.lock` (104 packages, scikit-learn 1.9.1, mlflow 3.17.2) |
| Invocation | `python test.py` | `bikes confs/pipeline.yaml` (tuning → training → evaluation → promotion → inference → explanations) |
| Result definition | stdout numbers | stdout numbers, plus predictions and explanation parquet files (converted to numbers in-container) |
| Run time | ~2–4 s per run | ~35 s per run, ~4 min per case (6 runs) |
| Cases | M-PATH ×2; C-ENV, C-CACHE, C-PATH (C-DEP not constructible, D4) | M-CACHE, M-ENV, M-PATH; C-ENV, C-CACHE, C-PATH, C-DEP |

Every run was offline and non-root, with a read-only root filesystem, no capabilities, 2 CPU / 3 GiB, and only its fresh work copy mounted. No run failed for repository reasons. One configuration error in our harness (D7) produced Docker `infra_failure`s; these were labelled correctly as such and were not counted.

## Results (final pilot attempt, after D1, D5 and D6)

| Repository | Case | Intent | Oracle label | S1 | S2 | D |
|---|---|---|---|---|---|---|
| fmind | M-PATH-1 (shadow training data in the working directory) | positive | **stable_change** | – | flag | **flag** |
| fmind | M-CACHE-1 (stale local MLflow store) | positive | unchanged (equivalent mutation) | – | flag | – |
| fmind | M-ENV-1 (`MLFLOW_TRACKING_URI` → stale store) | positive | unchanged (equivalent mutation) | – | flag | – |
| fmind | C-ENV, C-CACHE, C-PATH, C-DEP | control | unchanged (4/4) | – | flag (4/4) | – (0/4) |
| Tabular-AutoML | all 5 cases | — | indeterminate: the **baseline is nondeterministic** | – | flag | flag |

Pilot counts (fmind only, since Tabular's baseline is not stable): 1 positive, 4 negatives. D found 1/1 positives with 0/4 false alarms. S1 found 0/1 with 0/4 false alarms. S2 flagged all 7 cases, including every control. These numbers are far below the minimum-evidence rule and say nothing about H1.

## What the pilot taught us (all logged in `DEVIATIONS.md`)

1. **Clock stamps in output (D1).** An XGBoost warning prints the wall-clock time (`[03:49:44]`), so identical runs looked different. Lines with clock stamps are now excluded for all repositories.
2. **Identifiers are not results (D5).** Under the first adapter, fmind's stale MLflow store was labelled `stable_change`. The only difference was the printed model version (1 → 2); the predictions and explanations were identical (`harness/diagnose_case.py`). Identifier lines are now excluded. Under the corrected adapter, both MLflow mutations are **equivalent mutations**: the pipeline retrains and promotes a new model, so the stale store has no effect on the result. Without this check the pilot would have overstated what the hidden state does.
3. **Store every run's outputs (D6).** This lets labels be audited and the tolerance sensitivity analyses be recomputed.
4. **Nondeterministic baselines exist.** Tabular-AutoML gives different scores on identical runs (unseeded estimators; e.g. regression MSE 0.313 vs 0.324). The protocol handles this by marking its cases `indeterminate` and excluding them from the primary analysis. It is still reported, and it enters sensitivity analysis 5.
5. **S2 flags every control by design.** S2 includes the environment map, the working-directory path and untracked files, so the controls that change exactly those things trigger it. This is expected and will be reported as S2's false-alarm rate.
6. **C-DEP can be impossible.** No binary scikit-learn wheel exists below 1.0.2 for cp310/aarch64 (D4).

## Implication for the full study

The main risk is the **number of positives**, not the harness. In the pilot, 1 of 3 constructible positive-intent mutations changed the result. With 12 remaining repositories, most having only an M-PATH channel, the registered minimum of 12 stable positives from at least 4 repositories may not be reached. The verdict would then be **inconclusive**, and it will be reported that way.

The remaining repositories' case plans are not yet registered, so a legitimate response is to register, before any of their outcome runs, one M-PATH case per relative input file (as done for Tabular-AutoML). This raises the number of designed cases without looking at outcomes.

## Reproduce

```
python e2/harness/prep_fmind.py <fmind image id>                       # stale/shadow artifacts (fmind only)
python e2/harness/run_plan.py e2/plans/<slug>.json <results_dir>        # baseline + all cases
python e2/harness/summarise.py <results_dir>                            # table + pre-registered analysis
```

Image recipes, lock files and package lists are in `e2/env/builds/`. Raw records are in `e2/results/pilot/`. Superseded attempts are kept with `attempt` in their file names.
