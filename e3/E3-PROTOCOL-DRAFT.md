# E3 protocol: hidden-state mutations on a new sample of independently written ML repositories

**Status: DRAFT, NOT REGISTERED.** No E3 snapshot has been taken, no E3 repository has been screened and no third-party code has been run for E3. The registration point will be the git commit that adds the final version of this file as `e3/E3-PROTOCOL.md`. Any later change goes in `e3/DEVIATIONS.md`.

- Author: Hamjeth Misree (ORCID 0009-0008-2548-6920)
- Execution resources: personal Mac, personal GitHub account, Colima VM (see `e2/THREAT-MODEL.md`), under `INDEPENDENCE.md`
- Section 2 decisions approved by the author on 2026-11-14: target size, rule M8, fallback population P5, seed text, pooled secondary analysis.
- **Open until the pilots in Appendix A finish:** whether the thread-count family (§4) and the nondeterministic-baseline group (§5b) are included. Each section states what happens either way.

## 0. Relationship to E2

E2 was inconclusive on case count, not on direction: 10 positives against a minimum of 12, and 34 negatives against 35. On the cases it had, dynamic re-execution (D) caught 10 of 10 and static comparison (S1) 0 of 10. E3 tests the same hypothesis with the same decision rule on a **new, disjoint sample**. It changes only:

1. **The population** (§2): new, larger, and fixed in advance, with a registered fallback.
2. **The sample size**: 24 eligible repositories instead of 15.
3. **Harness rules** that E2 added as deviations (D1–D13, S13, S15). These are registered from the start (§3–§6).
4. **Up to two additions**, depending on the pilots: a thread-count mutation family (M-THREADS) and a descriptive analysis of repositories whose baselines are nondeterministic.

E2's results are already known, so they never enter E3's primary analysis.

## 1. Research question and hypothesis

Unchanged from E2.

**RQ.** On independently written ML code, does dynamic re-execution detect result-changing failures caused by *hidden execution state* (state not represented in the declared configuration) better than static configuration comparison, without an unacceptable increase in false alarms?

**H1 (primary).** Dynamic re-execution (D) has higher recall than declared-configuration static comparison (S1) on oracle-confirmed, stable, result-changing hidden-state mutations. Its false-positive rate on oracle-confirmed controls must not exceed S1's by an unacceptable margin (§9).

**Structural caveat, stated in advance.** Hidden-state mutations leave the declared configuration unchanged by construction, so S1 is expected to have recall ≈ 0. A supported H1 is therefore expected if genuine positives exist and D is stable. The informative quantities are:

- how often realistic hidden-state changes actually alter results in real code;
- D's false alarms caused by baseline nondeterminism;
- D's misses on intermittent effects;
- the trade-off against the stronger static comparator S2.

The report will say this plainly.

## 2. Population and selection (static, deterministic, text-only)

### 2.1 P4 (primary population)

`topic:scikit-learn` repositories with fewer than 10 stars. This is P1's exact query with the star filter inverted, so it covers the repositories that P1 left out only because of their star count. With `stars:>=10`, the same filters return 215 today, matching P1.

```
topic:scikit-learn  language:Python  stars:<10  fork:false  size:<=20000
license:mit license:apache-2.0 license:bsd-3-clause license:bsd-2-clause
created:2018-01-01..2026-06-30
```

Slices keep each query under GitHub's 1,000-result cap. Repeating `license:` combines licences with OR; this was checked.

| Slice | `created:` range | Count on 2026-11-13 (sizing only) |
|---|---|---|
| P4-a | 2018-01-01..2022-12-31 | 326 |
| P4-b | 2023-01-01..2023-12-31 | 107 |
| P4-c | 2024-01-01..2024-12-31 | 180 |
| P4-d | 2025-01-01..2025-06-30 | 207 |
| P4-e | 2025-07-01..2025-12-31 | 371 |
| P4-f | 2026-01-01..2026-03-31 | 388 |
| P4-g | 2026-04-01..2026-06-30 | 713 |
| **Total** | | **2,292** |

**If a slice reaches the cap at snapshot time,** halve its date range until every part is under 1,000, and record the split in `DEVIATIONS.md`.

### 2.2 P5 (fallback, used only if P4 is exhausted with fewer than 24 eligible)

Seven classical-ML topics, each queried separately (repeated `topic:` qualifiers combine with AND), then merged. No star filter.

```
topic:<T>  language:Python  fork:false  size:<=20000
license:mit license:apache-2.0 license:bsd-3-clause license:bsd-2-clause
created:2018-01-01..2026-06-30
-topic:scikit-learn -topic:sklearn -topic:mlops
```

