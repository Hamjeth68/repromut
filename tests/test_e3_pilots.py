"""Tests for the E3 pilots (e3/pilots). No Docker and no third-party code: a fake executor stands in."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e3" / "pilots"))
import pilotlib as PL  # noqa: E402

from repromut.e2 import container as C  # noqa: E402
from repromut.e2.cases import CaseSpec  # noqa: E402

IMG = "python@sha256:" + "a" * 64


# ----------------------------------------------------------------------------- selection (real E2 records)
def test_pilot_t_selection_rule_on_e2_records():
    manifest = json.loads((ROOT / "e2" / "REPOSITORY-MANIFEST.json").read_text())
    got = PL.select_pilot_t(manifest, ROOT / "e2" / "results" / "full")
    # Tabular-AutoML (P1 order 14) is skipped: its E2 baseline was not stable.
    assert got == ["fmind/mlops-python-package",
                   "ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques",
                   "youngcoder45/Student-Performance-Predictor"]


def test_pilot_n_config_names_e2_nondeterministic_repo():
    cfg = json.loads((ROOT / "e3" / "pilots" / "pilot_n_config.json").read_text())
    base = [json.loads(l) for l in (ROOT / "e2" / "results" / "full" / f"{PL.slug(cfg['repo'])}.jsonl")
            .read_text().splitlines() if '"case_id": "baseline"' in l][0]
    assert base["stable"] is False
    assert cfg["n_runs"] == 10 and cfg["repeats"] == 2 and cfg["alpha"] == 0.01 and cfg["seed"] == 20261114


# ----------------------------------------------------------------------------- pilot T pieces
def test_threads_case_is_env_only_and_valid():
    c = PL.threads_case()
    assert c.family == "M-ENV" and c.intent == "positive"
    assert c.env == {v: "1" for v in PL.THREAD_VARS}
    assert not c.pre_files and not c.shadow_files and c.image_key == "base"


def test_threadpool_parsing_and_signature():
    info = [{"user_api": "blas", "internal_api": "openblas", "prefix": "libopenblas", "num_threads": 4,
             "filepath": "/x", "version": "0.3"}]
    out = "noise\n" + PL.DIAG_MARK + json.dumps(info) + "\n"
    parsed = PL.parse_threadpool(out)
    assert parsed == [{"user_api": "blas", "internal_api": "openblas", "prefix": "libopenblas",
                       "version": "0.3", "num_threads": 4}]
    one = [dict(info[0], num_threads=1)]
    assert PL.thread_signature(parsed) != PL.thread_signature(PL.parse_threadpool(PL.DIAG_MARK + json.dumps(one)))
    assert PL.parse_threadpool("nothing here") is None
    assert PL.parse_threadpool(PL.DIAG_MARK + "{broken") is None
    assert PL.thread_signature(None) is None


@pytest.mark.parametrize("effects,labels,adopt", [
    ([True, True, False], ["unchanged", "stable_change", "unchanged"], True),
    ([True, False, False], ["unchanged", "unchanged", "unchanged"], False),       # took effect in 1 of 3
    ([True, True, True], ["unchanged", "indeterminate", "unchanged"], False),    # a label not decidable
    ([True, True, True], ["unchanged", "infra_failure", "unchanged"], False),    # infra failure left
    ([True, True], ["unchanged", "unchanged"], False),                           # only 2 repositories
])
def test_adopt_t(effects, labels, adopt):
    reps = [{"diag_differs": e, "label": l} for e, l in zip(effects, labels)]
    assert PL.adopt_t(reps)["adopt"] is adopt


# ----------------------------------------------------------------------------- pilot N pieces
def test_extract_metric_strips_ansi_and_takes_last():
    out = ("\x1b[36mCurrent best val_mse value : 0.5\x1b[0m\n"
           "Model Metrics :\n"
           "\x1b[36mCurrent best val_mse value : 0.3132\x1b[0m\n")
    pat = r"Current best val_mse value : ([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)"
    assert PL.extract_metric(out, pat) == pytest.approx(0.3132)
    assert PL.extract_metric(out, pat, "first") == pytest.approx(0.5)
    assert PL.extract_metric("no metric line", pat) is None


def test_permutation_pvalue():
    assert PL.permutation_pvalue([1.0] * 10, [1.0] * 10) == 1.0                    # identical groups
    p_sep = PL.permutation_pvalue([0.0] * 10, [1.0] * 10)
    assert p_sep < 1e-3                                                             # fully separated
    assert PL.permutation_pvalue([0.0] * 10, [1.0] * 10) == p_sep                  # seeded, reproducible
    # exact two-sided p for [1,2,3] vs [4,5,6] is 2/20 = 0.1
    assert PL.permutation_pvalue([1, 2, 3], [4, 5, 6]) == pytest.approx(0.1, abs=0.02)
    assert PL.permutation_pvalue([], [1.0]) is None
    assert PL.permutation_pvalue([float("nan")], [1.0]) is None


@pytest.mark.parametrize("statuses,pv,expected", [
    (["ok"] * 4, {"a": 0.004, "b": 0.9}, "distribution_change"),       # 0.004 < 0.01/2
    (["ok"] * 4, {"a": 0.006, "b": 0.9}, "no_detected_change"),        # Bonferroni: 0.006 >= 0.005
    (["ok"] * 4, {"a": 0.006}, "distribution_change"),                 # one metric: 0.006 < 0.01
    (["ok"] * 4, {"a": None, "b": 0.001}, "indeterminate"),            # missing metric
    (["ok", "crash", "ok"], {"a": 0.001}, "crash"),
    (["ok", "timeout", "crash"], {"a": 0.001}, "timeout"),
    (["infra_failure"] * 3, {"a": 0.001}, "infra_failure"),
    (["ok", "infra_failure"], {"a": 0.001}, "indeterminate"),
])
def test_label_n(statuses, pv, expected):
    assert PL.label_n(statuses, pv, 0.01) == expected


def test_adopt_n():
    rep = lambda lab: [{"case_id": "baseline", "statuses": ["ok"] * 3},
                       {"case_id": "M-PATH-1", "label": lab, "statuses": ["ok"] * 3}]
    assert PL.adopt_n([rep("distribution_change"), rep("distribution_change")])["adopt"] is True
    assert PL.adopt_n([rep("distribution_change"), rep("no_detected_change")])["adopt"] is False
    bad = rep("distribution_change"); bad[1]["statuses"] = ["ok", "timeout", "ok"]
    assert PL.adopt_n([bad, rep("distribution_change")])["adopt"] is False
    assert PL.adopt_n([rep("distribution_change")])["adopt"] is False             # needs two repeats


# ----------------------------------------------------------------------------- end-to-end, fake executor
def _fixture_repo(tmp_path: Path) -> dict:
    src = tmp_path / "src"; src.mkdir()
    (src / "main.py").write_text("print('fixture')\n"); (src / "data.txt").write_text("0.3")
    return {"repo": "me/fixture", "source_tree": str(src), "argv": ["python", "main.py"], "cwd_rel": "",
            "timeout_s": 600, "adapter": {"stdout": True, "files": []}}


def _run_index(spec: C.ContainerSpec) -> int:
    return int(Path(spec.work_host).name.rsplit("-", 1)[1])


def _fake(spec: C.ContainerSpec, declared: list[str]) -> C.RunResult:
    """Stands in for containers. Diagnostic: thread count follows OMP_NUM_THREADS.
    Experiment: prints the value of the cwd-relative data.txt, plus a tiny shift when single-threaded,
    plus deterministic run-index noise when NOISE=1 is set by the test plan (nondeterministic baseline)."""
    if spec.argv[:3] == ["python", "-I", "-c"]:
        n = 1 if spec.env.get("OMP_NUM_THREADS") == "1" else 4
        info = [{"user_api": "openmp", "internal_api": "openmp", "prefix": "libgomp", "num_threads": n}]
        return C.RunResult("ok", 0, PL.DIAG_MARK + json.dumps(info) + "\n", "", 0.01)
    root = Path(spec.work_host)
    cwd = root / spec.cwd.removeprefix("/work").lstrip("/")
    val = float((cwd / "data.txt").read_text())
    if spec.env.get("OMP_NUM_THREADS") == "1":
        val += 1e-3
    if _FAKE_NOISE[0]:
        val += 0.01 * ((_run_index(spec) * 7) % 10) / 10
    out = f"\x1b[36mCurrent best val_mse value : {val}\x1b[0m\nCurrent best val_accuracy_score value : 1.0\n"
    return C.RunResult("ok", 0, out, "", 0.01, {})


_FAKE_NOISE = [False]


def test_pilot_t_end_to_end(tmp_path):
    _FAKE_NOISE[0] = False
    plan = _fixture_repo(tmp_path)
    st = PL.stage(plan, tmp_path / "pw", tmp_path / "e2art", {"base": IMG}, {"base": "scikit-learn==1.4.0"},
                  with_artifacts=False)
    r = PL.run_pilot_t_repo(st, tmp_path / "out", tmp_path / "pw", execute=_fake)
    assert r["diag_differs"] is True
    assert r["label"] == "stable_change"
    assert r["flags"]["D"] and not r["flags"]["S1"] and r["flags"]["S2"]           # S2 sees the env map
    diag = json.loads((tmp_path / "out" / "me__fixture.diagnostic.json").read_text())
    assert diag["differs"] and diag["baseline"]["threadpools"][0]["num_threads"] == 4
    assert PL.adopt_t([r, r, r])["adopt"] is True


def test_pilot_n_end_to_end(tmp_path):
    _FAKE_NOISE[0] = True
    try:
        plan = _fixture_repo(tmp_path)
        st = PL.stage(plan, tmp_path / "pw", tmp_path / "e2art", {"base": IMG}, {"base": "x"}, with_artifacts=False)
        (st.art / "shadow.txt").write_text("0.8")
        cases = [CaseSpec("M-PATH-1", "M-PATH", "positive", shadow_files={"data.txt": "shadow.txt"}),
                 CaseSpec("C-ENV", "C-ENV", "control", env={"REPROMUT_UNUSED_VAR": "1"})]
        cfg = json.loads((ROOT / "e3" / "pilots" / "pilot_n_config.json").read_text())
        reps = [PL.run_pilot_n_repeat(st, cases, cfg, r, tmp_path / "out", tmp_path / "pw", execute=_fake)
                for r in (1, 2)]
    finally:
        _FAKE_NOISE[0] = False
    by = {x["case_id"]: x for x in reps[0]}
    assert by["baseline"]["n_distinct_fingerprints"] > 1                           # baseline is nondeterministic
    assert by["M-PATH-1"]["label"] == "distribution_change"
    assert by["C-ENV"]["label"] == "no_detected_change"
    assert by["C-ENV"]["flags"]["D"] is True            # plain re-running false-alarms on noisy baselines
    assert PL.adopt_n(reps)["adopt"] is True
    assert (tmp_path / "out" / "me__fixture.repeat2.jsonl").exists()


def test_stage_requires_e2_setup_artifacts(tmp_path):
    plan = dict(_fixture_repo(tmp_path), setup={"add_files": {"data/x.zip": "x.zip"}})
    with pytest.raises(FileNotFoundError):
        PL.stage(plan, tmp_path / "pw", tmp_path / "e2art", {"base": IMG}, {"base": "x"}, with_artifacts=False)


def test_cli_dry_runs_report_missing_e2_work_area(monkeypatch, tmp_path, capsys):
    """On a machine without ~/repromut-e2-work the scripts refuse to run anything (exit 2)."""
    monkeypatch.setattr(PL.RP, "WORK", tmp_path / "no-e2-work")
    import pilot_n
    import pilot_t
    assert pilot_t.main(["--dry-run"]) == 2
    assert "NOT READY" in capsys.readouterr().out
    assert pilot_n.main(["--dry-run"]) == 2


# ----------------------------------------------------------------------------- restore_inputs (no network, no Docker)
import io as _io  # noqa: E402
import tarfile as _tarfile  # noqa: E402

import restore_inputs as RI  # noqa: E402


def test_restore_covers_the_four_pilot_repositories_with_committed_build_files():
    repos = RI.pilot_repos()
    assert repos == ["fmind/mlops-python-package", "ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques",
                     "youngcoder45/Student-Performance-Predictor", "sagnik1511/Tabular-AutoML"]
    for r in repos:
        src = RI.build_src(r)
        assert (src / "Dockerfile").exists() and (src / "packages_base.txt").exists(), r
        plan = json.loads((ROOT / "e2" / "plans" / f"{PL.slug(r)}.json").read_text())
        if plan["build"]["mode"] == "requirements":
            assert (src / "lock.txt").exists(), r
        assert len(RI.commit_of(r)) == 40, r
    datasets = json.loads((ROOT / "e2" / "env" / "datasets.json").read_text())
    assert len(datasets["student.zip"]["sha256"]) == 64


def test_compare_packages_is_order_insensitive_and_reports_differences():
    ok, diff = RI.compare_packages("b==2\nA==1\n", "a==1\nb==2\n".replace("a==1", "A==1"))
    assert ok and diff == []
    ok, diff = RI.compare_packages("numpy==2.0.0\nscipy==1.14.0\n", "numpy==2.0.1\nscipy==1.14.0\n")
    assert not ok and "-numpy==2.0.0" in diff and "+numpy==2.0.1" in diff


def test_sha256_file(tmp_path):
    f = tmp_path / "x.bin"; f.write_bytes(b"abc")
    assert RI.sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_extract_tarball_skips_unsafe_members(tmp_path):
    buf = _io.BytesIO()
    with _tarfile.open(fileobj=buf, mode="w:gz") as tf:
        def add(name, data=b"x", kind=_tarfile.REGTYPE, link=""):
            ti = _tarfile.TarInfo(name); ti.type = kind; ti.linkname = link; ti.size = len(data) if kind == _tarfile.REGTYPE else 0
            tf.addfile(ti, _io.BytesIO(data) if kind == _tarfile.REGTYPE else None)
        add("owner-repo-abc1234/ok.py", b"print(1)\n")
        add("../evil.py")
        add("owner-repo-abc1234/abs_link", kind=_tarfile.SYMTYPE, link="/etc/passwd")
    dest = tmp_path / "dest"; dest.mkdir()
    skipped = RI.extract_tarball(buf.getvalue(), dest)
    assert (dest / "owner-repo-abc1234" / "ok.py").read_text() == "print(1)\n"
    assert not (tmp_path / "evil.py").exists() and not (dest / "owner-repo-abc1234" / "abs_link").exists()
    assert skipped == 2


def test_restore_dry_run_touches_nothing(capsys):
    assert RI.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "uvlock" in out and "student.zip" in out
