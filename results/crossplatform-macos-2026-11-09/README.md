# Cross-platform replication of the synthetic benchmark

The full benchmark (`repromut bench --out results/full`) was re-run by the author on a second machine on 2026-11-09. Its case-level output (`cases.jsonl`) was then compared with the original development run, `results/dev-2026-11-08/cases.jsonl`.

| | Original run | Replication |
|---|---|---|
| Platform | Linux aarch64 (glibc 2.35) | macOS 27.2, Apple Silicon (arm64) |
| Python | 3.10.12 | 3.12.13 |
| NumPy | 2.2.6 | 2.5.4 |
| SciPy | 1.15.3 | 1.18.1 |
| scikit-learn | 1.7.2 | 1.9.1 |

**Result:** all 452 cases match on everything except runtime fields. That covers the mutation, the declared label, the oracle outcome, the first divergent stage, and every auditor's verdict, stage and reason. Oracle agreement is 452/452 in both runs, and every count in `summary.md` is identical.

**Note on the version field:** `summary.json` reports `repromut 0.1.0.dev0`. That value comes from `repromut.__version__`, which had not been bumped when the package metadata moved to 0.1.1; the code run was commit `e51de2f`.

**How to check:** run `python results/crossplatform-macos-2026-11-09/compare.py`. It loads both `cases.jsonl` files, drops the `elapsed_s` field from every verdict, and compares them.

**What this does not show:**

- behaviour on x86-64 or Windows;
- behaviour with other BLAS backends or older library versions;
- anything about the E1 external study, which ran in one environment.
