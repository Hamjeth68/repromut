"""Run one registered repository plan (e2/plans/<slug>.json) under the E2 harness.

Usage: python e2/harness/run_plan.py e2/plans/<slug>.json <results_dir>
All third-party code runs only inside offline containers (repromut.e2.container).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from repromut.e2 import outputs as O
from repromut.e2.cases import CaseSpec, perturb_rows
from repromut.e2.study import RepoPlan, run_repo

WORK = Path.home() / "repromut-e2-work"          # the only directory the VM can see


def tracked_files(tree: Path) -> list[str]:
    return sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file() and not p.is_symlink())


def prepare_artifacts(plan: dict, tree: Path, art: Path) -> None:
    """Deterministic shadow/stale inputs declared in the plan: copy or 90%-row perturbation of a tracked file."""
    art.mkdir(parents=True, exist_ok=True)
    for name, spec in plan.get("artifacts", {}).items():
        data = (tree / spec["from"]).read_bytes()
        if spec["method"] == "perturb_rows":
            data = perturb_rows(data, spec.get("fraction", 0.9), spec.get("header", True))
        elif spec["method"] != "copy":
            raise ValueError(spec["method"])
        (art / name).write_bytes(data)


def main(plan_path: str, results_dir: str) -> None:
    plan = json.loads(Path(plan_path).read_text())
    tree = Path(plan["source_tree"]).expanduser()
    slug = plan["repo"].replace("/", "__")
    art = WORK / "artifacts" / slug
    prepare_artifacts(plan, tree, art)
    packages = {k: Path(v).expanduser().read_text() for k, v in plan["packages"].items()}
    rp = RepoPlan(repo=plan["repo"], source_tree=tree, argv=plan["argv"],
                  adapter=O.AdapterSpec.from_dict(plan["adapter"]), tracked=tracked_files(tree),
                  images=plan["images"], packages=packages,
                  cases=[CaseSpec.from_dict(c) for c in plan["cases"]], artifacts=art,
                  cwd_rel=plan.get("cwd_rel", ""), timeout_s=plan.get("timeout_s", 600))
    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    recs = run_repo(rp, out / f"{slug}.jsonl", WORK / "runs")
    for r in recs:
        print(r["case_id"], r["label"], r["flags"], r["d_reason"], flush=True)


if __name__ == "__main__":
    os.environ.setdefault("DOCKER_CONTEXT", "colima-repromut-e2")
    main(sys.argv[1], sys.argv[2])
