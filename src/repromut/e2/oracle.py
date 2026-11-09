"""Independent oracle (protocol section 5). Uses full normalised outputs and tolerances, never auditor flags."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from repromut.e2 import outputs as O

LABELS = ("stable_change", "intermittent_change", "unchanged", "crash", "timeout",
          "install_failure", "infra_failure", "indeterminate")


@dataclass
class Observed:
    """One run as seen by the oracle."""
    status: str                                  # ok | crash | timeout | infra_failure
    outputs: dict[str, np.ndarray] | None = None


def baseline_stable(baseline: list[Observed], rtol: float = O.RTOL, atol: float = O.ATOL) -> bool:
    """All baseline runs succeed and agree pairwise within tolerance."""
    if not baseline or any(b.status != "ok" for b in baseline):
        return False
    ref = baseline[0].outputs
    return all(O.equal(ref, b.outputs, rtol, atol) for b in baseline[1:])


def label(baseline: list[Observed], runs: list[Observed],
          rtol: float = O.RTOL, atol: float = O.ATOL) -> tuple[str, str | None]:
    """Return (label, earliest divergent artifact) for one case.

    A case run 'differs' only if it differs from every baseline run, so baseline jitter
    within tolerance cannot create a change. Non-stable baselines give `indeterminate`.
    """
    if not baseline_stable(baseline, rtol, atol):
        return "indeterminate", None
    if not runs:
        return "indeterminate", None
    statuses = [r.status for r in runs]
    if all(s == "infra_failure" for s in statuses):
        return "infra_failure", None
    if "timeout" in statuses:
        return "timeout", None
    if "crash" in statuses:
        return "crash", None
    if "infra_failure" in statuses:
        return "indeterminate", None
    base_outs = [b.outputs for b in baseline]
    differs = [all(not O.equal(r.outputs, b, rtol, atol) for b in base_outs) for r in runs]
    if not any(differs):
        return "unchanged", None
    first = O.first_difference(base_outs[0], runs[differs.index(True)].outputs, rtol, atol)
    if all(differs):
        agree = all(O.equal(runs[0].outputs, r.outputs, rtol, atol) for r in runs[1:])
        # All runs differ but disagree with each other: not covered by stable/intermittent -> indeterminate.
        return ("stable_change" if agree else "indeterminate"), first
    return "intermittent_change", first
