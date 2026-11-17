"""Tests for e3/screening/screen.py. No network: a fake GitHub stands in; E2's real rules are used."""
from __future__ import annotations

import io
import json
import sys
import tarfile
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e3" / "screening"))
import screen as SC  # noqa: E402

needs_filter = pytest.mark.skipif(not hasattr(tarfile, "data_filter"), reason="tarfile 'data' filter needed")

GOOD = ("import os\nimport pandas as pd\nfrom sklearn.linear_model import LogisticRegression\n"
        "def main():\n    df = pd.read_csv('data/train.csv')\n    print(LogisticRegression().fit(df[['a']], df['b']).score(df[['a']], df['b']))\n"
        "if __name__ == '__main__':\n    main()\n")
NO_SKLEARN = "print('hello')\nif __name__ == '__main__':\n    pass\n"
X6 = GOOD.replace("import os\n", "import os\nfrom sklearn.datasets import fetch_openml\nX = fetch_openml('iris')\n")


def tarball(name: str, sha: str, files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    top = f"{name.replace('/', '-')}-{sha[:7]}"
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for rel, text in files.items():
            data = text.encode()
            ti = tarfile.TarInfo(f"{top}/{rel}"); ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


class FakeGitHub:
    def __init__(self, repos: dict[str, dict[str, str]], fail_first: set[str] = frozenset(), always_fail: set[str] = frozenset()):
        self.repos, self.fail_first, self.always_fail, self.calls = repos, set(fail_first), set(always_fail), []

    def __call__(self, path: str, raw: bool = False):
        self.calls.append(path)
        parts = path.split("/")
        name = f"{parts[1]}/{parts[2]}"
        if name in self.always_fail or (name in self.fail_first and path.endswith("tarball/" + "a" * 40)):
            if name in self.fail_first:
                self.fail_first.discard(name)
            raise RuntimeError("HTTP 502 for " + path)
        if len(parts) == 3:
            return {"license": {"spdx_id": "MIT"}, "default_branch": "main"}
        if parts[3] == "license":
            return {"path": "LICENSE"}
        if parts[3] == "commits":
            return {"sha": "a" * 40}
        if parts[3] == "tarball":
            return tarball(name, parts[4], self.repos[name])
        raise AssertionError(path)


def meta(name: str, order: int) -> dict:
    return {"id": order, "fullName": name, "url": f"https://github.com/{name}", "description": "a small ML project",
            "stargazersCount": 1, "license": {"key": "mit"}, "order": order}


@pytest.fixture
def env(tmp_path, monkeypatch):
    out = tmp_path / "e3" / "screening"
    (out / "P4").mkdir(parents=True)
    monkeypatch.setattr(SC, "OUT", out)
    monkeypatch.setattr(SC, "WORK", tmp_path / "work")
    monkeypatch.setattr(SC, "committed_and_clean", lambda p: True)
    monkeypatch.delenv("REPROMUT_GITHUB_TOKEN", raising=False)
    def write_order(names):
        (out / "P4" / "order.json").write_text(json.dumps({"repositories": [meta(n, i) for i, n in enumerate(names)]}))
    return out, tmp_path / "work", write_order


def records(out):
    return [json.loads(l) for l in (out / "P4" / "screening.jsonl").read_text().splitlines()]


def test_loads_e2_rules_unchanged_and_leaves_argv_alone():
    before = list(sys.argv)
    ps = SC.load_e2_rules()
    assert sys.argv == before
    assert callable(ps.screen) and ps.HIGH_STAKES.search("phishing detector") and "hamjeth68" in ps.OWN_ACCOUNTS
    assert "max_features" not in " ".join(ps.DEFAULT_CHANGE)                      # E2 refinement S3 is in


@needs_filter
def test_screening_applies_e2_rules_and_keeps_only_reviewable_sources(env):
    out, work, write_order = env
    repos = {"o/good": {"train.py": GOOD, "LICENSE": "MIT"}, "o/nosk": {"run.py": NO_SKLEARN},
             "o/net": {"train.py": X6}, "hamjeth68/mine": {"train.py": GOOD}}
    write_order(list(repos))
    assert SC.main(["--population", "P4"], gh=FakeGitHub(repos), sleep=lambda s: None) == 0
    recs = {r["repo"]: r for r in records(out)}
    assert recs["o/good"]["static_pass"] and recs["o/good"]["commit"] == "a" * 40
    assert "X12 does not import scikit-learn" in recs["o/nosk"]["reasons"]
    assert recs["o/net"]["reasons"] == SC.X6_ONLY
    assert "X4 own repository" in recs["hamjeth68/mine"]["reasons"]
    src = work / "P4" / "src"
    assert (src / "o__good").exists() and (src / "o__net").exists()                 # pass + X6-only kept
    assert not (src / "o__nosk").exists() and not (src / "hamjeth68__mine").exists()
    assert [r["order"] for r in records(out)] == [0, 1, 2, 3]


@needs_filter
def test_infra_is_retried_once_then_recorded(env):
    out, work, write_order = env
    repos = {"o/flaky": {"train.py": GOOD}, "o/down": {"train.py": GOOD}}
    write_order(list(repos))
    gh = FakeGitHub(repos, fail_first={"o/flaky"}, always_fail={"o/down"})
    assert SC.main([], gh=gh, sleep=lambda s: None) == 0
    recs = {r["repo"]: r for r in records(out)}
    assert recs["o/flaky"]["static_pass"] and "502" in recs["o/flaky"]["first_attempt_error"]
    assert recs["o/down"]["reasons"][0].startswith("INFRA") and not (work / "P4" / "src" / "o__down").exists()


@needs_filter
def test_resumes_and_respects_limit(env):
    out, work, write_order = env
    repos = {f"o/r{i}": {"train.py": GOOD} for i in range(5)}
    write_order(list(repos))
    assert SC.main(["--limit", "2"], gh=FakeGitHub(repos), sleep=lambda s: None) == 0
    assert len(records(out)) == 2
    gh = FakeGitHub(repos)
    assert SC.main([], gh=gh, sleep=lambda s: None) == 0
    assert [r["repo"] for r in records(out)] == list(repos)
    assert not any("o/r0" in c or "o/r1" in c for c in gh.calls)                    # not re-screened


def test_refuses_without_token_or_uncommitted_order(env, monkeypatch, capsys):
    out, work, write_order = env
    write_order(["o/a"])
    monkeypatch.setattr(SC, "HAS_DATA_FILTER", True)
    assert SC.main([]) == 2 and "REPROMUT_GITHUB_TOKEN" in capsys.readouterr().out
    assert SC.main(["--dry-run"]) == 0                                              # dry run needs no token
    monkeypatch.setattr(SC, "committed_and_clean", lambda p: False)
    assert SC.main(["--dry-run"]) == 2 and "must be committed" in capsys.readouterr().out


class _Resp:
    def __init__(self, body, headers):
        self._b, self.headers = body, headers
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_transport_waits_on_rate_limit_and_never_forwards_the_token():
    seen, slept = [], []
    def fake_urlopen(req, timeout):
        seen.append(req)
        if len(seen) == 1:
            raise urllib.error.HTTPError(req.full_url, 403, "rate limited",
                                         {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"}, None)
        return _Resp(b'{"ok": true}', {"X-RateLimit-Remaining": "4999"})
    gh = SC.GitHub("secret-token", urlopen=fake_urlopen, sleep=slept.append)
    assert gh("repos/o/a") == {"ok": True} and len(slept) == 1
    req = seen[-1]
    assert req.unredirected_hdrs.get("Authorization") == "Bearer secret-token"
    assert "Authorization" not in req.headers                                       # dropped on redirects
    with pytest.raises(RuntimeError, match="HTTP 404"):
        SC.GitHub("t", urlopen=lambda r, timeout: (_ for _ in ()).throw(
            urllib.error.HTTPError(r.full_url, 404, "nf", {}, None)), sleep=lambda s: None)("repos/o/gone")


def test_refuses_on_python_without_tarfile_data_filter(env, monkeypatch, capsys):
    out, work, write_order = env
    write_order(["o/a"])
    monkeypatch.setattr(SC, "HAS_DATA_FILTER", False)
    assert SC.main(["--dry-run"]) == 2 and "data' filter" in capsys.readouterr().out
