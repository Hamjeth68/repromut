"""Tests for the E2 framework. No Docker and no third-party code: a fake executor stands in for containers."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import numpy as np
import pytest

from repromut.e2 import analysis as AN
from repromut.e2 import auditors as A
from repromut.e2 import container as C
from repromut.e2 import outputs as O
from repromut.e2.cases import CaseSpec, absolutise_entry, materialise, perturb_rows, standard_controls
from repromut.e2.oracle import Observed, baseline_stable, label
from repromut.e2.study import RepoPlan, run_repo

IMG = "python@sha256:" + "a" * 64


# ----------------------------------------------------------------------------- outputs
def test_parse_formats_and_canonicalisation():
    buf = io.BytesIO(); np.save(buf, np.array([-0.0, 1.5]))
    assert O.parse_file("a.npy", buf.getvalue())["a.npy"].tolist() == [0.0, 1.5]
    assert O.parse_file("m.json", b'{"b": 2, "a": [1, "x", null]}')["m.json"].tolist() == [1.0, 2.0]
    assert O.parse_file("t.csv", b"x,y\n1,2\nfoo,3.5\n")["t.csv"].tolist() == [1.0, 2.0, 3.5]
    with pytest.raises(ValueError):
        O.parse_file("img.png", b"\x89PNG")


def test_collect_marks_missing_files_and_excludes_timing_lines():
    spec = O.AdapterSpec(stdout=True, files=["out.json"])
    outs = O.collect(spec, "acc 0.9\ntook 3.2 seconds\n", {})
    assert outs["stdout"].tolist() == [0.9]
    assert np.isnan(outs["out.json:<missing>"]).all()


def test_clock_stamped_lines_are_excluded():
    outs = O.collect(O.AdapterSpec(), "[03:49:44] WARNING: learner.cc:1115 note\nacc 0.5\n", {})
    assert outs["stdout"].tolist() == [0.5]


def test_identifier_lines_are_excluded():
    outs = O.collect(O.AdapterSpec(), "Training Job Finished: Model version: 2\nrun_id 7\nr2 0.76\n", {})
    assert outs["stdout"].tolist() == [0.76]


def test_date_stamped_lines_are_excluded():
    outs = O.collect(O.AdapterSpec(), "Saved run 20261109-101010\nlog 2026-11-09 ok\nacc 0.9\n", {})
    assert outs["stdout"].tolist() == [0.9]


def test_first_difference_and_tolerance():
    a = {"stdout": np.array([1.0]), "f": np.array([2.0])}
    assert O.first_difference(a, {"stdout": np.array([1.0 + 1e-12]), "f": np.array([2.0])}) is None
    assert O.first_difference(a, {"stdout": np.array([1.0]), "f": np.array([2.1])}) == "f"
    assert O.first_difference(a, {"stdout": np.array([1.0, 2.0]), "f": np.array([2.0])}) == "stdout"


def test_fingerprint_rounding_and_negative_zero():
    assert O.fingerprint({"x": np.array([0.0])}) == O.fingerprint({"x": np.array([-0.0])})
    assert O.fingerprint({"x": np.array([1.0])}) == O.fingerprint({"x": np.array([1.0 + 1e-12])})
    assert O.fingerprint({"x": np.array([1.0])}) != O.fingerprint({"x": np.array([1.001])})


# ----------------------------------------------------------------------------- container
def test_docker_argv_has_every_isolation_flag(tmp_path):
    spec = C.ContainerSpec(IMG, tmp_path, "/work/repo", ["python", "main.py"], {"V": "1"})
    argv = C.build_docker_argv(spec, "rmx-test")
    joined = " ".join(argv)
    for flag in C.ISOLATION_FLAGS:
        assert flag in argv
    assert "--network none" in joined and "docker.sock" not in joined and "--privileged" not in joined
    assert argv[argv.index("-v") + 1].endswith(":/work:rw")
    assert argv.count("-v") == 1                          # only the work copy is mounted
    assert "PYTHONHASHSEED=0" in argv and "V=1" in argv
    assert argv[-3:] == [IMG, "python", "main.py"]


@pytest.mark.parametrize("image,cwd", [("python:3.12-slim", "/work"), (IMG, "/etc")])
def test_docker_argv_rejects_unpinned_image_or_cwd_outside_work(tmp_path, image, cwd):
    with pytest.raises(ValueError):
        C.build_docker_argv(C.ContainerSpec(image, tmp_path, cwd, ["true"]), "x")


def test_read_outputs_refuses_symlinks_and_escapes(tmp_path):
    secret = tmp_path / "secret.txt"; secret.write_text("host secret")
    work = tmp_path / "work"; (work / "out").mkdir(parents=True)
    (work / "out" / "ok.json").write_text("[1]")
    os.symlink(secret, work / "out" / "leak.json")
    os.symlink(tmp_path, work / "linkdir")
    got = C.read_outputs(work, ["out/ok.json", "out/leak.json", "linkdir/secret.txt", "../secret.txt", str(secret)])
    assert got == {"out/ok.json": b"[1]"}


def test_run_classifies_timeout_crash_and_infra(tmp_path):
    import subprocess
    spec = C.ContainerSpec(IMG, tmp_path, "/work", ["x"], timeout_s=1)
    calls = []

    def timeout_runner(argv, **kw):
        calls.append(argv)
        if argv[1] == "kill":
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        raise subprocess.TimeoutExpired(argv, 1)
    assert C.run(spec, [], runner=timeout_runner).status == "timeout"
    assert calls[-1][:2] == ["docker", "kill"]
    crash = lambda argv, **kw: subprocess.CompletedProcess(argv, 1, b"", b"boom")
    assert C.run(spec, [], runner=crash).status == "crash"
    infra = lambda argv, **kw: subprocess.CompletedProcess(argv, 125, b"", b"daemon error")
    assert C.run(spec, [], runner=infra).status == "infra_failure"


# ----------------------------------------------------------------------------- oracle
def _obs(*vals, status="ok"):
    return Observed(status, {"stdout": np.array(vals, float)} if status == "ok" else None)


def test_oracle_labels():
    base = [_obs(1.0) for _ in range(5)]
    assert label(base, [_obs(1.0)] * 3)[0] == "unchanged"
    lab, first = label(base, [_obs(2.0)] * 3)
    assert (lab, first) == ("stable_change", "stdout")
    assert label(base, [_obs(2.0), _obs(1.0), _obs(2.0)])[0] == "intermittent_change"
    assert label(base, [_obs(2.0), _obs(3.0), _obs(4.0)])[0] == "indeterminate"
    assert label(base, [_obs(1.0), _obs(status="crash"), _obs(1.0)])[0] == "crash"
    assert label(base, [_obs(status="timeout")] * 3)[0] == "timeout"
    assert label(base, [_obs(status="infra_failure")] * 3)[0] == "infra_failure"


def test_nondeterministic_baseline_is_indeterminate():
    base = [_obs(1.0), _obs(1.0), _obs(1.5), _obs(1.0), _obs(1.0)]
    assert not baseline_stable(base)
    assert label(base, [_obs(2.0)] * 3)[0] == "indeterminate"


# ----------------------------------------------------------------------------- auditors
def test_static_manifests(tmp_path):
    (tmp_path / "main.py").write_text("x = 1\n")
    (tmp_path / "conf.yaml").write_text("a: 1\n")
    tracked = ["main.py", "conf.yaml"]
    base = A.s1_manifest(tmp_path, tracked, ["python", "main.py"])
    (tmp_path / "main.py").write_text("x = 1  # comment only\n")
    assert A.s1_manifest(tmp_path, tracked, ["python", "main.py"]) == base       # AST hash ignores comments
    (tmp_path / "cache.pkl").write_bytes(b"stale")
    assert A.s1_manifest(tmp_path, tracked, ["python", "main.py"]) == base       # S1 blind to untracked files
    s2a = A.s2_manifest(tmp_path, tracked, ["python", "main.py"], packages="p", env={}, cwd_abs="/work/repo")
    (tmp_path / "cache.pkl").write_bytes(b"other")
    s2b = A.s2_manifest(tmp_path, tracked, ["python", "main.py"], packages="p", env={}, cwd_abs="/work/repo")
    assert A.static_flag(s2a, s2b)
    (tmp_path / "conf.yaml").write_text("a: 2\n")
    assert A.static_flag(base, A.s1_manifest(tmp_path, tracked, ["python", "main.py"]))


def test_dynamic_flag_reasons():
    assert A.dynamic_flag("f", ["f", "f", "g"], k=2).flag is False
    assert A.dynamic_flag("f", ["f", "f", "g"], k=3).reason == "numeric_change"
    assert A.dynamic_flag("f", ["g", "g"], k=2).reason == "numeric_change"
    assert A.dynamic_flag("f", [None, "f"], k=2).reason == "execution_failure"
    assert A.combine(False, A.DynamicResult(True, "numeric_change", [])) == (True, "dynamic:numeric_change")


# ----------------------------------------------------------------------------- cases
def test_perturb_rows_and_entry_relocation():
    assert perturb_rows(b"h\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n") == b"h\n1\n2\n3\n4\n5\n6\n7\n8\n9\n"
    assert absolutise_entry(["python", "src/main.py", "-v"], "/work/repo") == ["python", "/work/repo/src/main.py", "-v"]
    with pytest.raises(ValueError):
        absolutise_entry(["python", "-m", "pkg"], "/work/repo")


def test_materialise_layouts(tmp_path):
    src = tmp_path / "src"; (src / "data").mkdir(parents=True)
    (src / "main.py").write_text("print(1)\n"); (src / "data" / "x.csv").write_text("a\n1\n")
    art = tmp_path / "art"; art.mkdir(); (art / "shadow.csv").write_text("a\n9\n")
    case = CaseSpec("M-PATH-1", "M-PATH", "positive", shadow_files={"data/x.csv": "shadow.csv"})
    cwd, argv, repo = materialise(case, src, tmp_path / "r1", art, ["python", "main.py"])
    assert cwd == "/work/sibling" and argv == ["python", "/work/repo/main.py"]
    assert (tmp_path / "r1/sibling/data/x.csv").read_text() == "a\n9\n"
    assert (repo / "data/x.csv").read_text() == "a\n1\n"                         # tracked file untouched
    cwd, _, repo = materialise(CaseSpec("C-PATH", "C-PATH", "control"), src, tmp_path / "r2", art, ["python", "main.py"])
    assert cwd.endswith("relocated/deeper/repo") and (repo / "main.py").exists()
    with pytest.raises(ValueError):
        materialise(CaseSpec("bad", "M-CACHE", "positive", pre_files={"../x": "shadow.csv"}),
                    src, tmp_path / "r3", art, ["python", "main.py"])
    assert {c.case_id for c in standard_controls(True)} == {"C-ENV", "C-CACHE", "C-PATH", "C-DEP"}


def test_mpath_mirrors_cwd_depth_and_keeps_console_scripts(tmp_path):
    src = tmp_path / "src"; (src / "src" / "core").mkdir(parents=True); (src / "data").mkdir()
    (src / "src" / "core" / "main.py").write_text("open('../../data/x.txt')\n"); (src / "data" / "x.txt").write_text("1")
    art = tmp_path / "art"; art.mkdir(); (art / "s.txt").write_text("2")
    case = CaseSpec("M-PATH-1", "M-PATH", "positive", shadow_files={"data/x.txt": "s.txt"})
    cwd, argv, _ = materialise(case, src, tmp_path / "r", art, ["python", "main.py"], cwd_rel="src/core")
    assert cwd == "/work/sibling/src/core" and argv == ["python", "/work/repo/src/core/main.py"]
    # ../../data from the sibling cwd resolves to the shadow file inside the sibling tree
    assert (tmp_path / "r/sibling/src/core/../../data/x.txt").resolve().read_text() == "2"
    assert absolutise_entry(["JDML", "train", "-C", "c.yaml"], "/work/repo") == ["JDML", "train", "-C", "c.yaml"]


# ----------------------------------------------------------------------------- end-to-end with a fake executor
def _fake_executor(spec: C.ContainerSpec, declared: list[str]) -> C.RunResult:
    """Simulates our own fixture program: result = value of cwd-relative data file + SCALE env + cache."""
    root = Path(spec.work_host)
    cwd = root / spec.cwd.removeprefix("/work").lstrip("/")
    repo = root / Path(spec.argv[1]).parent.as_posix().removeprefix("/work/") if spec.argv[1].startswith("/") else cwd
    val = float((cwd / "data.txt").read_text()) if (cwd / "data.txt").exists() else float("nan")
    if (repo / "cache.txt").exists():
        val = float((repo / "cache.txt").read_text())
    val *= float(spec.env.get("SCALE", "1"))
    if spec.image.endswith("b" * 64):
        val += 0.5                                                                  # "dependency default change"
    (cwd / "out.json").write_text(json.dumps({"v": val}))                          # outputs land in the cwd
    files = C.read_outputs(root, declared)
    return C.RunResult("ok", 0, f"result {val}\n", "", 0.01, files)


def test_run_repo_end_to_end_and_resume(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "main.py").write_text("print('fixture')\n"); (src / "data.txt").write_text("2.0")
    art = tmp_path / "art"; art.mkdir(); (art / "stale.txt").write_text("7.0"); (art / "shadow.txt").write_text("3.0")
    cases = [CaseSpec("M-ENV-1", "M-ENV", "positive", env={"SCALE": "3"}),
             CaseSpec("M-CACHE-1", "M-CACHE", "positive", pre_files={"cache.txt": "stale.txt"}),
             CaseSpec("M-PATH-1", "M-PATH", "positive", shadow_files={"data.txt": "shadow.txt"}),
             CaseSpec("M-DEP-1", "M-DEP", "positive", image_key="dep_alt"),
             *standard_controls(True)]
    plan = RepoPlan("me/fixture", src, ["python", "main.py"], O.AdapterSpec(files=["out.json"]),
                    ["main.py", "data.txt"],
                    {"base": IMG, "dep_alt": "python@sha256:" + "b" * 64, "dep_patch": "python@sha256:" + "c" * 64},
                    {"base": "sklearn==1.4.0", "dep_alt": "sklearn==1.5.0", "dep_patch": "sklearn==1.4.2"},
                    cases, art)
    out = tmp_path / "cases.jsonl"
    recs = {r["case_id"]: r for r in run_repo(plan, out, tmp_path / "work", execute=_fake_executor)}
    for cid in ("M-ENV-1", "M-CACHE-1", "M-PATH-1", "M-DEP-1"):
        assert recs[cid]["label"] == "stable_change", cid
        assert recs[cid]["flags"]["D"] and not recs[cid]["flags"]["S1"], cid
        assert recs[cid]["flags"]["S2"], cid                                         # S2 sees env/untracked/cwd/packages
    for cid in ("C-ENV", "C-CACHE", "C-PATH", "C-DEP"):
        assert recs[cid]["label"] == "unchanged" and not recs[cid]["flags"]["D"], cid
    assert recs["M-CACHE-1"]["first_divergence"] == "stdout"
    n_lines = len(out.read_text().splitlines())
    calls = []
    run_repo(plan, out, tmp_path / "work", execute=lambda s, d: calls.append(1))     # resume: nothing re-run
    assert not calls and len(out.read_text().splitlines()) == n_lines


# ----------------------------------------------------------------------------- analysis
def _rec(repo, intent, lab, d, s1):
    return {"repo": repo, "intent": intent, "label": lab, "flags": {"D": d, "S1": s1}}


def test_analysis_verdicts():
    pos = [_rec(f"r{i}", "positive", "stable_change", True, False) for i in range(5) for _ in range(3)]
    neg35 = [_rec(f"r{i}", "control", "unchanged", False, False) for i in range(5) for _ in range(7)]
    res = AN.analyse(pos + neg35, reps=500)
    assert res["n_pos"] == 15 and res["n_neg"] == 35 and res["minimum_evidence"]
    assert res["recall_diff"] == 1.0 and res["recall_diff_ci"][0] > 0
    # Zero false positives in both arms: Wilson upper bound for 0/35 is 9.89% <= 10pp (DEVIATIONS S14).
    assert res["fpr_rule"].startswith("wilson") and res["fpr_acceptable"] is True
    assert res["verdict"] == "supported"
    # With 25 negatives the minimum-evidence rule is not met.
    assert AN.analyse(pos + neg35[:25], reps=200)["verdict"] == "inconclusive"
    # A false-alarm increase above 5pp makes the verdict "not supported".
    noisy = [dict(r, flags={"D": i % 5 == 0, "S1": False}) for i, r in enumerate(neg35)]
    assert AN.analyse(pos + noisy, reps=300)["verdict"] == "not_supported"
    a = AN.cluster_bootstrap(pos + neg35, "D", "S1", reps=300)
    assert a == AN.cluster_bootstrap(pos + neg35, "D", "S1", reps=300)                 # seeded and deterministic