| `<T>` | Count on 2026-11-13 |
|---|---|
| random-forest | 434 |
| xgboost | 665 |
| regression | 416 |
| logistic-regression | 291 |
| feature-engineering | 262 |
| supervised-learning | 169 |
| classification, created 2018-01-01..2022-12-31 | 621 |
| classification, created 2023-01-01..2026-06-30 | 595 |

**Not used, and why:**
- `machine-learning` and `data-science`: too large, and mostly not scikit-learn.
- `kaggle`: its data needs credentials.
- `mlflow` and `dvc`: E2's `mlops` population gave 0 eligible from 229.

### 2.3 Removal of already-screened repositories

Remove every repository whose full name is in `e2/REPOSITORY-MANIFEST.json` (1,111 entries). For P5, also remove every repository in P4. If the snapshot records repository IDs, match on those as well, so that renamed repositories are caught.

### 2.4 Order

For each population separately:
1. Merge the slices and remove duplicates.
2. Sort by full name.
3. Shuffle with Python `random.Random(seed)`, where `seed = int(sha256(seed_text), 16) mod 2^32`, as in `e2/screening/prescreen.py`.

| Population | Seed text | Seed |
|---|---|---|
| P4 | `ReproMut-E3\|10.5281/zenodo.24090849\|P4` | 701390840 |
| P5 | `ReproMut-E3\|10.5281/zenodo.24090849\|P5` | 3756357948 |

### 2.5 Snapshot

- Take the snapshot only after this protocol is committed (registered or as a dated draft) and before any E3 screening.
- Commit:
  - the script that runs the queries
  - each slice's exact query string and `total_count`
  - the raw JSON results
  - the UTC time
- E2 committed raw results but not the command; E3 commits both.

### 2.6 Screening rules

- **Automated rules X1–X12:** unchanged from E2 §2.
- **Manual review M1–M7:** unchanged from E2 §2, including amendment A1 (rule M2′ for repositories excluded only by X6).
- **E2's screening refinements:** the extended keyword lists, the removal of the `max_features` entry, and the skipping of unsafe archive members all apply from the start.

**New rule M8 (duplicates).** Exclude a repository if its entry-point script is byte-identical to that of a repository already accepted earlier in seeded order, or if it is a copy of one with only cosmetic changes (names, comments, formatting). Record the matched repository in the manifest. Duplicates would give correlated cases and overstate the evidence.

### 2.7 Sample and stopping rule

- **Sample:** the first **24** repositories in seeded order that pass X1–X12 and M1–M8.
- **Review order:** P4 first. P5 is reviewed only if P4 is exhausted with fewer than 24 eligible.
- **Stop:** review stops at 24 eligible, or when P4 and P5 are both exhausted.
- **Shortfall:** if P4 and P5 give fewer than 24, proceed with however many are eligible, as long as there are at least 6, and report the shortfall. If there are fewer than 6, run no confirmatory analysis and report the selection funnel. The population is never widened beyond P5.

Every reviewed repository and the reason for any exclusion go into `e3/REPOSITORY-MANIFEST.json`.

**Expected yield** (E2 rates; estimates, not guarantees):
- about 17 positives (minimum 12);
- about 58 negatives (minimum 35);
- about 300 manual reviews.

Risks in this estimate:
- 8 of E2's 10 positives came from one family (M-PATH).
- Nearly a third of P4 (P4-g) was created in 2026 Q2, and its eligibility rate is unknown.

## 3. Environment

- **Execution:** a new Colima VM `repromut-e3` with the same settings as E2 (aarch64 Linux, 4 vCPU, 6 GiB RAM). The disk target is 60 GiB, and the actual size goes in `e3/env/PREFLIGHT.md`. The preflight checks from E2 must pass before any run.
- **Image:** the official `python:<X.Y>-slim`, pinned by digest. X.Y is the lowest version that satisfies the repository's declared Python constraint (default 3.10), as in E2 S15.
- **Dependencies:** resolved with `uv pip compile --exclude-newer 2026-11-14` into a hash-locked lock file. If none are declared, imports map to `{numpy, scipy, scikit-learn, pandas, matplotlib, joblib}` plus other detected third-party imports, as in E2 D10. Documented extras that the registered invocation needs are installed (E2 D12).
- **Build-stage network:** check connectivity first, and retry locking and `docker build` up to 3 times. If the network stays down, stop the whole pipeline without classifying anything. Record an install failure only after 3 attempts with working network (E2 D11).
- **Every run** fixes `PYTHONHASHSEED=0`, `MPLBACKEND=Agg` and `HOME=/tmp` (E2 S13d).
- **Isolation:** as in `e2/THREAT-MODEL.md`. Network is disabled for every outcome-producing run.
- Image digests, lock files, the uv version, and the Colima and Docker versions go in `e3/env/` before any outcome run.

