"""External validation harness: audit real, third-party Python ML scripts.

Unlike the synthetic benchmark, ground truth here is *not* declared in advance.
Operators declare an *intent* (result-changing or semantics-preserving); the
execution oracle decides what actually happened. Disagreements between intent
and effect are reported, not hidden (the "equivalent mutant" problem).

Reported result of a script = the numbers it prints to stdout, excluding lines
that look like timing output (pre-registered heuristic, see TIMING_RE).
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

NUM_RE = re.compile(r"(?<![\w.])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?(?![\w])")
TIMING_RE = re.compile(r"(?i)(time|sec\b|secs|second|elapsed|duration|took|\d\s*s\b|\bms\b|\d+s\b)")
NETWORK_RE = re.compile(r"\bfetch_\w+\(|urlopen|urlretrieve|requests\.|pooch|load_sample_image|"
                        r"fetch_openml|datasets\.fetch")
SEED_KWARGS = {"random_state", "seed", "random_seed", "rng_seed"}
SEED_FUNCS = {"seed", "manual_seed"}               # np.random.seed(x), random.seed(x), torch.manual_seed(x)
RNG_CTORS = {"RandomState", "default_rng", "Generator", "PCG64", "MT19937"}

ORACLE_RTOL = 1e-6
ORACLE_ATOL = 1e-9
DECIMALS = 8


# --------------------------------------------------------------------------
# Running scripts
# --------------------------------------------------------------------------

@dataclass
class RunOutput:
    ok: bool
    numbers: list[float]
    seconds: float
    error: str = ""


def extract_numbers(stdout: str) -> list[float]:
    out: list[float] = []
    for line in stdout.splitlines():
        if TIMING_RE.search(line):
            continue
        for tok in NUM_RE.findall(line):
            try:
                out.append(float(tok))
            except ValueError:
                pass
    return out


def run_script(source: str, timeout: float = 60.0, env_extra: dict | None = None,
               workdir_name: str = "w") -> RunOutput:
    """Run `source` as a fresh process in an isolated temporary directory."""
    with tempfile.TemporaryDirectory(prefix="rmx-") as tmp:
        wd = Path(tmp) / workdir_name
        wd.mkdir(parents=True)
        (wd / "script.py").write_text(source)
        env = {k: v for k, v in os.environ.items()
               if k in ("PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH", "VIRTUAL_ENV", "TMPDIR")}
        env.update({"MPLBACKEND": "Agg", "PYTHONWARNINGS": "ignore"})
        if env_extra:
            env.update(env_extra)
        t = time.perf_counter()
        try:
            p = subprocess.run([sys.executable, "script.py"], cwd=wd, env=env,
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return RunOutput(False, [], time.perf_counter() - t, "timeout")
        dt = time.perf_counter() - t
        if p.returncode != 0:
            return RunOutput(False, [], dt, (p.stderr or "")[-300:])
        return RunOutput(True, extract_numbers(p.stdout), dt)


def fingerprint_numbers(nums: list[float]) -> str:
    rounded = [0.0 if round(x, DECIMALS) == 0 else round(x, DECIMALS) for x in nums]
    return hashlib.sha256(json.dumps(rounded).encode()).hexdigest()


def numbers_close(a: list[float], b: list[float]) -> bool:
    if len(a) != len(b):
        return False
    return bool(np.allclose(np.array(a, float), np.array(b, float),
                            rtol=ORACLE_RTOL, atol=ORACLE_ATOL, equal_nan=True))


# --------------------------------------------------------------------------
# Static analysis used by auditors
# --------------------------------------------------------------------------

def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def seed_literals(source: str) -> list:
    """Ordered list of literal seed values found in the source."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            for kw in node.keywords:
                if kw.arg in SEED_KWARGS:
                    out.append(kw.value.value if isinstance(kw.value, ast.Constant) else "<expr>")
            if name in SEED_FUNCS | RNG_CTORS:
                if node.args and isinstance(node.args[0], ast.Constant):
                    out.append(node.args[0].value)
                elif name in SEED_FUNCS or not node.args:
                    out.append("<unseeded>" if not node.args else "<expr>")
    return out


def semantic_hash(source: str) -> str:
    """Hash of the AST: insensitive to comments and formatting."""
    return hashlib.sha256(ast.dump(ast.parse(source), include_attributes=False).encode()).hexdigest()


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

