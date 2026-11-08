"""Reported-result records and the compared audit methods.

Audit task: given a *shipped* experiment package and the *reported record*
produced by the author's original run, decide whether re-executing the shipped
package will fail to reproduce the reported result, and if so, which pipeline
stage first diverges.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import RESULT_STAGES, STAGES
from .fingerprint import fingerprint_json, fingerprint_stage
from .runner import RunResult, read_package, run_package

DECLARED_SECTIONS = ("task", "seeds", "data", "split", "preprocess", "model",
                     "evaluation", "dependencies")
SECTION_STAGE = {
    "task": "data", "data": "data", "split": "split", "preprocess": "preprocess",
    "evaluation": "preprocess", "dependencies": "preprocess", "model": "model",
}
SEED_STAGE = {"data": "data", "split": "split", "model": "model"}


def declared_manifest(config: dict) -> dict:
    return {sec: fingerprint_json(config.get(sec)) for sec in DECLARED_SECTIONS}


def stage_fingerprints(result: RunResult) -> dict:
    return {stage: fingerprint_stage(result.arrays[stage]) for stage in STAGES}


def make_record(config: dict, result: RunResult) -> dict:
    """The record an author would publish alongside the package."""
    return {
        "name": config["name"],
        "manifest": declared_manifest(config),
        "seeds": dict(config["seeds"]),
        "stages": stage_fingerprints(result),
        "metrics": dict(result.metrics),
    }


@dataclass
class Verdict:
    method: str
    flagged: bool
    stage: str | None
    reason: str
    elapsed_s: float


def _earliest(stages) -> str | None:
    stages = [s for s in stages if s]
    return min(stages, key=STAGES.index) if stages else None


def audit_none(pkg: Path, record: dict) -> Verdict:
    t = time.perf_counter()
    run_package(pkg)  # "it ran without error"
    return Verdict("no_audit", False, None, "execution succeeded", time.perf_counter() - t)


def audit_seed_only(pkg: Path, record: dict) -> Verdict:
    t = time.perf_counter()
    seeds = read_package(pkg).config.get("seeds", {})
    bad = [k for k in ("data", "split", "model")
           if not (isinstance(seeds.get(k), int) and not isinstance(seeds.get(k), bool))]
    changed = [k for k in ("data", "split", "model")
               if k not in bad and seeds.get(k) != record["seeds"].get(k)]
    problems = bad + changed
    stage = _earliest(SEED_STAGE[k] for k in problems)
    reason = (f"non-literal seeds: {bad}; changed seeds: {changed}" if problems
              else "all seeds declared and match the record")
    return Verdict("seed_only", bool(problems), stage, reason, time.perf_counter() - t)


def audit_static(pkg: Path, record: dict) -> Verdict:
    t = time.perf_counter()
    cfg = read_package(pkg).config
    current = declared_manifest(cfg)
    diff = [s for s in DECLARED_SECTIONS if current[s] != record["manifest"][s]]
    stages = []
    for sec in diff:
        if sec == "seeds":
            stages += [SEED_STAGE[k] for k in ("data", "split", "model")
                       if cfg["seeds"].get(k) != record["seeds"].get(k)]
        else:
            stages.append(SECTION_STAGE[sec])
    reason = f"declared sections differ: {diff}" if diff else "declared manifest matches"
    return Verdict("static_manifest", bool(diff), _earliest(stages), reason,
                   time.perf_counter() - t)


def audit_dynamic(pkg: Path, record: dict, repeats: int = 2) -> Verdict:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    t = time.perf_counter()
    runs = [stage_fingerprints(run_package(pkg)) for _ in range(repeats)]
    first = runs[0]
    mismatch_ref = [s for s in STAGES if first[s] != record["stages"][s]]
    unstable = [s for s in STAGES if any(r[s] != first[s] for r in runs[1:])]
    result_bad = any(s in RESULT_STAGES for s in mismatch_ref + unstable)
    stage = None
    if result_bad:
        stage = _earliest(mismatch_ref) or _earliest(unstable)
    if result_bad:
        reason = (f"result differs from record (first divergence: {stage}); "
                  f"unstable across {repeats} runs: {bool(unstable)}")
    elif mismatch_ref or unstable:
        reason = "intermediate artifacts differ but result reproduces"
    else:
        reason = "all stage fingerprints reproduce"
    return Verdict("dynamic", result_bad, stage, reason, time.perf_counter() - t)


def audit_combined(pkg: Path, record: dict, repeats: int = 2,
                   static: Verdict | None = None, dynamic: Verdict | None = None) -> Verdict:
    t = time.perf_counter()
    static = static or audit_static(pkg, record)
    dynamic = dynamic or audit_dynamic(pkg, record, repeats)
    flagged = static.flagged or dynamic.flagged
    stage = dynamic.stage if dynamic.flagged else static.stage
    elapsed = static.elapsed_s + dynamic.elapsed_s + (time.perf_counter() - t)
    return Verdict("combined", flagged, stage,
                   f"static: {static.flagged}; dynamic: {dynamic.flagged}", elapsed)
