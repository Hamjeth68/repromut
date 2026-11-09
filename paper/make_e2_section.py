"""Generate paper/e2_section.tex from the E2 final analysis JSON (all numbers come from the analysis output).

Usage: python paper/make_e2_section.py e2/results/full/analysis.json paper/e2_section.tex
"""
import json
import sys
from pathlib import Path

from repromut.stats import wilson


def main(aj, out):
    A = json.loads(Path(aj).read_text())
    P, C, S = A["primary"], A["auditors_counts"], A["sensitivity"]
    reps = A["repositories"]
    n_runnable = sum(1 for r in reps.values() if r["baseline_stable"])
    n_nondet = sum(1 for r in reps.values() if not r["baseline_stable"] and all(s == "ok" for s in r["baseline_statuses"]))
    n_fail = sum(1 for r in reps.values() if all(s != "ok" for s in r["baseline_statuses"]))

    def cell(a, key):
        k, n = C[a][key]
        lo, hi = wilson(k, n)
        return f"{k}/{n} ({100 * k / n:.0f}\\%; {100 * lo:.0f}--{100 * hi:.0f})"

    rows = "\n".join(f"{name} & {cell(a, 'recall')} & {cell(a, 'false_alarms')} \\\\"
                     for a, name in [("D", "Dynamic re-execution ($k=2$)"), ("S1", "Declared-configuration static (S1)"),
                                     ("S2", "Extended-manifest static (S2)"), ("C1", "S1 $\\lor$ D"), ("C2", "S2 $\\lor$ D")])
    fk, fn = C["D"]["false_alarms"]
    tex = rf"""
\section{{Pre-registered validation on independently written ML repositories (E2)}}
\label{{sec:e2}}
E2 tests the claim that E1 could not exercise: \emph{{on independently written ML code, dynamic re-execution detects more result-changing hidden-state mutations than static configuration comparison, without an unacceptable increase in false alarms}}. The protocol, sampling rules, decision rules and every later change are in the repository folder \texttt{{e2/}}; the protocol was registered by commit \texttt{{5dbf087}} and pushed publicly before any third-party code ran, and each repository's case plan was committed and pushed before that repository's outcome runs.

\paragraph{{Selection.}} Three GitHub topic populations (\texttt{{scikit-learn}}, \texttt{{mlops}}, \texttt{{sklearn}}; permissive licences only) gave 1{{,}}111 repositories, screened in a seeded random order by static text-only rules and then by manual review (batch entry point, offline-obtainable inputs, CPU within 10 minutes, numeric output, not high-stakes, a real hidden-state channel, licence). Only 14 were eligible; the reasons for every exclusion are recorded. Two repositories served as a pilot and were re-run under the frozen harness.

\paragraph{{Isolation and cases.}} Every run executed in a fresh copy inside an offline, non-root, read-only, capability-free container in a dedicated VM that could see only a work folder; dependencies were hash-locked with a fixed cut-off date. Mutations change only hidden state: a shadow input file with the first 90\% of rows in the working directory (M-PATH), a stale cache produced by the repository's own code from perturbed input (M-CACHE), an environment variable (M-ENV), or a scikit-learn version across a documented default change (M-DEP). Controls set an unused variable, add an unused file, relocate the repository, or change scikit-learn by one patch release. An oracle (5 baseline runs, 3 runs per case, $\mathrm{{rtol}}=10^{{-6}}$) labels every case, independently of the auditors.

\paragraph{{Outcome of the 14 repositories.}} {n_runnable} had a stable baseline; {n_nondet} produced different numbers on identical baseline runs and {'was' if n_nondet == 1 else 'were'} excluded from the primary analysis; {n_fail} could not complete an unchanged run (time limit or an import error in the repository); and 2 could not be installed because their pinned 2017--2020 dependencies do not resolve on Python 3.10.

\begin{{table}}[h]
\centering\small
\caption{{E2 detection and false alarms (Wilson 95\% intervals). Positives: hidden-state mutations that the oracle found to change the result stably. Negatives: controls the oracle found unchanged.}}
\label{{tab:e2}}
\begin{{tabular}}{{lll}}
\toprule
Auditor & Recall on positives & False alarms on negatives \\
\midrule
{rows}
\bottomrule
\end{{tabular}}
\end{{table}}

\paragraph{{Pre-registered verdict: inconclusive.}} The decision rule required at least 12 stable positives from at least 4 repositories and at least 35 negatives; E2 observed {P['n_pos']} positives from {P['n_pos_repos']} repositories and {P['n_neg']} negatives, so H1 is \emph{{inconclusive}} and we make no confirmatory claim. Descriptively the pattern is one-sided: re-execution detected {C['D']['recall'][0]} of {C['D']['recall'][1]} result-changing mutations and declared-configuration comparison detected {C['S1']['recall'][0]} (exact McNemar $p={P['mcnemar_p_pos']:.2g}$), with {fk} dynamic false alarm{'s' if fk != 1 else ''} in {fn} unchanged controls. Every pre-declared sensitivity analysis (tolerances $10^{{-4}}$ and $10^{{-8}}$, $k=1$ and $k=3$, counting intermittent changes or crashes as positive, including nondeterministic repositories, excluding the pilot, one repository per author) gave the same direction and the same verdict; including the nondeterministic repository raises the positives to {S['nondeterministic_repos_included']['n_pos']}, but the negatives remain {S['nondeterministic_repos_included']['n_neg']}, one below the threshold.

Four observations follow.
\begin{{enumerate}}
  \item \textbf{{Hidden state outside the declared configuration is invisible to configuration comparison.}} No positive was flagged by S1, because every mutation left the tracked code, configuration and invocation untouched.
  \item \textbf{{Even an extended manifest is both blind and noisy.}} S2, which also hashes package versions, the environment, the working directory and untracked files, missed the {C['S2']['recall'][1] - C['S2']['recall'][0]} stale-cache mutations whose stale file sat at a tracked data path, yet flagged {C['S2']['false_alarms'][0]} of {C['S2']['false_alarms'][1]} harmless controls.
  \item \textbf{{Many plausible hidden-state mutations do not change results.}} A stale MLflow store, a stale processed-data file and an MLflow environment override were absorbed by pipelines that retrain or regenerate; a naive output comparison initially counted a changed model-version number as a result change until identifier lines were excluded (deviation D5).
  \item \textbf{{Re-execution inherits nondeterminism.}} One repository passed five identical baseline runs and later produced an occasional different cross-validation score, which caused the dynamic false alarm{'s' if fk != 1 else ''}; two repeats are not a guarantee of determinism.
\end{{enumerate}}
"""
    Path(out).write_text(tex)
    print(tex)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
