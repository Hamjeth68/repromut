# E2 protocol: hidden-state mutations on independently written ML repositories

**Status: REGISTERED (approved by the author on 2026-11-09, including amendments A1, A2, S14 and S15).** The registration point is the local git commit that adds this file. Any later change is logged in `DEVIATIONS.md`. No third-party code has been executed. Repository screening (static, text-only) and drafting of this protocol both happened before any execution, so no outcome data existed at either stage.

- Registration commit: the commit returned by `git log --diff-filter=A --format=%H -- e2/E2-PROTOCOL.md`. A commit cannot contain its own hash, so the value is also written into `DEVIATIONS.md` by the next commit.
- Author: Hamjeth Misree (ORCID 0009-0008-2548-6920)
- Execution resources: personal Mac, personal GitHub account, Colima VM (see `THREAT-MODEL.md`)

## 1. Research question and hypothesis

**RQ.** On independently written ML code, does dynamic re-execution detect result-changing failures caused by *hidden execution state* (state not represented in the declared configuration) better than static configuration comparison, without an unacceptable increase in false alarms?

**H1 (primary).** Dynamic re-execution (D) has higher recall than declared-configuration static comparison (S1) on oracle-confirmed, stable, result-changing hidden-state mutations. Its false-positive rate on oracle-confirmed controls must not exceed S1's by an unacceptable margin (§9).

**Structural caveat, stated in advance.** Hidden-state mutations leave the declared configuration unchanged by construction, so S1 is expected to have recall ≈ 0 on them. A positive H1 result is therefore *expected* if genuine positives exist and D is stable. The empirically informative quantities are:

1. **Prevalence.** How often realistic hidden-state changes actually alter results in real code (cf. E1, where none did).
2. **False alarms.** D's false alarms caused by baseline nondeterminism.
3. **Missed changes.** D's misses on intermittent effects.
4. **Trade-off.** The trade-off against a stronger static comparator, S2, that also inspects the environment (secondary analysis).

The report will say this plainly. A supported H1 will not be described as surprising or as general superiority.

## 2. Population and selection (static, deterministic, text-only)

**P1 (search).** GitHub search snapshot taken 2026-11-09T01:32Z (UTC) with:

```
topic:scikit-learn  language:Python  license ∈ {mit, bsd-3-clause, bsd-2-clause, apache-2.0}
stars ≥ 10   size ≤ 20,000 KB   created 2018-01-01..2026-06-30   forks excluded
```

This returned 215 repositories (`screening/raw_*.json`).

**Order.**
- Sort the repositories by full name.
- Shuffle them with Python `random.Random(seed)`, where `seed = int(sha256("ReproMut-E2|10.5281/zenodo.24048206"), 16) mod 2^32`.

**Automated static rules (X1–X12).** Every repository is downloaded at its default-branch commit SHA and read as text. A repository is excluded if any rule fails:

| Rule | Exclude if |
|---|---|
| X1 | Licence is not MIT/BSD-2/BSD-3/Apache-2.0, or there is no licence file |
| X3 | High-stakes domain keywords appear in the name, description or README |
| X4 | The repository is owned by your accounts |
| X5 | There is no Python script entry point |
| X6 | The code downloads data over the network |
| X8 | It depends on torch/tensorflow/jax or similar (CPU and runtime feasibility) |
| X9 | No hidden-state channel is detected |
| X10 | It uses a medical dataset |
| X11 | It contains a hard-coded credential pattern |
| X12 | It does not use scikit-learn |

The script is `screening/prescreen.py`, and every screened repository and its reasons are recorded in `screening/screening.jsonl`.

**Amendment A1 (approved by the author on 2026-11-09, before registration and before any execution).** X6 no longer excludes a repository by itself. Repositories that are excluded *only* by X6 enter manual review under rule M2′, which replaces M2 for them:

- **M2′ (inputs fetchable at build time).** Every input the run needs can be obtained during the **networked build stage** from a public, stable source:
  - a direct URL, an OpenML/UCI/scikit-learn fetcher, or NLTK/spaCy data packages;
  - each file is pinned by SHA-256;
  - each dataset's licence is recorded in `LICENSE-REVIEW.md` and permits local research use.

  The fetched files are placed where the code expects them (for example the scikit-learn or NLTK data home), so the **experiment runs need no network**. A repository whose inputs need credentials, an API key, a paid service, scraping of live web pages, or data whose licence forbids local research use is excluded.

**Order of review under A1.** Repositories excluded only by X6 are reviewed in the same seeded order (P1 first, then P2) after the already-eligible ones, and review stops when 15 are eligible.

