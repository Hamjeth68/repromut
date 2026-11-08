# Prospective confirmatory protocol (DRAFT — not preregistered)

The v0.1 development results were produced before this protocol received a public timestamp. This file must not be represented as a preregistration of those results. It may be adapted and publicly registered only for a future, separately frozen confirmatory study before that study is run.

Freeze this file with a signed git tag and a public timestamp (for example a Zenodo or OSF deposit) **before** running the confirmatory benchmark. Any analysis that changes after freezing must be labelled exploratory.

## Hypothesis

Run on the frozen v0.1.0 suite (catalog, mutations, tolerances and seeds exactly as tagged). The dynamic auditor (2 repeats, 8-decimal stage fingerprints) is predicted to:

1. Detect at least 90% of declared result-changing mutations.
2. Exceed the seed-only checker's recall by at least 30 percentage points (paired cases).
3. Keep a false-positive rate below 5% on declared semantics-preserving controls.

## Pre-specified analysis

- **Primary:** recall, false-positive rate, precision and F1 with Wilson 95% intervals.
- **Paired:** dynamic vs seed-only on positives, with a percentile bootstrap 95% CI (2,000 resamples, seed 0) and an exact McNemar test.
- **Secondary (exploratory):** per-family recall, localisation accuracy, runtime overhead, and hash-vs-tolerance disagreements.
- **Exclusions:** any case where the oracle disagrees with the declared label. Report the count; do not silently drop cases.

## Known threat to validity, stated in advance

The dynamic auditor and the oracle both execute the package. High dynamic recall on deterministic mutations is therefore expected by construction. The confirmatory contribution is the measured gap between static and dynamic methods and their cost, not the dynamic recall itself.

## Changes before freezing (development history)

- The development oracle run found 25 mismatches between declared and observed labels. They were resolved by narrowing applicability, which is documented in `docs/mutation-taxonomy.md`:
  - `row_order_changed` is now regression-only.
  - `dtype_float32` now excludes tree ensembles.
  - `solver_tolerance_loosened` now excludes GMM.
  - The clustering objective was added to model-stage artifacts.
