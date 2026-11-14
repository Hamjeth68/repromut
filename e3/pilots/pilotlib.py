"""E3 pilots T and N (E3 protocol draft, Appendix A).

This module adds to the E2 harness without changing it. It reuses E2's container runner, case
materialisation, oracle, auditors and per-repository driver, and only adds:

- pilot T: the M-THREADS case (run with E2's M-ENV mechanics: three thread variables set to 1),
  a threadpoolctl diagnostic run, and the adoption rule of Appendix A.1;
- pilot N: repeated runs of a baseline-nondeterministic repository, a permutation test on registered
  metrics, the section 5b labels, and the adoption rule of Appendix A.2.

Every executor call goes through `repromut.e2.container.run` (offline, isolated) unless a test injects
a fake. Nothing here reads E2 outcome labels to make a decision, except the pilot T selection rule,
which uses only E2 baseline stability, as Appendix A.1 states.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from repromut.e2 import auditors as A
from repromut.e2 import container as C
from repromut.e2 import outputs as O
from repromut.e2 import study as S
from repromut.e2.cases import BASELINE, CaseSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "e2" / "harness"))
import run_plan as RP  # noqa: E402  (E2 harness helpers: resolve_images, safe_extract, prepare_artifacts)

THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
SEED = 20261114
DECIDABLE_T = {"stable_change", "intermittent_change", "unchanged"}
DIAG_MARK = "REPROMUT_THREADPOOL "
# Imports that load the BLAS and OpenMP runtimes so threadpoolctl can see them.
DIAG_CODE = (
    "import importlib, json\n"
    "for m in ('numpy', 'scipy.linalg', 'sklearn', 'sklearn.cluster'):\n"
    "    try:\n"
    "        importlib.import_module(m)\n"
    "    except Exception:\n"
    "        pass\n"
    "import threadpoolctl\n"
    f"print({DIAG_MARK!r} + json.dumps(threadpoolctl.threadpool_info()))\n"
)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

Executor = Callable[[C.ContainerSpec, list[str]], C.RunResult]


def slug(repo: str) -> str:
    return repo.replace("/", "__")


# ----------------------------------------------------------------------------- pilot T: selection
def select_pilot_t(manifest: dict, e2_results: Path, n: int = 3) -> list[str]:
    """First n E2-eligible repositories, in E2 review order (P1, P2, P3 by seeded order), whose
    registered E2 baseline was stable. 'Measurable' = a baseline record exists and is stable."""
    rank = {"P1": 0, "P2": 1, "P3": 2}
    eligible = [r for r in manifest["repositories"]
                if (r.get("manual_review") or {}).get("decision") == "eligible"]
    eligible.sort(key=lambda r: (rank[r["population"][:2]], r["order"]))
    chosen: list[str] = []
    for r in eligible:
        f = e2_results / f"{slug(r['repo'])}.jsonl"
        if not f.exists():
            continue
        base = [json.loads(l) for l in f.read_text().splitlines() if '"case_id": "baseline"' in l]
        if base and base[0].get("stable") is True:
            chosen.append(r["repo"])
        if len(chosen) == n:
            break
    return chosen


# ----------------------------------------------------------------------------- pilot T: case and diagnostic
def threads_case() -> CaseSpec:
    """M-THREADS uses E2's M-ENV mechanics (env vars only), so E2's case code stays unchanged."""
    return CaseSpec("M-THREADS", "M-ENV", "positive", env={v: "1" for v in THREAD_VARS},
                    note="E3 pilot T: M-THREADS (thread variables set to 1; baseline leaves them unset)")


def parse_threadpool(stdout: str) -> list[dict] | None:
    for line in stdout.splitlines():
        if line.startswith(DIAG_MARK):
            try:
                info = json.loads(line[len(DIAG_MARK):])
            except ValueError:
                return None
            keep = ("user_api", "internal_api", "prefix", "version", "num_threads")
            return [{k: d.get(k) for k in keep} for d in info]
    return None


def thread_signature(info: list[dict] | None) -> list[tuple] | None:
    if info is None:
        return None
    return sorted((d.get("user_api"), d.get("internal_api"), d.get("prefix"), d.get("num_threads")) for d in info)


def run_diagnostic(image: str, env: dict[str, str], root: Path, execute: Executor) -> dict:
    """Separate, non-outcome container run in the repository's image: what thread pools load, and with
    how many threads. Same isolation as every other run (offline, read-only, unprivileged)."""
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    root.chmod(0o777)
    res = execute(C.ContainerSpec(image, root, "/work", ["python", "-I", "-c", DIAG_CODE], dict(env), 120), [])
    shutil.rmtree(root, ignore_errors=True)
    info = parse_threadpool(res.stdout) if res.status == "ok" else None
    return {"status": res.status, "threadpools": info, "stderr_tail": res.stderr[-800:] if res.status != "ok" else ""}


def adopt_t(repos: list[dict]) -> dict:
    """Appendix A.1: adopt if the setting takes effect in at least 2 of 3 repositories and every pilot
    case has a decidable label with no infrastructure failure left after retries."""
    n_effect = sum(1 for r in repos if r.get("diag_differs") is True)
    decidable = len(repos) == 3 and all(r.get("label") in DECIDABLE_T for r in repos)
    return {"adopt": n_effect >= 2 and decidable, "n_setting_took_effect": n_effect,
            "all_labels_decidable": decidable, "n_repositories": len(repos)}


# ----------------------------------------------------------------------------- shared staging
@dataclass
class Staged:
    plan: dict
    tree: Path
    art: Path
    images: dict
    packages: dict


def stage(plan: dict, pilot_work: Path, e2_art: Path, images: dict, packages: dict,
          with_artifacts: bool) -> Staged:
    """Copy the commit-pinned snapshot into the pilot's own work area and apply the plan's setup
    (README steps / A1 data), without touching E2's trees. Optionally prepare host-side artifacts
    (copies and 90%-row perturbations) into the pilot's own artifact directory."""
    s = slug(plan["repo"])
    tree = pilot_work / "trees" / s
    shutil.rmtree(tree, ignore_errors=True)
    tree.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(plan["source_tree"]).expanduser(), tree, symlinks=True)
    setup = plan.get("setup") or {}
    for rel, a in setup.get("add_files", {}).items():
        src = e2_art / a
        if not src.exists():
            raise FileNotFoundError(f"setup artifact missing in E2 work area: {src}")
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, tree / rel)
    for rel in setup.get("extract_zips", []):
        RP.safe_extract(tree / rel, (tree / rel).parent)
    art = pilot_work / "artifacts" / s
    shutil.rmtree(art, ignore_errors=True)
    art.mkdir(parents=True)
    if with_artifacts:
        RP.prepare_artifacts(plan, tree, art)
    return Staged(plan, tree, art, images, packages)