**Amendment A2 (approved by the author on 2026-11-09, before registration and before any execution).** P1 and P2 gave only 4 eligible repositories under A1 (DEVIATIONS S9), so a third population is added.

- **P3 definition.** GitHub repositories with `topic:sklearn`, `language:Python`, and licence MIT, Apache-2.0, BSD-3-Clause or BSD-2-Clause. Every query returns fewer than 1,000 results, so no slicing is needed. Repositories already in P1 or P2 are removed.
- **Order.** Seeded shuffle with seed text `ReproMut-E2|10.5281/zenodo.24048206|P3`.
- **Rules.** Identical to P1/P2: the same X1–X12 automated rules, then M1–M7 with A1's M2′ for X6-only repositories.
- **Review order.** Manual review covers static passes and X6-only repositories in P3 seeded order. It stops when the total across P1–P3 reaches 15 eligible repositories, or when P3 is exhausted.
- **If still short.** If the total is still below 6, the study does not run confirmatory analyses. It reports the selection funnel and, with the author's approval, may run an exploratory analysis only.

**Manual review rules (M1–M7).** These are applied to static passes, in sampled order, by reading the code only:

| Rule | Requirement |
|---|---|
| M1 | The entry point is a batch experiment or training/evaluation script, not a server, GUI, bot, notebook-only or interactive program. |
| M2 | All inputs are available offline: committed to the repository, generated, or a non-medical scikit-learn bundled dataset. |
| M3 | Statically plausible to run on CPU within 10 minutes. |
| M4 | Produces numerical results: printed metrics or written arrays/tables/models. |
| M5 | Not high-stakes or sensitive, judged beyond keywords: no inference about people's health, psychology or identity, no security/malware detection, no trading/gambling automation, no biometrics. |
| M6 | At least one hidden-state channel is *real*: the code actually reads the environment variable, cache artifact or relative path on the computation path, or uses an estimator affected by a documented scikit-learn default change. |
| M7 | No licence restriction on local execution or on storing derived outputs. |

**Sample.** The first **15** repositories in sampled order that pass both X and M.

**Extension to P2.** P1 yielded only 3 eligible repositories, so the sample is extended to P2:
- **Query:** the same filters with `topic:mlops`, snapshot 2026-11-09T01:53Z (UTC). This gave 242 repositories, 13 of which were already screened in P1.
- **Seed:** the same rule with the suffix `|P2`.
- **Why not `topic:machine-learning`:** that query returns about 4,000 repositories, which exceeds the GitHub search cap of 1,000 per query and would need non-deterministic splitting.
- **Why `topic:mlops`:** it was chosen *before any outcome data existed*, because MLOps pipelines are where hidden execution state (caches, registries, environment configuration) plausibly lives.
- **Generalisation:** this choice limits generalisation, and the report will state that.

**Further extension.** If P1 and P2 together yield fewer than 10, the study proceeds with however many are eligible (minimum 6). It reports the shortfall rather than widening the population again.

Every reviewed repository and the reason for any exclusion goes into `REPOSITORY-MANIFEST.json`.

**Screening refinements made during screening.** These were made before any execution and do not touch outcome data:
- extended the high-stakes and network-download keyword lists;
- removed the RandomForest/ExtraTrees `max_features` entry, because its 1.1 change was a rename with identical behaviour (`'auto'` → `1.0`/`'sqrt'`), not a behaviour change;
- extraction now skips unsafe archive members instead of failing the whole repository.

All of these are listed in `DEVIATIONS.md` under "pre-registration screening notes".

## 3. Environment

- Execution: Colima VM `repromut-e2` (aarch64 Linux, 4 vCPU, 6 GiB RAM), Docker image based on the official `python:<X.Y>-slim`, pinned by digest, where X.Y is the lowest version that satisfies the repository's declared Python constraint (default 3.10) (S15).
- Dependencies: each repository's requirements are resolved with `uv pip compile --exclude-newer 2026-11-01` into a hash-locked lock file. If no requirements are declared, its imports map to `{numpy, scipy, scikit-learn, pandas, matplotlib, joblib}` under the same cutoff.
- Exact image digests, lock files, the uv version and the Colima/Docker versions are recorded in `e2/env/` before any outcome run.
- Isolation: as in `THREAT-MODEL.md`. Network is disabled for every outcome-producing run.

## 4. Cases

Every case runs the **unchanged declared invocation**: same entry point, same arguments, same tracked files. Only hidden state differs.

### Mutation families (intent only; the oracle decides the label)

