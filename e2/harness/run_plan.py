"""Run one registered repository plan (e2/plans/<slug>.json) under the E2 harness.

Usage: python e2/harness/run_plan.py e2/plans/<slug>.json <results_dir> [--prep-only]
All third-party code runs only inside offline containers (repromut.e2.container).

Plan keys (beyond argv/cwd_rel/adapter/cases):
  images/packages: explicit, or "from_build" -> build/<slug>/images.json + packages_<key>.txt
  setup.add_files {repo_rel: artifact}, setup.extract_zips [repo_rel zip]  -> augmented source tree used
        by EVERY run, baseline included (build-stage data per A1 / README setup steps)
  artifacts {name: {from|from_artifact, method: copy|perturb_rows|zip_member_perturb, ...}} (host, data only)
  prep [{name, argv, cwd_rel, pre_files, capture {repo_rel: artifact}}]  -> the repository's own code,
        run in the offline container, produces stale artifacts BEFORE outcome runs
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

from repromut.e2 import container as C
from repromut.e2 import outputs as O
from repromut.e2.cases import CaseSpec, materialise, perturb_rows
from repromut.e2.study import RepoPlan, run_repo

WORK = Path.home() / "repromut-e2-work"          # the only directory the VM can see


def tracked_files(tree: Path) -> list[str]:
    return sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file() and not p.is_symlink())


def safe_extract(zpath: Path, dest: Path) -> None:
    """Data-only extraction: regular files only, no absolute/.. paths, skip __MACOSX metadata."""
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith("__MACOSX/") or info.is_dir() or name.startswith("/") or ".." in Path(name).parts:
                continue
            if (info.external_attr >> 16) & 0o170000 == 0o120000:     # symlink entry
                continue
            out = dest / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(z.read(info))


def build_tree(plan: dict, snapshot: Path, art: Path, slug: str) -> Path:
    setup = plan.get("setup")
    if not setup:
        return snapshot
    tree = WORK / "trees" / slug
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(snapshot, tree, symlinks=True)
    for rel, a in setup.get("add_files", {}).items():
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(art / a, tree / rel)
    for rel in setup.get("extract_zips", []):
        safe_extract(tree / rel, (tree / rel).parent)
    return tree


def prepare_artifacts(plan: dict, tree: Path, art: Path) -> None:
    """Deterministic host-side artifacts (data only): copies and first-90%-of-rows perturbations."""
    art.mkdir(parents=True, exist_ok=True)
    for name, spec in plan.get("artifacts", {}).items():
        src = (art / spec["from_artifact"]) if "from_artifact" in spec else (tree / spec.get("from", "."))
        m = spec["method"]
        data = src.read_bytes() if m not in ("copy_tree", "empty") else b""
        if m == "perturb_rows":
            data = perturb_rows(data, spec.get("fraction", 0.9), spec.get("header", True))
        elif m == "zip_member_perturb":
            buf = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
                for info in zin.infolist():
                    payload = zin.read(info)
                    if info.filename == spec["member"]:
                        payload = perturb_rows(payload, spec.get("fraction", 0.9), True)
                    zout.writestr(info, payload)
            data = buf.getvalue()
        elif m == "copy_tree":
            dst = art / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, symlinks=True)
            continue
        elif m == "empty":
            data = b""
        elif m != "copy":
            raise ValueError(m)
        (art / name).write_bytes(data)


def run_prep(plan: dict, tree: Path, art: Path, images: dict, slug: str) -> None:
    for p in plan.get("prep", []):
        root = WORK / "runs" / f"prep-{slug}-{p['name']}"
        shutil.rmtree(root, ignore_errors=True)
        case = CaseSpec("prep", "M-CACHE", "positive", pre_files=p.get("pre_files", {}))
        cwd, argv, repo = materialise(case, tree, root, art, p["argv"], p.get("cwd_rel", ""))
        for rel in p.get("remove", []):          # e.g. a committed cache that would mask regeneration
            (repo / rel).unlink(missing_ok=True)
        caps = list(p["capture"])
        r = C.run(C.ContainerSpec(images[p.get("image_key", "base")], root, cwd, argv, {}, plan.get("timeout_s", 600)),
                  [f"repo/{c}" for c in caps])
        if r.status != "ok":
            raise RuntimeError(f"prep {p['name']} failed ({r.status}): {r.stderr[-1500:]}")
        for c in caps:
            if f"repo/{c}" not in r.files:
                raise RuntimeError(f"prep {p['name']}: {c} not produced")
            (art / p["capture"][c]).write_bytes(r.files[f"repo/{c}"])
        shutil.rmtree(root, ignore_errors=True)


def resolve_images(plan: dict, slug: str) -> tuple[dict, dict]:
    if plan.get("images") == "from_build":
        b = WORK / "build" / slug
        images = {k: v for k, v in json.loads((b / "images.json").read_text()).items() if v}
        packages = {k: (b / f"packages_{k}.txt").read_text() for k in images}
        return images, packages
    return plan["images"], {k: Path(v).expanduser().read_text() for k, v in plan["packages"].items()}


def main(plan_path: str, results_dir: str, prep_only: bool = False) -> None:
    plan = json.loads(Path(plan_path).read_text())
    snapshot = Path(plan["source_tree"]).expanduser()
    slug = plan["repo"].replace("/", "__")
    art = WORK / "artifacts" / slug
    art.mkdir(parents=True, exist_ok=True)
    images, packages = resolve_images(plan, slug)
    tree = build_tree(plan, snapshot, art, slug)
    prepare_artifacts(plan, tree, art)
    run_prep(plan, tree, art, images, slug)
    if prep_only:
        print("prep done:", sorted(p.name for p in art.iterdir()))
        return
    cases = [CaseSpec.from_dict(c) for c in plan["cases"] if c.get("image_key", "base") in images]
    skipped = [c["case_id"] for c in plan["cases"] if c.get("image_key", "base") not in images]
    if skipped:
        print("not constructible (image build failed):", skipped, flush=True)
    rp = RepoPlan(repo=plan["repo"], source_tree=tree, argv=plan["argv"],
                  adapter=O.AdapterSpec.from_dict(plan["adapter"]), tracked=tracked_files(tree),
                  images=images, packages=packages, cases=cases, artifacts=art,
                  cwd_rel=plan.get("cwd_rel", ""), timeout_s=plan.get("timeout_s", 600))
    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    recs = run_repo(rp, out / f"{slug}.jsonl", WORK / "runs")
    for r in recs:
        print(r["case_id"], r["label"], r["flags"], r["d_reason"], flush=True)


if __name__ == "__main__":
    os.environ.setdefault("DOCKER_CONTEXT", "colima-repromut-e2")
    main(sys.argv[1], sys.argv[2], "--prep-only" in sys.argv)
