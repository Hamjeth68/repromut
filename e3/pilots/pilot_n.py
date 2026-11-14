"""E3 pilot N (nondeterministic-baseline group), E3 protocol draft Appendix A.2.

Usage (on the Mac, from the repository root, with the repromut-e2 Colima VM running):
    python e3/pilots/pilot_n.py --dry-run     # prerequisite checks, runs nothing
    python e3/pilots/pilot_n.py               # 2 independent repeats of 10 baseline + 10 runs per case

Settings come from e3/pilots/pilot_n_config.json, which must be committed before the first run.
Outputs: e3/pilots/results/N/<slug>.repeat{1,2}.jsonl and summary.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilotlib as PL  # noqa: E402
from repromut.e2.cases import CaseSpec  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="check prerequisites; run nothing")
    ap.add_argument("--config", default=str(PL.REPO_ROOT / "e3" / "pilots" / "pilot_n_config.json"))
    args = ap.parse_args(argv)
    root, work = PL.REPO_ROOT, PL.RP.WORK
    cfg = json.loads(Path(args.config).read_text())
    repo = cfg["repo"]
    s = PL.slug(repo)
    plan = json.loads((root / "e2" / "plans" / f"{s}.json").read_text())
    problems = []
    try:
        images, packages = PL.RP.resolve_images(plan, s)
    except (FileNotFoundError, KeyError) as e:
        images, packages = {}, {}
        problems.append(f"E2 image record missing ({e}); E2 build area must still exist")
    if images and "base" not in images:
        problems.append("no base image in E2 build record")
    if not Path(plan["source_tree"]).expanduser().exists():
        problems.append(f"source snapshot missing: {plan['source_tree']}")
    print(f"Repository: {repo}\nMetrics: {[m['name'] for m in cfg['metrics']]}  alpha={cfg['alpha']} "
          f"(Bonferroni over {len(cfg['metrics'])})  runs={cfg['n_runs']}  repeats={cfg['repeats']}")
    if problems:
        print("NOT READY:\n  " + "\n  ".join(problems))
        return 2
    print("Prerequisites OK.")
    if args.dry_run:
        return 0
    os.environ.setdefault("DOCKER_CONTEXT", "colima-repromut-e2")
    pilot_work = work / "e3-pilots" / "N"
    out_dir = root / "e3" / "pilots" / "results" / "N"
    st = PL.stage(plan, pilot_work, work / "artifacts" / s, images, packages, with_artifacts=True)
    cases = [CaseSpec.from_dict(c) for c in plan["cases"]
             if c.get("image_key", "base") in images
             and all((st.art / a).exists() for a in [*c.get("pre_files", {}).values(), *c.get("shadow_files", {}).values()])]
    print("Cases:", [c.case_id for c in cases])
    repeats = []
    for r in range(1, cfg["repeats"] + 1):
        recs = PL.run_pilot_n_repeat(st, cases, cfg, r, out_dir, pilot_work)
        for x in recs[1:]:
            print(f"repeat {r}  {x['case_id']:14s} {x['label']:20s} p={x['pvalues']}  D={x['flags']['D']}", flush=True)
        repeats.append(recs)
    summary = {"pilot": "N", "repo": repo, "config": cfg, **PL.adopt_n(repeats)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("adopt", "all_runs_completed", "labels_agree_across_repeats")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
