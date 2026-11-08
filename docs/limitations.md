# Limitations

1. **Circularity.** The dynamic auditor and the oracle both execute the package. Dynamic recall near 100% on deterministic, single-fault mutations is expected and is **not** evidence of real-world effectiveness. The informative results are:
   - what static and seed-only checks miss;
   - the false alarms static checks raise;
   - localisation;
   - cost.
2. **Synthetic only.** No real research repositories were audited. The taxonomy was designed by the author and has not been validated against an empirical sample of real reproducibility failures.
3. **Scale.** Small CPU-only scikit-learn experiments (400 samples). Not tested on GPU, distributed or deep-learning workloads, or across operating systems.
4. **Simulated dependency drift.** Version drift is modelled by `simlib`, a stand-in library, not by real package upgrades.
5. **Single faults.** Two-fault interactions are planned but not yet implemented.
6. **One environment.** The development run used Linux aarch64, Python 3.10.12, numpy 2.2.6 and scikit-learn 1.7.2. Cross-environment agreement is untested.
7. **Not preregistered.** The current results are exploratory development results.
8. **Not a correctness check.** Reproducing a result does not mean the result is scientifically valid.