@dataclass
class Operator:
    id: str
    intent: str                      # "positive" or "control"
    kind: str                        # "source" or "environment"
    description: str
    transform: Callable[[str], str | None] | None = None   # source -> mutant source (None = n/a)
    env: dict | None = None
    workdir_name: str = "w"


class _SeedTx(ast.NodeTransformer):
    def __init__(self, mode: str):
        self.mode, self.sites = mode, 0

    def _new(self, v):
        return ast.Constant(None) if self.mode == "remove" else ast.Constant(v + 1)

    def visit_Call(self, node):
        self.generic_visit(node)
        for kw in node.keywords:
            if kw.arg in SEED_KWARGS and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, int) and not isinstance(kw.value.value, bool):
                kw.value = self._new(kw.value.value)
                self.sites += 1
        name = _call_name(node)
        if name in SEED_FUNCS | RNG_CTORS and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, int):
            if self.mode == "remove":
                node.args = node.args[1:] if name in RNG_CTORS else [ast.Constant(None)]
            else:
                node.args[0] = ast.Constant(node.args[0].value + 1)
            self.sites += 1
        return node


def _apply(tx: ast.NodeTransformer, source: str) -> str | None:
    tree = tx.visit(ast.parse(source))
    if getattr(tx, "sites", 0) == 0:
        return None
    return ast.unparse(ast.fix_missing_locations(tree))


def seed_removed(src: str) -> str | None:
    return _apply(_SeedTx("remove"), src)


def seed_changed(src: str) -> str | None:
    return _apply(_SeedTx("change"), src)


class _KwTx(ast.NodeTransformer):
    def __init__(self, calls: set | None, kw: str, fn: Callable, add_default=None):
        self.calls, self.kw, self.fn, self.add_default, self.sites = calls, kw, fn, add_default, 0

    def visit_Call(self, node):
        self.generic_visit(node)
        if self.calls is not None and _call_name(node) not in self.calls:
            return node
        for k in node.keywords:
            if k.arg == self.kw and isinstance(k.value, ast.Constant) \
                    and isinstance(k.value.value, (int, float)) and not isinstance(k.value.value, bool):
                new = self.fn(k.value.value)
                if new != k.value.value:
                    k.value = ast.Constant(new)
                    self.sites += 1
                return node
        if self.add_default is not None:
            node.keywords.append(ast.keyword(arg=self.kw, value=ast.Constant(self.add_default)))
            self.sites += 1
        return node


def split_changed(src: str) -> str | None:
    def f(v):
        if isinstance(v, float):
            return round(v + 0.05, 4) if v < 0.9 else round(v - 0.05, 4)
        return v + 1
    return _apply(_KwTx({"train_test_split"}, "test_size", f, add_default=0.3), src)


def cv_changed(src: str) -> str | None:
    tx = _KwTx(None, "n_splits", lambda v: v + 1 if isinstance(v, int) else v)
    out = _apply(tx, src)
    tx2 = _KwTx(None, "cv", lambda v: v + 1 if isinstance(v, int) else v)
    return _apply(tx2, out or src) or out


