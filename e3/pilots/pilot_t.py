"""E3 pilot T (thread-count family), E3 protocol draft Appendix A.1.

Usage (on the Mac, from the repository root, with the repromut-e2 Colima VM running):
    python e3/pilots/pilot_t.py --dry-run     # selection + prerequisite checks, runs nothing
    python e3/pilots/pilot_t.py               # diagnostic + 5 baseline, 3 oracle, 3 D runs per repository

Outputs: e3/pilots/results/T/<slug>.jsonl, <slug>.diagnostic.json, summary.json
Uses E2's images and setup artifacts in ~/repromut-e2-work (read only); pilot work goes to
~/repromut-e2-work/e3-pilots/T. E2's code, plans and results are not modified.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilotlib as PL  # noqa: E402

RULE = ("first 3 E2-eligible repositories in E2 review order (P1, P2, P3 by seeded order) "
        "whose registered E2 baseline was stable")


def check(repo: str, root: Path, work: Path) -> tuple[dict | None, list[str]]:
    s = PL.slug(repo)
    problems: list[str] = []
    plan = json.loads((root / "e2" / "plans" / f"{s}.json").read_text())
    try:
        images, packages = PL.RP.resolve_images(plan, s)
    except (FileNotFoundError, KeyError) as e:
        return None, [f"{repo}: E2 image record missing ({e}); E2 build area must still exist"]
    if "base" not in images:
        problems.append(f"{repo}: no base image in E2 build record")
    if not Path(plan["source_tree"]).expanduser().exists():
        problems.append(f"{repo}: source snapshot missing: {plan['source_tree']}")
    for a in (plan.get("setup") or {}).get("add_files", {}).values():
        if not (work / "artifacts" / s / a).exists():
            problems.append(f"{repo}: setup artifact missing: {work / 'artifacts' / s / a}")
    return {"plan": plan, "images": images, "packages": packages}, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="show selection and check prerequisites; run nothing")
    args = ap.parse_args(argv)
    root, work = PL.REPO_ROOT, PL.RP.WORK
    manifest = json.loads((root / "e2" / "REPOSITORY-MANIFEST.json").read_text())
    repos = PL.select_pilot_t(manifest, root / "e2" / "results" / "full")
    print(f"Selection rule: {RULE}\nSelected: {repos}")
    checked, problems = [], []
    for repo in repos:
        info, probs = check(repo, root, work)
        problems += probs
        if info:
            checked.append((repo, info))
    if len(repos) != 3:
        problems.append(f"expected 3 repositories, found {len(repos)}")
    if problems:
        print("NOT READY:\n  " + "\n  ".join(problems))
        return 2
    print("Prerequisites OK.")
    if args.dry_run:
        return 0
    os.environ.setdefault("DOCKER_CONTEXT", "colima-repromut-e2")
    pilot_work = work / "e3-pilots" / "T"
    out_dir = root / "e3" / "pilots" / "results" / "T"
    results = []
    for repo, info in checked:
        st = PL.stage(info["plan"], pilot_work, work / "artifacts" / PL.slug(repo),
                      info["images"], info["packages"], with_artifacts=False)
        r = PL.run_pilot_t_repo(st, out_dir, pilot_work)
        print(json.dumps(r), flush=True)
        results.append(r)
    summary = {"pilot": "T", "rule": RULE, "repositories": results, **PL.adopt_t(results)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("adopt", "n_setting_took_effect", "all_labels_decidable")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
