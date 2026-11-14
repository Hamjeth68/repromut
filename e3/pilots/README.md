# E3 pilots T and N

These two pilots decide whether the E3 protocol keeps the thread-count family (M-THREADS, §4) and the nondeterministic-baseline group (§5b). The adoption rules are in Appendix A of `e3/E3-PROTOCOL-DRAFT.md`.

The code adds to the E2 harness without changing it. E2's code, plans and results are only read.

## Before running

1. **Commit first.** Commit the protocol draft, this folder, `pilot_n_config.json` and `tests/test_e3_pilots.py`, then push. That timestamps the pilot rules and the pilot N metrics before any pilot result exists.
2. **Log the session** in `INDEPENDENCE.md`.
3. **Start the E2 VM.** `colima start -p repromut-e2` (it must still exist: the pilots reuse its Docker images).
4. **Check the E2 work area is intact.** `~/repromut-e2-work` must still hold `build/<slug>/images.json`, the source snapshots, and the setup artifacts (for example `artifacts/youngcoder45__Student-Performance-Predictor/student.zip`).

## If `~/repromut-e2-work` was lost: restore the pilot inputs first

`restore_inputs.py` rebuilds only what the pilots read, for their four repositories:
- **Source snapshots:** downloaded at the commits recorded in the manifest.
- **Base images:** rebuilt from E2's committed Dockerfiles and lock files, with nothing re-resolved.
- **Package check:** confirms each rebuilt image installs exactly E2's committed package list.
- **Setup data:** re-fetches `student.zip` and checks its SHA-256.

The rebuilt images get new IDs, so the package check is what shows they are the same environments. Everything goes in `e3/pilots/results/restore.json`; cite it in the pilot report.

```bash
colima stop -p repromut-e2 && colima start -p repromut-e2   # so the VM mounts the folder again
python e3/pilots/restore_inputs.py --dry-run
caffeinate -i python e3/pilots/restore_inputs.py
```

If a package list differs, the script stops and shows the difference. Do not continue until you have read it.

## Run

```bash
python -m pytest -q tests/test_e3_pilots.py     # no Docker needed
python e3/pilots/pilot_t.py --dry-run          # selection + prerequisite checks; runs nothing
python e3/pilots/pilot_n.py --dry-run
caffeinate -i python e3/pilots/pilot_t.py
caffeinate -i python e3/pilots/pilot_n.py
```

A dry run exits with status 2 and lists anything missing.

## What each pilot does

**Pilot T** applies the Appendix A.1 rule to E2's records, which selects:
- `fmind/mlops-python-package`
- `ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques`
- `youngcoder45/Student-Performance-Predictor`

Tabular-AutoML comes first in E2's order but is skipped, because its baseline was not stable.

For each repository, pilot T:
1. Runs a `threadpoolctl` diagnostic in the repository's image, once with the thread variables unset and once with `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and `MKL_NUM_THREADS` set to 1. This is not an outcome run.
2. Runs E2's per-repository driver on the single M-THREADS case: 5 baseline, 3 oracle and 3 D runs.

M-THREADS uses E2's M-ENV mechanics (environment variables only), so E2's case code stays unchanged.

**Pilot N** runs `sagnik1511/Tabular-AutoML`, E2's only nondeterministic baseline, twice and independently. Each repeat does 10 baseline runs and 10 runs per constructible E2 case, then a permutation test per metric:
- two metrics, registered in `pilot_n_config.json`: the final best validation accuracy (classification) and the final best validation MSE (regression);
- Bonferroni correction across the two metrics, α = 0.01;
- 10,000 permutations, seed 20261114.

D, S1 and S2 are reported descriptively. D is computed from the first 3 case runs against baseline run 1, not from separate runs as in the main study.

## Outputs

| Path | Contents |
|---|---|
| `e3/pilots/results/T/<slug>.jsonl` | One E2-format case record per repository (baseline + M-THREADS) |
| `e3/pilots/results/T/<slug>.diagnostic.json` | Thread pools seen with the variables unset and set to 1 |
| `e3/pilots/results/T/summary.json` | Labels, whether the setting took effect, and the adoption decision |
| `e3/pilots/results/N/<slug>.repeat{1,2}.jsonl` | Metrics per run, p-values, labels, D/S1/S2 flags |
| `e3/pilots/results/restore.json` | How the pilot inputs were rebuilt: commits, image IDs, package checks, data hashes |
| `e3/pilots/results/N/summary.json` | Whether runs completed, whether labels agree across repeats, and the adoption decision |

Pilot work copies go to `~/repromut-e2-work/e3-pilots/`, which is the only path the VM can see.

## Expected time

These are estimates from E2's baseline run times:
- Pilot T: about 15 minutes. fmind and Student-Performance take about 30 seconds per run.
- Pilot N: about 5 minutes.

## After running

1. Write `e3/PILOT-REPORT.md`: the two summaries, every label, and anything unexpected.
2. Apply the adoption rules exactly as written. Keep or remove §4's M-THREADS and §5b in the protocol.
3. Report the pilot results whatever they show.