def repo_plan(st: Staged, cases: list[CaseSpec]) -> S.RepoPlan:
    p = st.plan
    return S.RepoPlan(repo=p["repo"], source_tree=st.tree, argv=p["argv"],
                      adapter=O.AdapterSpec.from_dict(p["adapter"]), tracked=RP.tracked_files(st.tree),
                      images=st.images, packages=st.packages, cases=cases, artifacts=st.art,
                      cwd_rel=p.get("cwd_rel") or "", timeout_s=p.get("timeout_s", 600))


# ----------------------------------------------------------------------------- pilot T: driver
def run_pilot_t_repo(st: Staged, out_dir: Path, pilot_work: Path, execute: Executor = C.run) -> dict:
    """Diagnostic for baseline and mutant, then E2's driver on one case (5 baseline, 3 oracle, 3 D runs)."""
    s = slug(st.plan["repo"])
    image = st.images["base"]
    diag_base = run_diagnostic(image, {}, pilot_work / "diag" / f"{s}-base", execute)
    diag_mut = run_diagnostic(image, threads_case().env, pilot_work / "diag" / f"{s}-threads", execute)
    sig_b, sig_m = thread_signature(diag_base["threadpools"]), thread_signature(diag_mut["threadpools"])
    differs = (sig_b is not None and sig_m is not None and sig_b != sig_m)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{s}.diagnostic.json").write_text(json.dumps({"baseline": diag_base, "threads_1": diag_mut,
                                                              "differs": differs}, indent=2))
    recs = S.run_repo(repo_plan(st, [threads_case()]), out_dir / f"{s}.jsonl", pilot_work / "runs", execute)
    rec = next(r for r in recs if r["case_id"] == "M-THREADS")
    return {"repo": st.plan["repo"], "diag_differs": differs, "label": rec["label"],
            "flags": rec["flags"], "d_reason": rec["d_reason"], "first_divergence": rec["first_divergence"]}


# ----------------------------------------------------------------------------- pilot N: metrics and test
def extract_metric(stdout: str, pattern: str, occurrence: str = "last") -> float | None:
    """Value of the registered metric from raw stdout (ANSI colour codes removed). None if absent."""
    vals = []
    for m in re.finditer(pattern, ANSI_RE.sub("", stdout)):
        try:
            vals.append(float(m.group(1)))
        except (ValueError, IndexError):
            continue
    vals = [v for v in vals if np.isfinite(v)]
    if not vals:
        return None
    return vals[-1] if occurrence == "last" else vals[0]


