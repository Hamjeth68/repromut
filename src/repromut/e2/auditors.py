"""Auditors (protocol section 7). They never see oracle labels.

S1: declared-configuration manifest.  S2: S1 + resolved packages, env map, cwd, untracked files.
D: dynamic re-execution fingerprints.  C1 = S1 or D, C2 = S2 or D.
Static manifests read the work copy as text/bytes only; nothing is imported or executed.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

CONFIG_SUFFIXES = (".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf")
DEP_NAMES = ("requirements", "setup.py", "setup.cfg", "pyproject.toml", "environment.yml",
             "environment.yaml", "Pipfile", "uv.lock", "poetry.lock")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ast_hash(src: bytes) -> str:
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")     # third-party sources may contain invalid escapes etc.
            return _sha(ast.dump(ast.parse(src)).encode())
    except (SyntaxError, ValueError):
        return "raw:" + _sha(src)


def _is_dep_file(rel: str) -> bool:
    name = Path(rel).name
    return any(name.startswith(d) or name == d for d in DEP_NAMES)


def s1_manifest(work: Path, tracked: list[str], argv: list[str]) -> dict:
    """Hashes of tracked config/dependency files, AST hashes of tracked .py, and the invocation."""
    m: dict[str, str] = {"__argv__": _sha(json.dumps(argv).encode())}
    for rel in sorted(tracked):
        p = Path(work) / rel
        if p.is_symlink() or not p.is_file():
            m[rel] = "<absent>"
            continue
        data = p.read_bytes()
        if rel.endswith(".py"):
            m[rel] = _ast_hash(data)
        elif rel.endswith(CONFIG_SUFFIXES) or _is_dep_file(rel):
            m[rel] = _sha(data)
    return m


def s2_manifest(work: Path, tracked: list[str], argv: list[str], *, packages: str,
                env: dict[str, str], cwd_abs: str, max_untracked_bytes: int = 50 * 1024**2) -> dict:
    """S1 plus resolved package list, full env map, absolute cwd and untracked-file content hashes."""
    m = s1_manifest(work, tracked, argv)
    m["__packages__"] = _sha(packages.encode())
    m["__env__"] = _sha(json.dumps(env, sort_keys=True).encode())
    m["__cwd__"] = cwd_abs
    tracked_set = set(tracked)
    root = Path(work)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if rel in tracked_set or p.is_dir():
            continue
        if p.is_symlink():
            m["untracked:" + rel] = "link:" + _sha(str(p.readlink()).encode())
        elif p.is_file():
            size = p.stat().st_size
            m["untracked:" + rel] = _sha(p.read_bytes()) if size <= max_untracked_bytes else f"size:{size}"
    return m


def static_flag(baseline_manifest: dict, case_manifest: dict) -> bool:
    return baseline_manifest != case_manifest


@dataclass
class DynamicResult:
    flag: bool
    reason: str               # "numeric_change" | "execution_failure" | "none"
    fingerprints: list[str]


def dynamic_flag(baseline_fp: str, run_fps: list[str | None], k: int = 2) -> DynamicResult:
    """Flag if any of the first k runs differs from the baseline fingerprint, or they differ from each other.

    `None` marks a crashed/timed-out run: it flags with reason `execution_failure`, kept apart from
    numeric-change flags. Process success alone is never treated as reproduced.
    """
    fps = run_fps[:k]
    if any(f is None for f in fps):
        return DynamicResult(True, "execution_failure", [f or "" for f in fps])
    if any(f != baseline_fp for f in fps) or len(set(fps)) > 1:
        return DynamicResult(True, "numeric_change", list(fps))
    return DynamicResult(False, "none", list(fps))


def combine(static: bool, dynamic: DynamicResult) -> tuple[bool, str]:
    if static and dynamic.flag:
        return True, "both"
    if static:
        return True, "static"
    if dynamic.flag:
        return True, "dynamic:" + dynamic.reason
    return False, "none"
