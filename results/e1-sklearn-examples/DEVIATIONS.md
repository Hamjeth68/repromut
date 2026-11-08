# E1: deviations from the pre-registered protocol

The protocol was registered in commit `382e5fd` on 2026-11-08 at 15:15 +05:30, before any run. Every deviation is listed below, with its effect on the results.

1. **The harness was restructured after the first attempt (execution only).**
   - **What happened:** the first attempt ran in one long process and was killed by the sandbox's roughly 3-minute limit per command. By then it had screened 40 scripts.
   - **Fix:** the driver was rewritten to execute in resumable units. Each unit is one screening task, or one (script, operator) mutation task. Eligibility rules, operators, oracle, auditors and the sampling seed were all left unchanged.
   - **What we did with attempt 1:** its partial data is kept in `aborted_attempt1/`. The full run started from scratch. The 40 scripts screened in both attempts received **identical** eligibility outcomes.

2. **Scripts were screened in parallel, beyond the sample cut-off.**
   - Some scripts after the 30th eligible one were screened. They were not mutated and are not part of the analysis.
   - The sample is defined, exactly as registered, as the first 30 eligible scripts in sampled order.

3. **Crashed units were re-run as a sensitivity analysis.**
   - **What happened:** 9 mutation units crashed or timed out while 4 scripts ran in parallel. Two scripts were affected: `release_highlights/plot_release_highlights_1_3_0.py` and `preprocessing/plot_scaling_importance.py`.
   - **Why we think this is the infrastructure, not the mutations:** both scripts run cleanly in about 1.6 s when run on their own. Their baselines took 6.5 s and 19.6 s under parallel load.
   - **What we report:**
     - **Primary analysis:** follows the registered rule (crash = result changed).
     - **Sensitivity analysis:** the 9 crashed units, re-run once with a single worker (`cases_crash_rerun.jsonl`).
   - Both analyses are reported in `summary.md`. The difference is itself a finding: under resource contention, a dynamic auditor whose policy is "crash = flag" raises spurious alarms.
