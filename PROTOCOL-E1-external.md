# Protocol E1: external validation on independently written ML code

**Status: pre-registered. This file was committed and pushed to GitHub before any E1 run was started.** The commit timestamp is the registration record. Anything changed after that commit is reported as a deviation.

## Question

Do the conclusions of the synthetic benchmark hold on real, independently written ML code?

1. Seed-only and static-manifest checks have fixed, family-specific blind spots.
2. Static checks raise false alarms on harmless changes.
3. Re-execution (dynamic) is needed to catch the remaining failures.

The study also measures three things the synthetic suite could not:

- how often real scripts are **not reproducible run-to-run** to begin with;
- how often a plausible "breaking" change is in fact **equivalent** (it doesn't change the result);
- how often harmless-looking environment changes **do** change results.

## Population and independence

- **Population:** every `*.py` file under `examples/` in scikit-learn at tag **1.7.2**, commit `25dee604bae18205b01548348388baf7a1cdfe0e`. That is 279 files.
- **Independence:** these scripts were written and reviewed by scikit-learn contributors, not by the ReproMut author. None was chosen, edited or inspected for this study.
- **Why this population:** it is a large, public, versioned corpus of real ML code. Because it comes from the same project as an installed dependency, running it in an isolated sandbox is low-risk.
- **This is not research-paper code.** That is stage E2 (below), which needs a separate protocol and isolated CI.

## Sampling

- **Order:** a random permutation of the sorted file list, made with `numpy.random.default_rng(seed)`.
- **Seed:** `seed = int(sha256("10.5281/zenodo.24048006").hexdigest(), 16) mod 2^32`. This is derived from the preprint DOI, which was fixed before this protocol existed.
- **Screening:** scripts are screened in that order. The sample is the **first 30 eligible scripts** in the order, regardless of the order in which runs happen to finish.

## Eligibility (checked automatically, before any mutation)

| Code | Rule |
|---|---|
| E1 | No network or data-download calls. This is a static check: `fetch_*`, `urlopen`, `requests.`, `pooch` and similar. |
| E2 | Baseline exits with status 0 within **30 s**, using `MPLBACKEND=Agg` in the frozen environment (Python 3.10.12, scikit-learn 1.7.2, numpy 2.2.6, scipy 1.15.3). |
| E3 | The baseline prints at least one number to stdout. This is the script's "reported result". Lines matching the pre-registered timing pattern `TIMING_RE` in `src/repromut/external.py` are excluded from the result. |
| E4 | Two baseline runs agree within tolerance. A failure here is **counted and reported** as natural non-reproducibility, and the script is not mutated. |

## Operators (intent declared; effect decided by the oracle)

**Positive intent (expected to change results):**

- `seed_removed`
- `seed_changed`
- `split_changed`: `train_test_split` `test_size`
- `cv_changed`: `cv` / `n_splits`
- `iterations_reduced`: `max_iter` / `n_estimators`

**Control intent (expected not to change results):**

- `comment_added`
- `reformatted`: AST round trip
- `threads_1`: `OMP_NUM_THREADS=1`
- `workdir_moved`

An operator applies only when it finds a matching site in the script.

## Ground truth

This differs from the synthetic study. **Truth = the execution oracle**:

- 2 runs of the mutant;
- full-precision comparison against both baseline runs and against each other;
- `rtol = 1e-6`, `atol = 1e-9`.

A mutant that crashes or times out counts as result-changing.

## Auditors

| Auditor | What it does |
|---|---|
| Seed-only | Compares the literal seeds against the recorded ones. |
| Static manifest | Compares a hash of the AST, so it ignores comments and formatting. It cannot see environment changes. |
| Dynamic | 2 runs; SHA-256 of the printed numbers rounded to 8 decimals, compared against the recorded fingerprint. |

## Pre-specified analysis

- **Primary:** recall and false-positive rate of each auditor against the oracle truth, with Wilson 95% intervals.
- **Paired comparison:** dynamic vs static and dynamic vs seed-only, using an exact McNemar test.
- **Secondary, descriptive:**
  - the E4 natural non-reproducibility rate;
  - per-operator equivalent-mutant rate, i.e. positive intent but no change;
  - the control-intent change rate;
  - disagreements between dynamic fingerprints and the oracle;
  - runtime cost.

**Expected direction:** static recall < dynamic recall, and static FPR > 0 (if any equivalent positive-intent mutants exist).

**Known limitation stated in advance:** the dynamic auditor and the oracle both re-execute the script, so high dynamic recall is partly by construction.

## Stage E2 (not part of this run)

Independently selected **research-paper** repositories, e.g. a seeded random sample of ML Reproducibility Challenge reports with public code.

That stage executes untrusted third-party code. It will only be run in an isolated, ephemeral CI runner with no secrets, after the sampled list has been reviewed by a human. It needs its own protocol, committed before it runs.