**M-ENV: environment variable.**
- Applies when: the code reads environment variable *V* (found statically) on a path that affects computation.
- Change: baseline = the repository's default (unset unless the README says otherwise). The mutant sets *V* to a documented alternative value, or, if none is documented, to a type-consistent alternative.

**M-CACHE: stale cache artifact.**
- Applies when: the code reuses an on-disk artifact if it exists (for example `joblib.Memory`, or an `exists()` check followed by a load).
- Change: the mutant pre-places a *stale* artifact at that exact path. It is the artifact the repository's own code produces when run with a deterministic input perturbation that is registered per repository (for example, the first 90% of input rows). A truncated-file variant is run as a secondary case; it is expected to crash and is classified as a crash.

**M-DEP: dependency default change.**
- Applies when: the code calls an estimator whose default changed between two scikit-learn versions, and does not set that parameter explicitly.
- Change: the baseline lock is used, and the mutant changes **only** scikit-learn to the version on the other side of the documented change. All other packages stay at the same versions; if that is impossible, the case is excluded.
- Candidate documented changes. Each must be verified against the official scikit-learn release notes before any run; the link and quote go into `e2/env/default-changes.md`, and a candidate that cannot be verified is dropped:
  - KMeans/MiniBatchKMeans `n_init` (1.3 → 1.4)
  - TSNE `init`/`learning_rate` (1.1 → 1.2)
  - AdaBoostClassifier `algorithm` (1.5 → 1.6)
  - LinearSVC `dual` (1.4 → 1.5)
  - PCA `svd_solver="auto"` policy and component sign convention (1.4 → 1.5); this one is already verified in the 1.5 release notes.

**M-PATH: implicit working-directory resolution.**
- Applies when: the code opens a relative path resolved against the working directory (not `__file__`).
- Change: the declared entry point is invoked by absolute path from a sibling working directory that contains a **shadow** file at the same relative path. The shadow file's content gets the same deterministic perturbation as M-CACHE. Invocations that merely fail with "file not found" are not created on purpose.

### Controls (expected not to change results; the oracle decides)

| Control | What changes |
|---|---|
| C-ENV | An irrelevant variable `REPROMUT_UNUSED_VAR=1` |
| C-CACHE | An unused file `.repromut_unused_cache.pkl` in the working copy |
| C-PATH | Identical repository content at a different absolute path |
| C-DEP | A scikit-learn patch-level change on the same side of the boundary, with no documented default change (for example 1.4.1 → 1.4.2) |

C-DEP and C-CACHE apply to every eligible repository; C-ENV and C-PATH apply to every repository.

## 5. Oracle (independent of all auditors)

**Baseline.** 5 runs of the unchanged repository.
- The registered baseline is run #1.
- A repository is *baseline-stable* if all 5 runs agree within tolerance. Otherwise it is *baseline-nondeterministic*: its cases are labelled `indeterminate` and excluded from the primary analysis, and reported.

**Each case.** 3 oracle runs. Each run's normalised outputs are compared with every baseline run and with each other.

**Labels:**

| Label | Rule |
|---|---|
| `stable_change` | All 3 runs succeed, all differ from the baseline beyond tolerance, and all agree with each other |
| `intermittent_change` | Some runs differ from the baseline and some do not |
| `unchanged` | All 3 runs succeed and match the baseline |
| `crash` | Non-zero exit from the experiment |
| `timeout` | Run exceeded the time limit |
| `install_failure` | Environment could not be built |
| `infra_failure` | Docker/VM/runner error, retried up to 2 times |
| `indeterminate` | None of the above can be decided |

**Earliest divergence.** Recorded as the first output artifact, in the adapter's declared order, that differs.

## 6. Output adapters and tolerances

These are registered per repository in the manifest **before** outcome runs.

- **What counts as a result:**
  - numbers printed to stdout, with timing lines excluded by the E1 `TIMING_RE`;
  - the declared output files written by the run (CSV, JSON, NPY, NPZ, TXT, and pickled scikit-learn models via their learned array attributes);
  - images are excluded.
- **Normalisation:** float64 arrays, NaN and ±0 canonicalised.
- **Tolerance:** `rtol = 1e-6`, `atol = 1e-9`. This is the same for all repositories and is never loosened per repository except in pre-declared sensitivity analyses.
- **Pilot adjustments:** adapter changes after the pilot are logged in `DEVIATIONS.md`, and the pilot repositories are reported separately.

## 7. Auditors (no access to oracle labels)

