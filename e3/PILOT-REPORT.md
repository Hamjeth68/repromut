# E3 pilot report: pilots T and N

**Date:** 2026-11-14.

**What these pilots decide:** whether E3 includes the thread-count mutation family (M-THREADS, protocol §4) and the nondeterministic-baseline group (§5b).

**Rules:** the pilot plans and adoption rules are in Appendix A of `e3/E3-PROTOCOL-DRAFT.md`. They were committed in `271e39d` (2026-11-14 09:57 +0530, pushed to GitHub) together with the pilot code and pilot N's metrics (`e3/pilots/pilot_n_config.json`). The restore and both pilots ran after that commit.

**Repositories:** both pilots used E2 repositories only. §2.3 of the protocol removes every E2 repository from E3's populations, so no E3 repository has been run.

**Raw results:** `e3/pilots/results/` (`restore.json`, `T/`, `N/`).

## 1. Pilot inputs had to be rebuilt

The E2 work area (`~/repromut-e2-work`) had been lost. Only E2's committed records remained, plus the pinned Python base images inside the E2 VM. Before the pilots, `e3/pilots/restore_inputs.py` rebuilt the inputs the pilots read, for their four repositories, from E2's committed records alone:

| Repository | Snapshot | Rebuilt image installs E2's committed package list | Setup data |
|---|---|---|---|
| fmind/mlops-python-package | downloaded at `1dcea8d` | yes, identical | none |
| ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques | downloaded at `fd45b93` | yes, identical | none |
| youngcoder45/Student-Performance-Predictor | downloaded at `4191a1b` | yes, identical | `student.zip`, SHA-256 matches `e2/env/datasets.json` |
| sagnik1511/Tabular-AutoML | downloaded at `cada595` | yes, identical | none |

- **How:** each image was rebuilt from E2's committed Dockerfile and its hash-locked lock file (or `uv.lock`), with nothing re-resolved.
- **Image IDs:** the rebuilt images have new IDs. The package-list match is the evidence that they are the same environments. All the IDs are in `restore.json`.
- **Archive check:** no archive member was skipped as unsafe.

**Limits:**
1. fmind's original E2 image ID was never committed, so only its package list can be compared.
2. Text-Classifier's NLTK data is downloaded during the image build. E2 did not commit hashes for it, so we cannot show the rebuilt data is byte-identical to E2's. The new hashes are recorded in `restore.json`.

Neither limit affects the pilot comparisons, because each pilot compares runs inside its own rebuilt environment.

## 2. Pilot T: thread-count family