def permutation_pvalue(x, y, n_perm: int = 10_000, seed: int = SEED) -> float | None:
    """Two-sided permutation test on the difference in means. p = (#{|d*| >= |d|} + 1) / (n_perm + 1)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.size == 0 or y.size == 0 or not (np.isfinite(x).all() and np.isfinite(y).all()):
        return None
    pooled = np.concatenate([x, y])
    obs = abs(x.mean() - y.mean())
    rng = np.random.default_rng(seed)
    idx = rng.permuted(np.tile(np.arange(pooled.size), (n_perm, 1)), axis=1)
    perm = pooled[idx]
    d = np.abs(perm[:, :x.size].mean(axis=1) - perm[:, x.size:].mean(axis=1))
    count = int(np.sum(d >= obs - 1e-12 * max(1.0, obs)))
    return (count + 1) / (n_perm + 1)


def label_n(statuses: list[str], pvalues: dict[str, float | None], alpha: float) -> str:
    """Section 5b labels. Failure precedence as in E2's oracle; a missing metric is indeterminate.
    Several registered metrics: Bonferroni, change if any p < alpha / m."""
    if statuses and all(s == "infra_failure" for s in statuses):
        return "infra_failure"
    if "timeout" in statuses:
        return "timeout"
    if "crash" in statuses:
        return "crash"
    if "infra_failure" in statuses or any(s != "ok" for s in statuses):
        return "indeterminate"
    if not pvalues or any(p is None for p in pvalues.values()):
        return "indeterminate"
    m = len(pvalues)
    return "distribution_change" if any(p < alpha / m for p in pvalues.values()) else "no_detected_change"


def adopt_n(repeats: list[list[dict]]) -> dict:
    """Appendix A.2: adopt if every run completed (status ok, within limits) and both repeats give the
    same label for every case."""
    all_ok = all(s == "ok" for rep in repeats for r in rep for s in r["statuses"])
    by_case = [{r["case_id"]: r["label"] for r in rep if r["case_id"] != "baseline"} for rep in repeats]
    same = len(by_case) == 2 and by_case[0] == by_case[1] and len(by_case[0]) > 0
    return {"adopt": all_ok and same, "all_runs_completed": all_ok, "labels_agree_across_repeats": same,
            "labels": by_case}


# ----------------------------------------------------------------------------- pilot N: driver
def run_pilot_n_repeat(st: Staged, cases: list[CaseSpec], cfg: dict, repeat: int, out_dir: Path,
                       pilot_work: Path, execute: Executor = C.run) -> list[dict]:
    """n baseline runs and n runs per case; permutation test per registered metric; labels.
    D/S1/S2 are reported descriptively: D from the first 3 case runs against baseline run #1."""
    n = cfg["n_runs"]
    rp = repo_plan(st, cases)
    s = slug(st.plan["repo"])
    root = pilot_work / "runs" / f"{s}-N-r{repeat}"
    shutil.rmtree(root, ignore_errors=True)

    def runs_for(case: CaseSpec) -> list:
        return [S._execute_once(rp, case, root / f"{case.case_id}-{i}", execute) for i in range(n)]

    def metrics(runs) -> dict[str, list[float | None]]:
        return {m["name"]: [extract_metric(r.raw.stdout, m["pattern"], m.get("occurrence", "last"))
                            if r.raw.status == "ok" else None for r in runs] for m in cfg["metrics"]}

    t0 = time.perf_counter()
    base = runs_for(BASELINE)
    base_m = metrics(base)
    base_fps = [O.fingerprint(r.obs.outputs) if r.obs.outputs is not None else None for r in base]
    recs = [{"repo": st.plan["repo"], "repeat": repeat, "case_id": "baseline", "statuses": [r.raw.status for r in base],
             "metrics": base_m, "n_distinct_fingerprints": len({f for f in base_fps if f}),
             "seconds": time.perf_counter() - t0}]
    for case in cases:
        t1 = time.perf_counter()
        runs = runs_for(case)
        cm = metrics(runs)
        pv = {}
        for name in cm:
            b = [v for v in base_m[name] if v is not None]
            c = [v for v in cm[name] if v is not None]
            complete = len(b) == n and len(c) == n
            pv[name] = permutation_pvalue(b, c, cfg["n_permutations"], cfg["seed"]) if complete else None
        statuses = [r.raw.status for r in base] + [r.raw.status for r in runs]
        fps = [O.fingerprint(r.obs.outputs) if r.obs.outputs is not None else None for r in runs[:3]]
        d = A.dynamic_flag(base_fps[0], fps, 2) if base_fps[0] else A.DynamicResult(True, "execution_failure", [])
        recs.append({"repo": st.plan["repo"], "repeat": repeat, "case_id": case.case_id, "family": case.family,
                     "intent": case.intent, "label": label_n(statuses, pv, cfg["alpha"]), "pvalues": pv,
                     "metrics": cm, "statuses": [r.raw.status for r in runs],
                     "flags": {"D": d.flag, "S1": A.static_flag(base[0].s1, runs[0].s1),
                               "S2": A.static_flag(base[0].s2, runs[0].s2)},
                     "d_reason": d.reason, "seconds": time.perf_counter() - t1})
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{s}.repeat{repeat}.jsonl").open("w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    shutil.rmtree(root, ignore_errors=True)
    return recs
