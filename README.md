# ReproMut

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24048005.svg)](https://doi.org/10.5281/zenodo.24048005)
[![ci](https://github.com/Hamjeth68/repromut/actions/workflows/ci.yml/badge.svg)](https://github.com/Hamjeth68/repromut/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Hamjeth68/repromut?include_prereleases)](https://github.com/Hamjeth68/repromut/releases)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**A controlled mutation benchmark for dynamic reproducibility testing of small machine-learning experiments.**

> **Headline finding (exploratory):** seed checks and config-manifest checks missed **every** stale cache, hidden `.env` override and dependency drift we planted. Overall, seed checks caught 29% of the planted faults and config-manifest checks 73%; re-running the experiment caught all of them. [Read the preprint →](https://doi.org/10.5281/zenodo.24090849)

![Recall by mutation family](paper/figures/recall_by_family.png)

Status: `0.1.1`. This is a public exploratory release archived on Zenodo. Its synthetic development run was not preregistered and is not a confirmatory study.

The unreleased **E1 external validation** below was preregistered separately.

## Research question

When an ML experiment is shipped, which checks can tell whether re-running it will reproduce the reported result? And how much does each kind of check miss?

ReproMut deliberately breaks small, fully synthetic, CPU-only experiments in known ways. It then measures how well each auditing method detects and localises the breakage:

- **12 result-changing mutations:** unset or time-derived seeds, a changed split seed, row order, dependency default drift, a hidden `.env` override, float32 precision, a stale cache, train/eval preprocessing mismatch, generator drift (two kinds), and a loosened solver tolerance.
- **7 semantics-preserving controls:** renames, output path, notes, log level, thread count, a dependency patch bump, and config key order.
- **5 audit methods:** none, seed-only, static manifest, dynamic (repeated execution plus stage fingerprints), and static + dynamic combined.
- **An independent oracle:** it compares full arrays at a fixed tolerance, with more repeats than any auditor. The test suite checks every declared label and stage against it.

## Download

Ready-made downloads are on the [Releases page](https://github.com/Hamjeth68/repromut/releases):

- the wheel and source package;
- the preprint PDF;
- the raw results;
- SHA-256 checksums.

Releases are built automatically by `.github/workflows/release.yml` whenever a `v*` tag is pushed.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest -q                                          # 658 tests, ~30 s on 4 CPUs
repromut bench --smoke --out results/smoke         # 3 experiments, seconds
repromut bench --out results/full                  # 28 experiments, 452 cases, under 1 min
```

Audit one package by hand:

```bash
repromut list-mutations
repromut export reg-ridge-lownoise --mutation env_override --out /tmp/demo
repromut audit /tmp/demo/package --record /tmp/demo/record.json
```

Requirements: Python ≥ 3.10, numpy, scipy and scikit-learn. No GPU, network access or third-party datasets are needed.

## Development-run results (exploratory)

The full table is in [`results/dev-2026-11-08/summary.md`](results/dev-2026-11-08/summary.md). Summary of the 452 cases:

| Method | Recall (95% CI) | False-positive rate (95% CI) |
|---|---|---|
| seed-only | 29.4% (24.3–35.1) | 0.0% (0.0–2.1) |
| static manifest | 72.8% (67.2–77.7) | 6.7% (3.9–11.3) |
| dynamic | 100% (98.6–100) | 0.0% (0.0–2.1) |

The static manifest checker misses everything not written in the config: stale caches, hidden env overrides, and dependency drift. It also raises false alarms on harmless thread-count changes.

**Read this before quoting the numbers.** The dynamic auditor and the oracle both execute the package, so near-perfect dynamic recall on deterministic mutations is expected by construction. These numbers are not a confirmatory result. See [`docs/limitations.md`](docs/limitations.md).

## External validation E1: independently written code (pre-registered)

**Protocol:** [`PROTOCOL-E1-external.md`](PROTOCOL-E1-external.md), pushed in commit `382e5fd` before any run.

**Sample:** 30 scikit-learn 1.7.2 example scripts, drawn in a random order seeded from the preprint DOI. That took screening 114 scripts.

**Ground truth:** decided by execution, not declared in advance.

**Results:** 199 mutation cases. Full tables are in [`results/e1-sklearn-examples/summary.md`](results/e1-sklearn-examples/summary.md); deviations from the protocol are in [`DEVIATIONS.md`](results/e1-sklearn-examples/DEVIATIONS.md).

| Auditor | Recall | False-positive rate |
|---|---|---|
| Seed-only | 75% | 3.1% |
| Static manifest | 100% | 7.7% |
| Dynamic (2 runs) | 99% | 0% |

These are the sensitivity-analysis figures. The registered analysis gives 71% / 1.6%, 93% / 6.5% and 99% / 0%.

What E1 found:

- **The seed-only blind spot transfers to real code.** Seed checks missed every changed split size and fold count.
- **13% of plausible "breaking" changes didn't change the result.** The static check raised a false alarm on every one of them.
- **2 of 32 runnable scripts weren't reproducible run-to-run** before any change was made.
- **Re-running has its own failure modes.** Two repeats missed one intermittent effect, and running several scripts in parallel caused 9 spurious crashes.

**Not shown by E1:** the hidden-state gap (stale caches, `.env` overrides, dependency drift). The generic environment operators changed nothing on these scripts, so this claim still rests only on the synthetic suite.

**Next stage (E2):** research-paper repositories, run in isolated CI under a separate pre-registered protocol.

## What v0.1 demonstrates — and what it does not

**Demonstrated (development run on 2026-11-08, Linux aarch64, Python 3.10, scikit-learn 1.7.2):**

- All 28 baseline experiments are repeatable across repeated runs at a strict numerical tolerance (`atol=rtol=1e-12`).
- All 452 mutation/experiment pairs behave as declared, according to the independent oracle.
- The detection rates in the table above, on this synthetic suite.

**Not demonstrated:**

- Performance on real research repositories.
- How complete the mutation taxonomy is.
- GPU, distributed or deep-learning workloads.
- Usability for other researchers.
- Stability across future library versions.
- Scientific correctness of any audited experiment. **Passing ReproMut does not mean an experiment is correct.**

## Preprint

A draft preprint is in [`paper/repromut-preprint.pdf`](paper/repromut-preprint.pdf), with its source in `paper/`. Rebuild the figures with `python paper/make_figures.py results/dev-2026-11-08 paper/figures`, then compile with `latexmk -pdf paper/repromut-preprint.tex`.

## Repository map

| Path | Contents |
|---|---|
| `src/repromut/runner.py` | Package format and hermetic executor |
| `src/repromut/experiments.py` | 28 baseline experiments and the seed hierarchy |
| `src/repromut/mutations.py` | Mutation catalog |
| `src/repromut/auditors.py` | Audit methods and record format |
| `src/repromut/oracle.py` | Ground-truth oracle |
| `src/repromut/benchmark.py` | Benchmark runner and report |
| `docs/` | Method, taxonomy, data card, limitations, related-work plan |
| `PREREGISTRATION.md` | Draft hypothesis to freeze before the confirmatory run |
| `INDEPENDENCE.md` | Provenance and employment-separation log |

## Licence

- **Code:** Apache-2.0 (see `LICENSE`).
- **Documentation:** CC BY 4.0.
- **Generated fixtures:** CC0.

See `INDEPENDENCE.md` for the project's provenance and separation record. That record is evidence, not a legal conclusion.

## Citation

Preprint (draft v0.3, latest): Misree, H. (2026). *ReproMut: A Controlled Mutation Benchmark for Comparing Reproducibility Auditors on Small Machine-Learning Experiments.* Zenodo. https://doi.org/10.5281/zenodo.24090849

Earlier drafts: v0.2 https://doi.org/10.5281/zenodo.24048206 · v0.1 https://doi.org/10.5281/zenodo.24048006

To cite all versions, use the concept DOI 10.5281/zenodo.24048005. Machine-readable metadata is in `CITATION.cff`.

## E2: pre-registered test on independently written ML repositories

Protocol, deviations, case plans and raw records are in [`e2/`](e2/). Results: [`e2/RESULTS-REPORT.md`](e2/RESULTS-REPORT.md). The pre-registered verdict is **inconclusive** (10 result-changing cases against 12 required). Descriptively, re-execution detected 10/10 and declared-configuration comparison 0/10, with 1 dynamic false alarm in 34 controls.
