"""Resumable per-repository driver: baseline, oracle runs, auditor runs, structured case records.

The executor is injected so the whole pipeline is tested without Docker or third-party code.
Infrastructure failures are retried up to 2 times and are never counted as detections.
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from repromut.e2 import auditors as A
from repromut.e2 import container as C
from repromut.e2 import outputs as O
from repromut.e2.cases import BASELINE, CaseSpec, materialise
from repromut.e2.oracle import Observed, baseline_stable, label

N_BASELINE, N_ORACLE, N_DYNAMIC, K_PRIMARY = 5, 3, 3, 2
INFRA_RETRIES = 2


@dataclass
class RepoPlan:
    repo: str
    source_tree: Path                     # extracted commit-pinned snapshot (read only)
    argv: list[str]
    adapter: O.AdapterSpec
    tracked: list[str]                    # files in the commit snapshot (relative)
    images: dict[str, str]                # image_key -> digest-pinned image
    packages: dict[str, str]              # image_key -> resolved package list text (lock / pip freeze)
    cases: list[CaseSpec]
    artifacts: Path                       # stale/shadow artifacts prepared before outcome runs
    cwd_rel: str = ""
    timeout_s: float = 600.0


Executor = Callable[[C.ContainerSpec, list[str]], C.RunResult]


@dataclass
class _Run:
    obs: Observed
    raw: C.RunResult
    s1: dict = field(default_factory=dict)
    s2: dict = field(default_factory=dict)


def _execute_once(plan: RepoPlan, case: CaseSpec, run_root: Path, execute: Executor) -> _Run:
    for attempt in range(INFRA_RETRIES + 1):
        if run_root.exists():
            shutil.rmtree(run_root)
        cwd, argv, repo_host = materialise(case, plan.source_tree, run_root, plan.artifacts,
                                           list(plan.argv), plan.cwd_rel)
        env = {**case.env}
        s1 = A.s1_manifest(repo_host, plan.tracked, plan.argv)
        s2 = A.s2_manifest(repo_host, plan.tracked, plan.argv, packages=plan.packages[case.image_key],
                           env={**env, **C.FIXED_ENV}, cwd_abs=cwd)
        spec = C.ContainerSpec(plan.images[case.image_key], run_root, cwd, argv, env, plan.timeout_s)
        # Declared outputs are relative to the run's working directory, so an M-PATH run (cwd in the
        # sibling tree) is read from where it actually writes, not reported as "missing".
        cwd_rel_root = Path(cwd.removeprefix("/work").lstrip("/"))
        declared = [(cwd_rel_root / f).as_posix() for f in plan.adapter.files]
        res = execute(spec, declared)
        if res.status != "infra_failure":
            break
    files = {Path(k).relative_to(cwd_rel_root).as_posix(): v for k, v in res.files.items()}
    outs = O.collect(plan.adapter, res.stdout, files) if res.status == "ok" else None
    shutil.rmtree(run_root, ignore_errors=True)
    return _Run(Observed(res.status, outs), res, s1, s2)


def _done(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {r["case_id"]: r for r in map(json.loads, path.read_text().splitlines()) if r.get("repo")}


def _append(path: Path, rec: dict) -> None:
    with path.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")


def run_repo(plan: RepoPlan, out_jsonl: Path, work_base: Path, execute: Executor = C.run) -> list[dict]:
    """Run baseline and all cases for one repository, appending one record per case (resumable)."""
    done = _done(out_jsonl)
    slug = plan.repo.replace("/", "__")
    if "baseline" in done:
        b = done["baseline"]
        base_obs = [Observed(s, O.from_jsonable(o) if o is not None else None)
                    for s, o in zip(b["statuses"], b["outputs"])]
        base_s1, base_s2 = b["s1"], b["s2"]
    else:
        runs = [_execute_once(plan, BASELINE, work_base / slug / f"baseline-{i}", execute) for i in range(N_BASELINE)]
        base_obs = [r.obs for r in runs]
        base_s1, base_s2 = runs[0].s1, runs[0].s2
        _append(out_jsonl, {"repo": plan.repo, "case_id": "baseline", "family": "BASELINE", "intent": "baseline",
                            "statuses": [o.status for o in base_obs],
                            "outputs": [O.to_jsonable(o.outputs) if o.outputs is not None else None for o in base_obs],
                            "stable": baseline_stable(base_obs), "s1": base_s1, "s2": base_s2,
                            "seconds": [r.raw.seconds for r in runs]})
    base_fp = O.fingerprint(base_obs[0].outputs) if base_obs[0].outputs is not None else None
    records = []
    for case in plan.cases:
        if case.case_id in done:
            records.append(done[case.case_id])
            continue
        t0 = time.perf_counter()
        orc = [_execute_once(plan, case, work_base / slug / f"{case.case_id}-o{i}", execute) for i in range(N_ORACLE)]
        dyn = [_execute_once(plan, case, work_base / slug / f"{case.case_id}-d{i}", execute) for i in range(N_DYNAMIC)]
        lab, first = label(base_obs, [r.obs for r in orc])
        if all(r.raw.status == "infra_failure" for r in dyn):
            lab = "infra_failure"
        fps = [O.fingerprint(r.obs.outputs) if r.obs.outputs is not None else None for r in dyn]
        dres = {k: A.dynamic_flag(base_fp, fps, k) for k in (1, 2, 3)} if base_fp else None
        s1 = A.static_flag(base_s1, dyn[0].s1)
        s2 = A.static_flag(base_s2, dyn[0].s2)
        d = dres[K_PRIMARY] if dres else A.DynamicResult(True, "execution_failure", [])
        c1, c1_src = A.combine(s1, d)
        c2, c2_src = A.combine(s2, d)
        rec = {"repo": plan.repo, "case_id": case.case_id, "family": case.family, "intent": case.intent,
               "label": lab, "first_divergence": first,
               "flags": {"S1": s1, "S2": s2, "D": d.flag, "C1": c1, "C2": c2,
                         "D_k1": dres[1].flag if dres else True, "D_k3": dres[3].flag if dres else True},
               "d_reason": d.reason, "c1_source": c1_src, "c2_source": c2_src,
               "oracle_statuses": [r.raw.status for r in orc], "dynamic_statuses": [r.raw.status for r in dyn],
               "seconds": time.perf_counter() - t0, "note": case.note}
        _append(out_jsonl, rec)
        records.append(rec)
    return records
