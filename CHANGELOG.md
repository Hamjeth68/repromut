# Changelog

## Unreleased: preprint draft v0.2 (2026-11-08)

- **External validation E1:** a pre-registered study (`PROTOCOL-E1-external.md`) on 30 independently written scikit-learn 1.7.2 example scripts.
  - New harness: `src/repromut/external.py`.
  - Analysis script: `paper/analyze_e1.py`.
  - Results: `results/e1-sklearn-examples/`, with deviations documented.
- **Paper:** new Section 7 (E1), plus updates to the abstract, limitations and planned work (stage E2).
- **Tests:** 666 passing (8 new tests for the external harness).
- **Cross-platform replication:** the full synthetic benchmark gave identical case-level outcomes for all 452 cases on macOS arm64 (Python 3.12.13, scikit-learn 1.9.1) and on Linux aarch64. The evidence is in `results/crossplatform-macos-2026-11-09/`, and the paper's limitations section is updated to match.

## 0.1.1 — 2026-11-08

- Corrected the public-status and protocol wording across the documentation and manuscript.
- Defined cross-platform repeatability at a strict `1e-12` numerical tolerance instead of requiring bitwise-identical floating-point results.
- Added the public Zenodo DOI to the manuscript availability statement.
- Rebuilt and visually checked the 10-page exploratory preprint.

## 0.1.0.dev0 — 2026-11-08

- Package format and hermetic runner with 5 fingerprinted stages.
- 28 synthetic baseline experiments: binary, multiclass, regression and clustering.
- 12 result-changing mutations and 7 semantics-preserving controls.
- 5 audit methods and an independent tolerance oracle.
- 658 tests, including oracle confirmation of all 452 cases.
- Exploratory development benchmark in `results/dev-2026-11-08/`.
