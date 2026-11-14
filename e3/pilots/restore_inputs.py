"""Restore the E2 inputs that the E3 pilots read, after ~/repromut-e2-work was lost.

Rebuilds only what pilots T and N need, for their four repositories:
  1. the source snapshot at the commit recorded in e2/REPOSITORY-MANIFEST.json (GitHub tarball,
     extracted with tarfile's 'data' filter, as E2's prescreen did);
  2. the 'base' Docker image, from E2's committed build files in e2/env/builds/ (same Dockerfile,
     same hash-locked lock file or uv.lock; nothing is re-resolved);
  3. a check that the rebuilt image's installed packages equal E2's committed package list;
  4. setup data named in the plan (Student-Performance's student.zip), checked against the SHA-256
     in e2/env/datasets.json.

Rebuilt images get new IDs. Equivalence is shown by the package check, and every result is written
to e3/pilots/results/restore.json for the pilot report. Builds use the network, as E2's build stage
did; no third-party code runs on the host.

Usage (Mac, repository root, repromut-e2 VM running):
    python e3/pilots/restore_inputs.py --dry-run
    python e3/pilots/restore_inputs.py
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilotlib as PL  # noqa: E402

ROOT = PL.REPO_ROOT
BUILD_SRC_DIR = {"fmind/mlops-python-package": "fmind"}   # committed under a short name; others use the slug
CONTEXT = "colima-repromut-e2"


def pilot_repos() -> list[str]:
    manifest = json.loads((ROOT / "e2" / "REPOSITORY-MANIFEST.json").read_text())
    t = PL.select_pilot_t(manifest, ROOT / "e2" / "results" / "full")
    n = json.loads((ROOT / "e3" / "pilots" / "pilot_n_config.json").read_text())["repo"]
    return t + [n]


def commit_of(repo: str) -> str:
    m = json.loads((ROOT / "e2" / "REPOSITORY-MANIFEST.json").read_text())
    return next(r["commit"] for r in m["repositories"] if r["repo"] == repo)


def build_src(repo: str) -> Path:
    return ROOT / "e2" / "env" / "builds" / BUILD_SRC_DIR.get(repo, PL.slug(repo))


# ----------------------------------------------------------------------------- pure helpers (tested)
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_packages(expected: str, actual: str) -> tuple[bool, list[str]]:
    """Order-insensitive comparison of pip/uv freeze output; returns (equal, unified diff)."""
    def norm(t: str) -> list[str]:
        return sorted({l.strip() for l in t.splitlines() if l.strip() and not l.lstrip().startswith("#")},
                      key=str.lower)
    e, a = norm(expected), norm(actual)
    return e == a, list(difflib.unified_diff(e, a, "e2_committed", "rebuilt", lineterm="", n=0))


def extract_tarball(blob: bytes, dest: Path) -> int:
    """Extract with the 'data' filter (no absolute paths, no escapes, no device files).
    Unsafe members are skipped, never extracted. Returns the number skipped."""
    skipped = 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf.getmembers():
            try:
                tf.extract(m, dest, filter="data")
            except (tarfile.FilterError, OSError):
                skipped += 1
    return skipped


# ----------------------------------------------------------------------------- side effects
def docker(*args: str, check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "--context", CONTEXT, *args], capture_output=True, text=True,
                          check=check, **kw)


def mount_works(work: Path) -> bool:
    """The VM must see ~/repromut-e2-work (it was missing when the VM last started)."""
    probe = work / ".mount_probe"
    probe.write_text("ok\n")
    r = docker("run", "--rm", "--network", "none", "-v", f"{work}:/w:ro",
               "python@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d",
               "cat", "/w/.mount_probe", check=False)
    probe.unlink(missing_ok=True)
    return r.returncode == 0 and r.stdout.strip() == "ok"


def fetch(url: str, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "repromut-e3-restore",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def restore_snapshot(repo: str, plan: dict) -> dict:
    target = Path(plan["source_tree"]).expanduser()
    if target.exists():
        return {"snapshot": str(target), "status": "already present"}
    sha = commit_of(repo)
    blob = fetch(f"https://api.github.com/repos/{repo}/tarball/{sha}")
    skipped = extract_tarball(blob, target.parent)
    if not target.exists():
        raise RuntimeError(f"{repo}: extracted archive does not contain {target.name}")
    return {"snapshot": str(target), "commit": sha, "archive_members_skipped": skipped,
            "status": "downloaded"}


def restore_image(repo: str, plan: dict, work: Path, allow_mismatch: bool) -> dict:
    s = PL.slug(repo)
    src = build_src(repo)
    b = work / "build" / s
    shutil.rmtree(b, ignore_errors=True)
    b.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copyfile(f, b / f.name)
    mode = plan["build"]["mode"]
    if mode == "uvlock":
        shutil.copytree(Path(plan["source_tree"]).expanduser(), b / "src_snapshot", symlinks=True)
        args = ["--build-arg", "SKLEARN_OVERRIDE="]
    elif mode in ("requirements", "imports"):
        args = ["--build-arg", "LOCK=lock.txt"]
    else:
        raise ValueError(mode)
    tag = f"repromut-e2/{s.lower()}:base"
    r = docker("build", "-q", *args, "-t", tag, str(b), check=False)
    (b / "build_base.log").write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"{repo}: image build failed; see {b / 'build_base.log'}")
    iid = r.stdout.strip().splitlines()[-1]
    pk = docker("run", "--rm", "--network", "none", iid, "cat", "/opt/packages.txt").stdout
    (b / "packages_base.txt").write_text(pk)
    equal, diff = compare_packages((src / "packages_base.txt").read_text(), pk)
    e2_ids = json.loads((src / "images.json").read_text()) if (src / "images.json").exists() else {}
    rec = {"image_tag": tag, "image_id": iid, "e2_image_id": e2_ids.get("base"),
           "packages_match_e2": equal, "packages_diff": diff[:200]}
    if plan["build"].get("nltk"):
        rec["nltk_sha256"] = docker("run", "--rm", "--network", "none", iid, "cat",
                                    "/opt/nltk_sha256.txt", check=False).stdout.splitlines()
    if not equal and not allow_mismatch:
        raise RuntimeError(f"{repo}: rebuilt packages differ from E2's committed list:\n" + "\n".join(diff[:40]))
    (b / "images.json").write_text(json.dumps({"base": iid}, indent=1))
    return rec


def restore_setup_data(repo: str, plan: dict, work: Path) -> list[dict]:
    datasets = json.loads((ROOT / "e2" / "env" / "datasets.json").read_text())
    out = []
    for name in (plan.get("setup") or {}).get("add_files", {}).values():
        if name not in datasets:
            raise RuntimeError(f"{repo}: setup file {name} has no source in e2/env/datasets.json")
        spec = datasets[name]
        dst = work / "artifacts" / PL.slug(repo) / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not (dst.exists() and sha256_file(dst) == spec["sha256"]):
            dst.write_bytes(fetch(spec["url"]))
        got = sha256_file(dst)
        if got != spec["sha256"]:
            dst.unlink()
            raise RuntimeError(f"{repo}: {name} SHA-256 {got} does not match the recorded {spec['sha256']}")
        out.append({"file": name, "url": spec["url"], "sha256": got, "verified": True})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="list what would be restored; touch nothing")
    ap.add_argument("--allow-package-mismatch", action="store_true",
                    help="record a package-list difference instead of stopping (it goes in the pilot report)")
    args = ap.parse_args(argv)
    work = PL.RP.WORK
    repos = pilot_repos()
    plans = {r: json.loads((ROOT / "e2" / "plans" / f"{PL.slug(r)}.json").read_text()) for r in repos}
    print("Repositories:", repos)
    for r in repos:
        p = plans[r]
        print(f"  {r}: commit {commit_of(r)[:7]}, build mode {p['build']['mode']}, python {p['build']['python']}, "
              f"build files {build_src(r).relative_to(ROOT)}, setup data {list((p.get('setup') or {}).get('add_files', {}).values())}")
    if not hasattr(tarfile, "data_filter"):
        print("NOT READY: this Python has no tarfile 'data' filter; use Python 3.12+ (or 3.10.12+/3.11.4+).")
        return 2
    if args.dry_run:
        return 0
    if not work.exists():
        print(f"NOT READY: {work} does not exist")
        return 2
    if not mount_works(work):
        print(f"NOT READY: the repromut-e2 VM cannot see {work}. Restart it so the mount is set up:\n"
              "  colima stop -p repromut-e2 && colima start -p repromut-e2")
        return 2
    record = {"reason": "~/repromut-e2-work was lost; pilot inputs rebuilt from committed E2 records",
              "repositories": {}}
    for r in repos:
        print(f"== {r}", flush=True)
        rec = {"snapshot": restore_snapshot(r, plans[r])}
        print("   snapshot:", rec["snapshot"]["status"], flush=True)
        rec["image"] = restore_image(r, plans[r], work, args.allow_package_mismatch)
        print("   image:", rec["image"]["image_id"][:19], "packages match E2:", rec["image"]["packages_match_e2"], flush=True)
        rec["setup_data"] = restore_setup_data(r, plans[r], work)
        record["repositories"][r] = rec
    out = ROOT / "e3" / "pilots" / "results" / "restore.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2))
    print(f"Restored. Record: {out.relative_to(ROOT)}. Next: the pilots' --dry-run.")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("DOCKER_CONTEXT", CONTEXT)
    sys.exit(main())