## 4. Cases

Every case runs the **unchanged declared invocation**. Only hidden state differs.

**Case plans** are generated per repository by `make_plans.py` and committed before that repository's first outcome run (E2 D10):
- one M-PATH case per working-directory-relative input file on the computation path;
- M-ENV, M-CACHE and M-DEP where a registered channel applies;
- M-THREADS if adopted;
- four controls.

README setup steps and A1 data are applied in every run, baseline included.

### Mutation families (intent only; the oracle decides the label)

**M-ENV, M-CACHE, M-DEP, M-PATH:** as defined in E2 §4, with E2 S13a for M-PATH. The sibling working directory mirrors the registered working-directory depth, and `python -m` of a module that only resolves from the working directory is "not applicable".

M-DEP uses only the default changes verified in `e2/env/default-changes.md`:
- KMeans `n_init` (1.4)
- LinearSVC `dual` (1.5)
- TSNE `learning_rate` and `init` (1.2)
- AdaBoostClassifier `algorithm` (1.6)
- PCA `svd_solver='auto'` policy (1.5)

A new candidate needs the same verification first.

Stale artifacts for M-CACHE and shadow files for M-PATH are produced beforehand by each repository's own code on 90%-row inputs, in the offline container.

**M-THREADS: thread-count environment. Included only if pilot T adopts it (Appendix A.1).**
- Applies to every repository, since all of them use numpy and scikit-learn (X12).
- **Baseline:** `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and `MKL_NUM_THREADS` unset, which is the repository's default.
- **Mutant:** all three set to `1`.
- **Check:** a diagnostic run in the same image, not an outcome run, records `threadpoolctl.threadpool_info()` for baseline and mutant. If the reported thread counts do not differ, the case is "not applicable" for that repository.
- This is hidden state: S1 cannot see it, and S2 sees it through the full environment map.

If pilot T does not adopt M-THREADS, this family is removed before registration and nothing else changes.

### Controls (expected not to change results; the oracle decides)

| Control | What changes |
|---|---|
| C-ENV | An irrelevant variable `REPROMUT_UNUSED_VAR=1` |
| C-CACHE | An unused file `.repromut_unused_cache.pkl` in the working copy |
| C-PATH | Identical repository content at a different absolute path |
| C-DEP | The nearest other patch release of the locked scikit-learn minor that has a binary wheel for the platform (E2 D10). If none exists, the case is excluded and counted (E2 D4) |

## 5. Oracle (independent of all auditors)

Unchanged from E2 §5:
- 5 baseline runs. The registered baseline is run #1.
- A repository is *baseline-stable* if all 5 baseline runs agree within tolerance, otherwise *baseline-nondeterministic*.
- 3 oracle runs per case.
- Labels: `stable_change`, `intermittent_change`, `unchanged`, `crash`, `timeout`, `install_failure`, `infra_failure` (retried up to 2 times), `indeterminate`.
- The earliest divergence is recorded.

**Registered from the start:**
- **E2 S13c:** if all 3 runs differ from the baseline but disagree with each other, the label is `indeterminate`.
- **E2 D8:** if every baseline run fails, the repository's cases are recorded as `indeterminate` (`not_run`) without being executed, and reported as a baseline failure.

Cases from baseline-nondeterministic repositories are excluded from the primary analysis, as in E2.

## 5b. Nondeterministic-baseline group (secondary, descriptive). Included only if pilot N adopts it (Appendix A.2)

**Purpose:** to show, without confirmatory claims, what re-running tells you when the unchanged code does not give the same answer twice. These cases **never count toward the minimum evidence or the primary analysis.**

- **Applies to:** repositories labelled baseline-nondeterministic under §5.
- **Runs:** 10 baseline runs and 10 runs per case.
- **Primary metric or metrics:** each repository's main reported score or scores, named in its case plan before any outcome run. A repository whose entry point runs several experiments may name one metric per experiment.
- **Test:** a two-sided permutation test on the difference in means of each metric, using 10,000 permutations with seed 20261114 and α = 0.01, with a Bonferroni correction across a repository's metrics.
- **Labels:**
  - `distribution_change` if any metric's p < α divided by the number of metrics;
  - `no_detected_change` otherwise;
  - the §5 failure labels apply unchanged.
- **Reported:**
  - the labels;
  - how often plain D, S1 and S2 flag these cases. D is expected to flag almost all of them, and that is the finding;
  - run-to-run spread per repository.
- **Budget:** 6 hours per repository instead of 3. Cases that do not fit in the budget are recorded as `not_run` and reported.

If pilot N does not adopt this group, E2's behaviour applies: such repositories are `indeterminate`, reported, and included only in sensitivity analysis 5.

## 6. Output adapters and tolerances

Unchanged from E2 §6: stdout numbers and declared output files, images excluded, float64 normalisation, `rtol = 1e-6`, `atol = 1e-9`, never loosened per repository.

**Registered from the start:**
- **Lines excluded from comparison:**
  - timing lines matching E1's `TIMING_RE`;
  - wall-clock stamps `HH:MM:SS` (E2 D1);
  - registry or run identifiers such as `version` and `run id` (E2 D5);
  - calendar date stamps `YYYY-MM-DD` and `YYYYMMDD-HHMMSS` (E2 D9).
- **Non-text outputs:** parquet, and pickles if declared, are converted to numbers in a second offline run of the same image. The host never parses or unpickles them (E2 D2).
- **Directory artifacts:** allowed, for example an MLflow `mlruns` tree. Every file in a run copy is made writable by the container user (E2 D3).
- **Output paths:** declared output files are read relative to the run's working directory, as bytes only. Symlinks and paths outside the work copy are refused (E2 S13b, S13e).
- **Stored outputs:** every oracle and dynamic run's normalised outputs are stored in its case record (E2 D6).
- Any adapter change after the first outcome run is a deviation.

## 7. Auditors (no access to oracle labels)

Unchanged from E2 §7:

| Auditor | Definition | Role |
|---|---|---|
| **S1** | Declared-configuration static comparison | Primary comparator |
| **S2** | S1 plus resolved packages, the full environment map, absolute working directory and untracked files | Secondary comparator |
| **D** | 3 runs in fresh containers, 8-decimal fingerprints, *k* = 2; crash or timeout flags as `execution_failure`, kept separate | Evaluated method |
| **C1** = S1 ∨ D, **C2** = S2 ∨ D | Combined auditors | Combined |

D's runs are separate from the oracle's runs.

## 8. Outcomes

**Primary analysis set.** E3 repositories only. It contains cases from baseline-stable repositories labelled `stable_change` (positives) or designed controls labelled `unchanged` (negatives).

**Primary outcomes:**
- recall of D and S1;
- the paired recall difference D − S1, with a 95% repository-cluster bootstrap CI (10,000 resamples, seed **20261114**);
- the false-positive rates of D and S1, and their difference, with the same bootstrap.

**Secondary outcomes (descriptive):** everything in E2 §8, plus:
- results by population (P4 vs P5) and by creation-date slice;
- M-THREADS results, if adopted;
- the §5b group, if adopted;
- **pooled E2 + E3:** the same quantities computed on both studies together, labelled secondary and descriptive, with no verdict attached. E2's outcomes were known when E3 was designed.

## 9. Decision rules (fixed before any run)

Unchanged from E2 §9, including S14:
- **Minimum evidence:** at least **12** `stable_change` positives from at least **4** repositories, and at least **35** negatives. Otherwise **inconclusive**.
- **Unacceptable false-alarm increase:** the point estimate of FPR(D) − FPR(S1) is above 5 percentage points, or the upper 95% bound of that difference is above 10 percentage points. If there are zero false positives in both arms, the Wilson 95% upper bound of FPR(D) is used instead.
- **Verdicts:**
  - **Supported:** minimum evidence is met, the lower 95% bound of the recall difference D − S1 is above 0, and the false-alarm increase is acceptable.
  - **Not supported:** minimum evidence is met, but the recall interval includes 0 or the false-alarm increase is unacceptable.
  - **Inconclusive:** otherwise.
- **Multiple comparisons:** one confirmatory test. Secondary p-values are Holm-adjusted and labelled exploratory.

## 10. Missing data and exclusions

Unchanged from E2 §10:
- **Install failures:** excluded and reported. The next repository in seeded order replaces it, but only if the failure happens before that repository's first outcome run.
- **Infrastructure failures:** retried up to 2 times, then excluded and counted.
- **Crashes and timeouts:** never counted as detections in the primary analysis.

**Pilot repositories:** the first 2 eligible repositories in seeded order. They are reported separately and re-run under the frozen harness if any adapter changes, as in E2 D13.

## 11. Sensitivity analyses (pre-declared)

E2's six analyses, unchanged:
1. Tolerance: `rtol` set to 1e-4 and 1e-8.
2. Repeats for D: *k* = 1 and *k* = 3.
3. Counting `intermittent_change` as positive; counting crashes and timeouts as positive.
4. Including equivalent mutations as negatives.
5. Including baseline-nondeterministic repositories, using the oracle's per-run comparison.
6. Repository-level macro-average instead of pooled.

Added for E3:

7. Excluding P5 repositories.
8. Excluding M-THREADS cases, if adopted.
9. Excluding the 2 pilot repositories.
10. Excluding repositories created in 2026 Q2 (slice P4-g).

## 12. Limits

- **Per run:** 10 minutes wall clock, 2 CPU, 3 GiB RAM, 512 MiB tmpfs, no network.
- **Per repository:** 3 hours, or 6 hours for the §5b group.
- **Lanes:** at most 2 concurrent containers.
- **Host:** keep it awake during batches (`caffeinate -i`). A run lost to host sleep is an `infra_failure` and is retried.

## 13. Integrity statements

- All mutations are controlled interventions, not naturally occurring defects.
- Third-party code is not modified, redistributed or vendored.
- No maintainers are contacted, and nothing is published without explicit approval.
- Every working session is logged in `INDEPENDENCE.md`.
- Any change after registration goes in `e3/DEVIATIONS.md`.

---

## Appendix A. Pilots that decide §4 (M-THREADS) and §5b

Both pilots use **E2 repositories only**. Those repositories cannot be in E3's sample, because §2.3 removes everything E2 screened.

**Commit this draft before running either pilot**, so that the pilot plans and adoption rules carry a timestamp that precedes their results. Pilot results go in `e3/PILOT-REPORT.md`, whatever they show.

**Why the adoption rules work this way:** they test whether a method works (the setting takes effect, runs complete, labels are decidable and repeatable), not whether it produces positives. Whatever a pilot shows, its result is reported.

### A.1 Pilot T (thread-count family)

- **Repositories:** the first 3 baseline-stable, measurable E2 repositories in E2's review order (P1, P2, P3, each in seeded order). Applied to E2's records, this gives `fmind/mlops-python-package`, `ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques` and `youngcoder45/Student-Performance-Predictor`.
- **Procedure:**
  - E2 harness and images;
  - baseline with the thread variables unset;
  - mutant with all three set to `1`;
  - a `threadpoolctl` diagnostic for both;
  - 3 oracle runs, labelled as in §5.
- **Adopt M-THREADS if both:**
  - in at least 2 of the 3 repositories, the diagnostic shows different thread counts between baseline and mutant;
  - every pilot case receives a decidable label (`stable_change`, `intermittent_change` or `unchanged`) with no infrastructure failures left after retries.

### A.2 Pilot N (nondeterministic-baseline group)

- **Repository:** `sagnik1511/Tabular-AutoML`, the only baseline-nondeterministic repository in E2.
- **Metrics,** registered in `e3/pilots/pilot_n_config.json` before any pilot run:
  - the final best validation accuracy of the classification test;
  - the final best validation MSE of the regression test;
  - both read from the lines the repository prints.
- **Procedure:**
  - run its constructible E2 cases under §5b: 10 baseline runs and 10 runs per case;
  - then repeat the whole procedure independently;
  - in the pilot, D is computed from the first 3 case runs against baseline run 1, not from separate runs.
- **Adopt §5b if both:**
  - every run completes within the per-run limits;
  - the two repeats give the same label for every case.

## Appendix B. Order of operations

1. **Author review of this draft.** Commit it as `e3/E3-PROTOCOL-DRAFT.md`, which timestamps the plan.
2. **VM preflight.** Free host disk, create `repromut-e3`, then run the E2 preflight checks.
3. **Pilots T and N.** Write `e3/PILOT-REPORT.md`, then keep or remove §4's M-THREADS and §5b.
4. **Snapshot and static screening** (§2.5–§2.6). This only reads code, so it can happen before registration, as in E2.
5. **Registration.** Commit the final `e3/E3-PROTOCOL.md` and push it for a public timestamp.
6. **Manual review in seeded order** until the §2.7 stop.
7. **Case plans.** Commit each repository's case plan before its first outcome run.
8. **Execution, analysis, report.** The report says what the pilots showed and how §4 and §5b were decided.
