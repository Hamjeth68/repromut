# Changelog

## Unreleased: preprint draft v0.2 (2026-11-08)

- **External validation E1:** a pre-registered study (`PROTOCOL-E1-external.md`) on 30 independently written scikit-learn 1.7.2 example scripts.
  - New harness: `src/repromut/external.py`.
  - Analysis script: `paper/analyze_e1.py`.
  - Results: `results/e1-sklearn-examples/`, with deviations documented.
- **Paper:** new Section 7 (E1), plus updates to the abstract, limitations and planned work (stage E2).
- **Tests:** 666 passing (8 new tests for the external harness).

## 0.1.0.dev0 — 2026-11-08 (unreleased)

- Package format and hermetic runner with 5 fingerprinted stages.
- 28 synthetic baseline experiments: binary, multiclass, regression and clustering.
- 12 result-changing mutations and 7 semantics-preserving controls.
- 5 audit methods and an independent tolerance oracle.
- 658 tests, including oracle confirmation of all 452 cases.
- Exploratory development benchmark in `results/dev-2026-11-08/`.