**Repositories:** the Appendix A.1 rule (the first 3 baseline-stable E2 repositories in E2's review order) selected fmind, Text-Classifier and Student-Performance.

**Procedure:**
- One M-THREADS case per repository: `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and `MKL_NUM_THREADS` set to 1. The baseline leaves them unset. The case uses E2's M-ENV mechanics.
- Runs per repository: 5 baseline, 3 oracle and 3 D runs, plus a `threadpoolctl` diagnostic for the unset and set states.

**Did the setting take effect?** Yes, in all 3 repositories:

| Repository | Thread pools, variables unset | Variables set to 1 |
|---|---|---|
| fmind | OpenMP 4, OpenBLAS 4, OpenBLAS 4 | all 1 |
| Text-Classifier | OpenBLAS 4, OpenBLAS 4, OpenMP 4 | all 1 |
| Student-Performance | OpenBLAS 4, OpenBLAS 4, OpenMP 4 | all 1 |

The two OpenBLAS entries are the copies bundled with numpy and scipy. By default the libraries start 4 threads, matching the VM's 4 CPUs, although each container is limited to 2 CPUs.

**Results:**

| Repository | Oracle label | D | S1 | S2 |
|---|---|---|---|---|
| fmind | `unchanged` | no flag | no flag | flag |
| Text-Classifier | `unchanged` | no flag | no flag | flag |
| Student-Performance | `unchanged` | no flag | no flag | flag |

Going from 4 threads to 1 left every output identical. D compares 8-decimal fingerprints and saw no difference. S2 flagged all three, because it compares the full environment map, where the variables differ.

**Decision: adopt M-THREADS.** The rule asked for the setting to take effect in at least 2 of 3 repositories (it did in 3) and for every case to get a decidable label (all 3 did, all `unchanged`). No infrastructure failures remained.

**What it means for E3.** This is stated before any E3 run, so it cannot be presented later as a finding:
- M-THREADS is expected to produce mostly equivalent mutations, not positives.
- Those cases count as negatives only in sensitivity analysis 4. There, they measure S2 flagging hidden changes that do not change results.
- Reaching the minimum of 12 positives still depends on the sample size of 24 and the P5 fallback.
- The result agrees with E2's synthetic benchmark, where every static false alarm came from a harmless thread-count change.

## 3. Pilot N: nondeterministic-baseline group

**Repository:** `sagnik1511/Tabular-AutoML`, E2's only repository with a nondeterministic baseline.

**Procedure:**
- Two independent repeats. Each repeat ran 10 baseline runs and 10 runs for each of 5 constructible E2 cases: 120 runs in total.
- Test: a permutation test on two metrics registered in advance, with a Bonferroni correction (change if p < 0.005).
  - classification: final best validation accuracy on Iris;
  - regression: final best validation MSE on Wine.

**All 120 runs completed.**

**Baseline variation.** All 10 baseline runs gave different outputs in each repeat (10 distinct fingerprints out of 10).
- Validation MSE ranged from 0.3167 to 0.3219 in repeat 1, and from 0.3194 to 0.3219 in repeat 2.
- Classification accuracy was 1.0 in every run of both repeats.

**Results** (p-values for MSE; accuracy gave p = 1.0 for every case):

| Case | Repeat 1 label (p) | Repeat 2 label (p) | Plain D | S1 | S2 |
|---|---|---|---|---|---|
| M-PATH-wine | `distribution_change` (0.0001) | `distribution_change` (0.0001) | flag, both | no | flag |
| M-PATH-iris | `no_detected_change` (0.87) | `no_detected_change` (0.31) | flag, both | no | flag |
| C-ENV | `no_detected_change` (0.22) | `no_detected_change` (0.39) | flag, both | no | flag |
| C-CACHE | `no_detected_change` (0.10) | `no_detected_change` (0.039) | flag, both | no | flag |
| C-PATH | `no_detected_change` (0.23) | `no_detected_change` (0.13) | flag, both | no | flag |

**Decision: adopt the §5b group.** The rule asked for every run to complete (all 120 did) and for both repeats to give the same label for every case (all 5 matched).

**Observations:**
- **Plain D failed here, as expected.** D flagged every case in both repeats, including all three controls: 6 of 6 control flags were false alarms. On code that does not repeat itself, comparing exact outputs flags everything. The noise-aware test labelled the controls `no_detected_change`. Its smallest control p-value was 0.039, well above the 0.005 threshold.
- **M-PATH-wine was detected clearly in both repeats.** p = 0.0001 is the smallest value 10,000 permutations can give, meaning no permutation was as extreme as the observed difference.
- **M-PATH-iris was not detected,** because its only registered metric was constant. Iris accuracy was 1.0 in every run, so it could only detect a case that lowers it. This does not show that M-PATH-iris left all outputs unchanged. It shows the registered metric could not see it. §5b now requires reports to say when a label rests only on constant metrics.

## 4. Other notes

- **Pilot N's D computation.** D was computed from the first 3 runs of each case against baseline run 1, not from separate runs as in the main study. This is stated in Appendix A.2 and in `e3/pilots/README.md`.
- **Fresh baselines.** Both pilots took new baselines in the rebuilt environments. Nothing was compared with E2's recorded outputs.
- **Pilot code.** No pilot code or setting was changed after commit `271e39d`.

## 5. Protocol changes made after the pilots

All of these are in `e3/E3-PROTOCOL-DRAFT.md` and were made before registration:
- §4 and §5b are marked adopted, and the "if not adopted" wording is removed.
- §4 records that M-THREADS is expected to add mostly equivalent mutations.
- §5b adds the reporting rule for constant metrics.
- Appendix A records both outcomes, and Appendix B marks the pilot step done.

Nothing else changed.
