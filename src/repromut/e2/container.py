"""Run one case inside an isolated, offline container (THREAT-MODEL.md, protocol section 12).

The docker invocation is built by a pure function so the isolation flags are unit-tested.
Outputs are read back from the bind-mounted work copy as bytes only: symlinks and paths that
resolve outside the work copy are refused, so a run cannot make the host read other files.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

MAX_STREAM = 5 * 1024 * 1024
MIN_FREE_BYTES = 8 * 1024**3
FIXED_ENV = {"PYTHONHASHSEED": "0", "MPLBACKEND": "Agg", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}

# Isolation flags required for every outcome-producing run. Tests assert these are present.
ISOLATION_FLAGS = (
    "--network", "none",
    "--read-only",
    "--tmpfs", "/tmp:rw,size=512m",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--pids-limit", "256",
    "--cpus", "2",
    "--memory", "3g",
    "--memory-swap", "3g",
    "--user", "10001:10001",
)


@dataclass
class ContainerSpec:
    image: str                       # must be digest-pinned: name@sha256:...
    work_host: Path                  # fresh per-run work copy (bind-mounted read-write at /work)
    cwd: str                         # container working directory, under /work
    argv: list[str]                  # the declared invocation
    env: dict[str, str] = field(default_factory=dict)
    timeout_s: float = 600.0


@dataclass
class RunResult:
    status: str                      # ok | crash | timeout | infra_failure
    exit_code: int | None
    stdout: str
    stderr: str
    seconds: float
    files: dict[str, bytes] = field(default_factory=dict)
    note: str = ""


def build_docker_argv(spec: ContainerSpec, name: str, docker: str = "docker") -> list[str]:
    if "@sha256:" not in spec.image:
        raise ValueError("image must be pinned by digest")
    if not (spec.cwd == "/work" or spec.cwd.startswith("/work/")):
        raise ValueError("cwd must be inside /work")
    argv = [docker, "run", "--rm", "--name", name, *ISOLATION_FLAGS,
            "-v", f"{Path(spec.work_host).resolve()}:/work:rw", "-w", spec.cwd]
    for k, v in {**spec.env, **FIXED_ENV}.items():
        if "=" in k or not k:
            raise ValueError(f"bad env name {k!r}")
        argv += ["-e", f"{k}={v}"]
    return argv + [spec.image, *spec.argv]


def read_outputs(work_host: Path, declared: list[str], max_bytes: int = MAX_STREAM) -> dict[str, bytes]:
    """Read declared output files as bytes. Refuses symlinks and anything resolving outside work_host."""
    root = Path(work_host).resolve()
    out: dict[str, bytes] = {}
    for rel in declared:
        parts = Path(rel).parts
        if Path(rel).is_absolute() or ".." in parts:
            continue
        cur, linked = root, False
        for part in parts:                    # refuse if any component is a symlink
            cur = cur / part
            if cur.is_symlink():
                linked = True
                break
        if linked:
            continue
        try:
            rp = cur.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        if root not in rp.parents or not rp.is_file():
            continue
        with open(rp, "rb") as fh:
            out[rel] = fh.read(max_bytes)
    return out


def free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def run(spec: ContainerSpec, declared_outputs: list[str], docker: str = "docker",
        runner=subprocess.run) -> RunResult:
    """Run the container with an external wall-clock limit enforced by `docker kill`."""
    if free_bytes(spec.work_host) < MIN_FREE_BYTES:
        raise RuntimeError("free disk below 8 GB; aborting (THREAT-MODEL stop condition)")
    name = f"rmx-{uuid.uuid4().hex[:12]}"
    argv = build_docker_argv(spec, name, docker)
    t0 = time.perf_counter()
    try:
        p = runner(argv, capture_output=True, timeout=spec.timeout_s)
    except subprocess.TimeoutExpired:
        runner([docker, "kill", name], capture_output=True, timeout=60)
        return RunResult("timeout", None, "", "", time.perf_counter() - t0)
    except OSError as e:
        return RunResult("infra_failure", None, "", "", time.perf_counter() - t0, note=str(e)[:300])
    dt = time.perf_counter() - t0
    so = (p.stdout or b"")[:MAX_STREAM].decode("utf-8", "replace")
    se = (p.stderr or b"")[:MAX_STREAM].decode("utf-8", "replace")
    # Exit 125 = docker daemon could not create/start the container: infrastructure, not the experiment.
    if p.returncode == 125:
        return RunResult("infra_failure", 125, so, se, dt, note=se[-300:])
    files = read_outputs(spec.work_host, declared_outputs)
    return RunResult("ok" if p.returncode == 0 else "crash", p.returncode, so, se, dt, files)


def prepare_work_copy(source_tree: Path, dest: Path) -> Path:
    """Fresh copy of the commit-pinned source tree. Symlinks are copied as links, never followed."""
    if dest.exists():
        raise FileExistsError(dest)
    shutil.copytree(source_tree, dest, symlinks=True)
    os.chmod(dest, 0o777)  # writable by the unprivileged container user (10001)
    for d, dirs, files in os.walk(dest):
        for x in dirs + files:
            p = Path(d) / x
            if not p.is_symlink():
                os.chmod(p, 0o777 if p.is_dir() else 0o666)
    return dest