| Auditor | Definition | Role |
|---|---|---|
| **S1**: declared-configuration static comparison | Hashes of tracked config files (`*.yaml/yml/json/toml/ini/cfg/conf`), requirements/setup/pyproject/environment files, the entry point and its arguments, and the AST hashes of tracked `.py` files. Compared with the registered baseline. | Primary comparator |
| **S2**: extended-manifest static comparison | S1, plus the resolved package versions (lock file and `pip freeze`), the full environment-variable map, the absolute working-directory path, and content hashes of all untracked files in the working copy at launch. | Secondary comparator |
| **D**: dynamic re-execution | 3 runs in fresh containers. SHA-256 of each normalised output set (8-decimal rounding, as in E1). Flags if any of the first *k*=2 runs differs from the registered baseline fingerprint or the runs differ from each other. A crash or timeout flags with reason `execution_failure`, kept separate from numeric-change flags. Process success alone is never treated as reproduced. | Evaluated method |
| **C1** = S1 ∨ D, **C2** = S2 ∨ D | Combined auditors; the originating auditor and reason are kept. | Combined |

D's runs are separate from the oracle's runs.

## 8. Outcomes

**Primary analysis set.** Cases from baseline-stable repositories labelled `stable_change` (positives) or designed controls labelled `unchanged` (negatives).

**Primary outcomes:**
- recall of D and S1 on positives;
- the **paired recall difference D − S1**, with a 95% repository-cluster bootstrap CI (10,000 resamples of repositories with replacement, seed 20261109);
- the false-positive rate of D and S1 on negatives, and their difference with the same bootstrap.

**Secondary outcomes (descriptive, no confirmatory claims):**
- D vs S2 recall and FPR;
- C1 and C2;
- results by mutation family and by repository;
- macro-averages across repositories;
- prevalence of `stable_change` per family;
- the baseline nondeterminism rate;
- crash, timeout and install-failure rates;
- equivalent-mutation rate (positive-intent `unchanged`);
- runtime and resource overhead per auditor;
- per-case exact McNemar test D vs S1.

## 9. Decision rules (fixed before any run)

**Minimum evidence.** At least **12** `stable_change` positives from at least **4** different repositories, and at least **35** negatives (S14: the smallest n for which the zero-false-positive Wilson rule can be met). Otherwise H1 is **inconclusive**.

**Unacceptable increase in false alarms.** Either of:
- the point estimate of FPR(D) − FPR(S1) is above **5 percentage points**;
- the upper bound of its 95% cluster-bootstrap CI is above **10 percentage points**.

If there are zero false positives in both arms, the Wilson 95% upper bound of FPR(D) is used instead.

**Verdicts:**

| Verdict | Condition |
|---|---|
| **Supported** | Minimum evidence is met, the lower 95% bound of the recall difference D − S1 is above 0, and the false-alarm increase is acceptable |
| **Not supported** | Minimum evidence is met, but the recall CI includes 0 or the false-alarm increase is unacceptable |
| **Inconclusive** | Otherwise |

**Multiple comparisons.** There is one confirmatory test. Secondary results are descriptive. Any secondary p-values are Holm-adjusted and labelled exploratory.

## 10. Missing data and exclusions

- **Install failures:** excluded at the repository level and reported. The next repository in sampled order replaces it, but only if this happens before its first outcome run.
- **Infrastructure failures:** retried up to 2 times, then excluded and counted.
- **Crashes and timeouts:** never counted as detections in the primary analysis.
- **Pilot repositories (1–2):** the first eligible repositories in sampled order. Their results are reported separately, and they are re-run under the frozen harness if any adapter changed.

## 11. Sensitivity analyses (pre-declared)

1. **Tolerance:** `rtol` set to 1e-4 and 1e-8.
2. **Repeats for D:** *k* = 1 and *k* = 3.
3. **Counting:** counting `intermittent_change` as positive; counting crashes and timeouts as positive.
4. **Negatives:** including equivalent mutations as negatives.
5. **Baseline-nondeterministic repositories:** included, using the oracle's per-run comparison.
6. **Weighting:** repository-level macro-average instead of pooled.

## 12. Limits

- Per run: 10 minutes wall clock, 2 CPU, 3 GiB RAM, 512 MiB tmpfs, no network.
- Per repository: 3 hours total.
- Lanes: at most 2 concurrent containers, with fixed CPU quotas, to avoid the contention artefacts seen in E1.

## 13. Integrity statements

- All mutations are **controlled interventions**, not naturally occurring defects.
- Third-party code is not modified, redistributed or vendored. Only commit SHAs, licence metadata and our own adapters are stored.
- No maintainers are contacted, and nothing is published, released or uploaded without explicit approval.
- Any change after registration is written to `DEVIATIONS.md`.
