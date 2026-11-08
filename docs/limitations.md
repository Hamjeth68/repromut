# Limitations

1. **Circularity.** The dynamic auditor and the oracle both execute the package. Dynamic recall near 100% on deterministic, single-fault mutations is expected and is **not** evidence of real-world effectiveness. The informative results are:
   - what static and seed-only checks miss;
   - the false alarms static checks raise;
   - localisation;
   - cost.
2. **Mostly synthetic.**
   - E1 adds 30 independently written scikit-learn example scripts. These are documentation code, not research-paper code, and only scripts that print numbers qualify.
   - E1 could not exercise hidden-state failures (stale caches, `.env` overrides, dependency drift).
   - No research-paper repositories have been audited yet (that is stage E2).
   - The operator taxonomy is author-designed.
3. **Scale.** Small CPU-only scikit-learn experiments (400 samples). Not tested on GPU, distributed or deep-learning workloads.
4. **Simulated dependency drift.** Version drift is modelled by `simlib`, a stand-in library, not by real package upgrades.
5. **Single faults.** Two-fault interactions are planned but not yet implemented.
6. **Two environments, both arm64.**
   - The synthetic benchmark gave identical case-level outcomes for all 452 cases (timings excluded) on two setups:
     - Linux aarch64: Python 3.10.12, numpy 2.2.6, scikit-learn 1.7.2.
     - macOS arm64: Python 3.12.13, numpy 2.5.4, scikit-learn 1.9.1.
   - The evidence is in `results/crossplatform-macos-2026-11-09/`.
   - Still untested: x86-64, Windows and other library versions.
   - E1 ran in one environment.
7. **Partly preregistered.** The synthetic run is exploratory and was not preregistered. E1 was preregistered; its 3 documented deviations are in `results/e1-sklearn-examples/DEVIATIONS.md`.
8. **Not a correctness check.** Reproducing a result does not mean the result is scientifically valid.
