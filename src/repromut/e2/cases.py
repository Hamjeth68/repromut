"""Case definitions and work-copy setup for hidden-state mutations and controls (protocol section 4).

Every case keeps the declared invocation and tracked files unchanged; only hidden state differs:
environment variables, pre-placed artifacts, the working directory, or the dependency image.
`intent` records the design intent only. The oracle decides the label.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

FAMILIES = {"M-ENV", "M-CACHE", "M-DEP", "M-PATH", "C-ENV", "C-CACHE", "C-PATH", "C-DEP", "BASELINE"}
REPO_DIR = "repo"
SIBLING_DIR = "sibling"
CPATH_DIR = "relocated/deeper/repo"
UNUSED_CACHE = ".repromut_unused_cache.pkl"


@dataclass
class CaseSpec:
    case_id: str
    family: str
    intent: str                                            # positive | control | baseline
    env: dict[str, str] = field(default_factory=dict)
    pre_files: dict[str, str] = field(default_factory=dict)  # repo-relative path -> artifact-store file
    shadow_files: dict[str, str] = field(default_factory=dict)  # sibling-relative path -> artifact-store file
    image_key: str = "base"                                # base | dep_alt | dep_patch
    note: str = ""

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"unknown family {self.family}")
        if self.intent not in {"positive", "control", "baseline"}:
            raise ValueError(f"unknown intent {self.intent}")

    @classmethod
    def from_dict(cls, d: dict) -> "CaseSpec":
        return cls(**{k: d[k] for k in ("case_id", "family", "intent") },
                   env=dict(d.get("env", {})), pre_files=dict(d.get("pre_files", {})),
                   shadow_files=dict(d.get("shadow_files", {})), image_key=d.get("image_key", "base"),
                   note=d.get("note", ""))


BASELINE = CaseSpec("baseline", "BASELINE", "baseline")


def standard_controls(dep_patch_available: bool) -> list[CaseSpec]:
    cs = [CaseSpec("C-ENV", "C-ENV", "control", env={"REPROMUT_UNUSED_VAR": "1"}),
          CaseSpec("C-CACHE", "C-CACHE", "control"),
          CaseSpec("C-PATH", "C-PATH", "control")]
    if dep_patch_available:
        cs.append(CaseSpec("C-DEP", "C-DEP", "control", image_key="dep_patch"))
    return cs


def perturb_rows(data: bytes, fraction: float = 0.9, header: bool = True) -> bytes:
    """Deterministic input perturbation: keep the header and the first `fraction` of data rows."""
    lines = data.splitlines(keepends=True)
    head, body = (lines[:1], lines[1:]) if header else ([], lines)
    keep = max(1, int(len(body) * fraction)) if body else 0
    return b"".join(head + body[:keep])


def _place(src: Path, dst: Path) -> None:
    """Copy an artifact file or directory tree (symlinks copied as links, never followed)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, symlinks=True)
    else:
        shutil.copyfile(src, dst)


def _safe_rel(rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe relative path {rel!r}")
    return p


def materialise(case: CaseSpec, source_tree: Path, run_root: Path, artifacts: Path,
                argv: list[str], cwd_rel: str = "") -> tuple[str, list[str], Path]:
    """Create the work copy for one run under run_root; return (container cwd, argv, host repo dir).

    run_root is mounted at /work. The repository lives at /work/repo except for C-PATH.
    """
    from repromut.e2.container import prepare_work_copy

    run_root.mkdir(parents=True, exist_ok=False)
    repo_rel = CPATH_DIR if case.family == "C-PATH" else REPO_DIR
    repo_host = run_root / repo_rel
    repo_host.parent.mkdir(parents=True, exist_ok=True)
    prepare_work_copy(source_tree, repo_host)
    for rel, art in case.pre_files.items():
        _place(artifacts / _safe_rel(art), repo_host / _safe_rel(rel))
    if case.family == "C-CACHE":
        (repo_host / UNUSED_CACHE).write_bytes(b"repromut unused control artifact\n")
    cwd = f"/work/{repo_rel}" + (f"/{cwd_rel}" if cwd_rel else "")
    if case.family == "M-PATH":
        sib = run_root / SIBLING_DIR
        sib.mkdir()
        for rel, art in case.shadow_files.items():
            _place(artifacts / _safe_rel(art), sib / _safe_rel(rel))
        argv = absolutise_entry(argv, f"/work/{repo_rel}" + (f"/{cwd_rel}" if cwd_rel else ""))
        # The sibling cwd mirrors the registered cwd depth, so relative paths such as ../../data
        # resolve inside the sibling tree (shadow paths are relative to the sibling root).
        cwd = f"/work/{SIBLING_DIR}" + (f"/{cwd_rel}" if cwd_rel else "")
        (sib / cwd_rel).mkdir(parents=True, exist_ok=True)
    run_root.chmod(0o777)
    for p in run_root.rglob("*"):          # writable by the unprivileged container user (10001)
        if not p.is_symlink():
            p.chmod(0o777 if p.is_dir() else 0o666)
    return cwd, argv, repo_host


def absolutise_entry(argv: list[str], base: str) -> list[str]:
    """Make the declared entry independent of the working directory.

    `python script.py ...` -> `python /abs/script.py ...`. An installed console script
    (argv[0] not 'python') is location-independent and is kept unchanged. `python -m` of a
    module that is only importable from the cwd cannot be relocated, so M-PATH is not applicable.
    """
    if len(argv) >= 2 and argv[0].startswith("python") and argv[1].endswith(".py") and not argv[1].startswith("/"):
        return [argv[0], f"{base}/{argv[1]}", *argv[2:]]
    if argv and not argv[0].startswith("python"):
        return list(argv)
    raise ValueError("M-PATH needs a script-path or installed console-script entry point")