def iterations_reduced(src: str) -> str | None:
    tx = _KwTx(None, "max_iter", lambda v: max(1, int(v) // 2) if isinstance(v, int) else v)
    out = _apply(tx, src)
    tx2 = _KwTx(None, "n_estimators", lambda v: max(1, int(v) // 2) if isinstance(v, int) else v)
    return _apply(tx2, out or src) or out


def comment_added(src: str) -> str:
    return src + "\n# reproducibility audit note: no functional change\n"


def reformatted(src: str) -> str:
    return ast.unparse(ast.parse(src))


OPERATORS: tuple[Operator, ...] = (
    Operator("seed_removed", "positive", "source", "Literal seeds replaced by None / removed", seed_removed),
    Operator("seed_changed", "positive", "source", "Literal seeds incremented by 1", seed_changed),
    Operator("split_changed", "positive", "source", "train_test_split test_size changed (or set)", split_changed),
    Operator("cv_changed", "positive", "source", "cv / n_splits fold count incremented", cv_changed),
    Operator("iterations_reduced", "positive", "source", "max_iter / n_estimators halved", iterations_reduced),
    Operator("comment_added", "control", "source", "Comment appended", comment_added),
    Operator("reformatted", "control", "source", "Code reformatted via AST round trip", reformatted),
    Operator("threads_1", "control", "environment", "OMP_NUM_THREADS=1", None, {"OMP_NUM_THREADS": "1"}),
    Operator("workdir_moved", "control", "environment", "Run from a different working-directory path",
             None, None, "moved/elsewhere/dir"),
)


# --------------------------------------------------------------------------
# Auditors (same four classes as the synthetic benchmark)
# --------------------------------------------------------------------------

def make_record(source: str, out: RunOutput) -> dict:
    return {"seeds": seed_literals(source), "semantic_hash": semantic_hash(source),
            "result_fp": fingerprint_numbers(out.numbers), "n_numbers": len(out.numbers)}


def audit_seed_only(source: str, record: dict) -> bool:
    """Flags when the literal seeds differ from those of the recorded run."""
    return seed_literals(source) != record["seeds"]


def audit_static(source: str, record: dict) -> bool:
    return semantic_hash(source) != record["semantic_hash"]


def audit_dynamic(source: str, record: dict, op: Operator, repeats: int = 2, timeout: float = 60) -> tuple[bool, float]:
    t = time.perf_counter()
    fps = []
    for _ in range(repeats):
        o = run_script(source, timeout, op.env, op.workdir_name)
        fps.append(fingerprint_numbers(o.numbers) if o.ok else "FAILED")
    flagged = any(fp != record["result_fp"] for fp in fps)
    return flagged, time.perf_counter() - t


def oracle(source: str, baseline: list[RunOutput], op: Operator, repeats: int = 2, timeout: float = 60) -> dict:
    runs = [run_script(source, timeout, op.env, op.workdir_name) for _ in range(repeats)]
    if not all(r.ok for r in runs):
        return {"result_changed": True, "crashed": True}
    changed = any(not numbers_close(r.numbers, b.numbers) for r in runs for b in baseline)
    changed |= any(not numbers_close(r.numbers, runs[0].numbers) for r in runs[1:])
    return {"result_changed": changed, "crashed": False}


# --------------------------------------------------------------------------
# Study driver
# --------------------------------------------------------------------------

def sample_order(paths: list[str], seed_text: str) -> list[str]:
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    order = sorted(paths)
    rng.shuffle(order)
    return order


def screen(path: Path, timeout: float) -> dict:
    """Eligibility checks E1-E4 for one script."""
    src = path.read_text()
    if NETWORK_RE.search(src):
        return {"eligible": False, "reason": "E1 network/data download"}
    try:
        ast.parse(src)
    except SyntaxError:
        return {"eligible": False, "reason": "unparseable"}
    b1 = run_script(src, timeout)
    if not b1.ok:
        return {"eligible": False, "reason": "E2 failed/timeout: " + b1.error[:80]}
    if not b1.numbers:
        return {"eligible": False, "reason": "E3 prints no numeric result"}
    b2 = run_script(src, timeout)
    if not (b2.ok and numbers_close(b1.numbers, b2.numbers)):
        return {"eligible": False, "reason": "E4 baseline not reproducible run-to-run",
                "naturally_nondeterministic": True}
    return {"eligible": True, "baseline": [b1, b2]}


def _baseline_from(rec: dict) -> list[RunOutput]:
    return [RunOutput(True, nums, rec["baseline_seconds"]) for nums in rec["baseline_numbers"]]


def screen_task(args):
    idx, path, root, timeout = args
    path, root = Path(path), Path(root)
    s = screen(path, timeout)
    rec = {"order": idx, "script": str(path.relative_to(root)), "eligible": s["eligible"],
           "reason": s.get("reason", ""),
           "naturally_nondeterministic": s.get("naturally_nondeterministic", False)}
    if s["eligible"]:
        rec["baseline_numbers"] = [b.numbers for b in s["baseline"]]
        rec["baseline_seconds"] = round(s["baseline"][0].seconds, 3)
    return "screen", rec


def mutation_task(args):
    """One (script, operator) unit: oracle + dynamic audit. Short enough to resume safely."""
    rec, op_id, root, timeout, dyn_repeats, oracle_repeats = args
    op = next(o for o in OPERATORS if o.id == op_id)
    src = (Path(root) / rec["script"]).read_text()
    baseline = _baseline_from(rec)
    record = make_record(src, baseline[0])
    mutant = op.transform(src) if op.transform else src
    orc = oracle(mutant, baseline, op, oracle_repeats, timeout)
    dyn, dyn_s = audit_dynamic(mutant, record, op, dyn_repeats, timeout)
    return "case", {
        "order": rec["order"], "script": rec["script"], "operator": op.id, "intent": op.intent,
        "kind": op.kind, "oracle_changed": orc["result_changed"], "crashed": orc["crashed"],
        "seed_only": audit_seed_only(mutant, record), "static_manifest": audit_static(mutant, record),
        "dynamic": dyn, "dynamic_seconds": round(dyn_s, 3),
        "baseline_seconds": rec["baseline_seconds"], "n_numbers": record["n_numbers"],
    }


def applicable_ops(src: str) -> list[str]:
    return [o.id for o in OPERATORS if (o.transform is None or o.transform(src) is not None)]


def run_study(examples_root: Path, out_dir: Path, seed_text: str, target: int,
              budget_s: float, timeout: float = 30, workers: int = 4,
              dyn_repeats: int = 2, oracle_repeats: int = 2) -> dict:
    """Resumable, unit-based driver. Screening in sampled order until `target`
    eligible scripts; then every applicable (script, operator) unit."""
    from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
    examples_root, out_dir = Path(examples_root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    screen_f, cases_f = out_dir / "screening.jsonl", out_dir / "cases.jsonl"
    screened = {json.loads(l)["order"]: json.loads(l) for l in screen_f.read_text().splitlines()} \
        if screen_f.exists() else {}
    cases = {(json.loads(l)["order"], json.loads(l)["operator"]) for l in cases_f.read_text().splitlines()} \
        if cases_f.exists() else set()
    paths = sample_order([str(p) for p in examples_root.rglob("*.py")], seed_text)
    (out_dir / "sampling_order.json").write_text(json.dumps(
        [str(Path(p).relative_to(examples_root)) for p in paths], indent=1))
    start = time.time()

    def sample():
        chosen, i = [], 0
        while i in screened and len(chosen) < target:
            if screened[i]["eligible"]:
                chosen.append(screened[i])
            i += 1
        return chosen, i, len(chosen) >= target

    def next_tasks(in_flight):
        chosen, frontier, full = sample()
        tasks, mtasks = [], []
        for rec in chosen:
            src = (examples_root / rec["script"]).read_text()
            for op_id in applicable_ops(src):
                key = (rec["order"], op_id)
                if key not in cases and key not in in_flight:
                    mtasks.append((key, mutation_task,
                                  (rec, op_id, str(examples_root), timeout, dyn_repeats, oracle_repeats)))
        if not full:
            j = frontier
            eligible_needed = target - len(chosen)
            launched = sum(1 for k in in_flight if k[1] == "screen")
            while j < len(paths) and launched < max(eligible_needed, 1) * 2:
                key = (j, "screen")
                if j not in screened and key not in in_flight:
                    tasks.append((key, screen_task, (j, paths[j], str(examples_root), timeout)))
                    launched += 1
                j += 1
        # interleave screening and mutation units so neither starves
        out = []
        for a, b in zip(tasks, mtasks):
            out += [a, b]
        n = min(len(tasks), len(mtasks))
        return out + tasks[n:] + mtasks[n:]

    with ProcessPoolExecutor(workers) as ex:
        running = {}
        while True:
            if time.time() - start < budget_s:
                for key, fn, args in next_tasks(set(running.values())):
                    if len(running) >= workers:
                        break
                    running[ex.submit(fn, args)] = key
            if not running:
                break
            done_set, _ = wait(running, return_when=FIRST_COMPLETED)
            for fut in done_set:
                running.pop(fut)
                kind, rec = fut.result()
                if kind == "screen":
                    screened[rec["order"]] = rec
                    with screen_f.open("a") as fh:
                        fh.write(json.dumps(rec) + "\n")
                else:
                    cases.add((rec["order"], rec["operator"]))
                    with cases_f.open("a") as fh:
                        fh.write(json.dumps(rec) + "\n")
    chosen, _, full = sample()
    remaining = sum(1 for rec in chosen for op in applicable_ops((examples_root / rec["script"]).read_text())
                    if (rec["order"], op) not in cases)
    return {"screened": len(screened), "eligible_in_sample": len(chosen), "sample_full": full,
            "cases_done": len(cases), "cases_remaining": remaining,
            "complete": full and remaining == 0}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("examples_root")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed-text", default="10.5281/zenodo.24048006")
    ap.add_argument("--target", type=int, default=30)
    ap.add_argument("--budget", type=float, default=500)
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    print(json.dumps(run_study(Path(a.examples_root), Path(a.out), a.seed_text, a.target,
                               a.budget, a.timeout, a.workers)))
