"""Ground-truth oracle.

Independent of the auditors: it compares *full arrays* with absolute/relative
tolerances (not hashes) against the baseline run, using more repetitions than
any auditor. It reports whether the declared result changed and the first
stage at which any execution diverged.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import RESULT_STAGES, STAGES
from .fingerprint import stage_allclose
from .runner import PackageSpec, RunResult, execute


@dataclass
class OracleObservation:
    result_changed: bool
    first_stage: str | None


def observe(mutant: PackageSpec, baseline: RunResult, repeats: int = 3) -> OracleObservation:
    runs = [execute(mutant) for _ in range(repeats)]
    divergent: set[str] = set()
    for r in runs:
        for s in STAGES:
            if not stage_allclose(r.arrays[s], baseline.arrays[s]):
                divergent.add(s)
    for r in runs[1:]:
        for s in STAGES:
            if not stage_allclose(r.arrays[s], runs[0].arrays[s]):
                divergent.add(s)
    changed = any(s in divergent for s in RESULT_STAGES)
    first = min(divergent, key=STAGES.index) if divergent else None
    return OracleObservation(changed, first)
