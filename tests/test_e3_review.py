"""Tests for e3/screening/review.py: scripted answers stand in for the reviewer; nothing is executed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e3" / "screening"))
import review as RV  # noqa: E402
import screen as SC  # noqa: E402

TRAIN = ("import os\nimport pandas as pd\nfrom sklearn.linear_model import LogisticRegression\n"
         "SEED = int(os.environ.get('SEED', '0'))\n"
         "df = pd.read_csv('data/train.csv')\nprint(LogisticRegression().fit(df[['a']], df['b']).score(df[['a']], df['b']))\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    out, work = tmp_path / "e3" / "screening", tmp_path / "work"
    for pop in ("P4", "P5"):
        (out / pop).mkdir(parents=True)
    monkeypatch.setattr(RV, "OUT", out)
    monkeypatch.setattr(SC, "WORK", work)
    root = tmp_path / "root"
    (root / "e3").mkdir(parents=True)
    (root / "e3" / "E3-PROTOCOL.md").write_text("registered")
    monkeypatch.setattr(RV, "ROOT", root)
    monkeypatch.setattr(SC, "committed_and_clean", lambda p: True)

    def add(pop, repos, x6=()):
        recs, metas = [], []
        for i, (name, files) in enumerate(repos.items()):
            top = work / pop / "src" / name.replace("/", "__") / f"{name.replace('/', '-')}-aaaaaaa"
            for rel, text in files.items():
                (top / rel).parent.mkdir(parents=True, exist_ok=True)
                (top / rel).write_text(text)
            recs.append({"repo": name, "order": i, "commit": "a" * 40, "stars": 1, "license": "MIT", "n_py": 1,
                         "n_ipynb": 0, "entry_candidates": ["train.py"], "channels": {"env": True},
                         "sklearn_pinned": False, "reasons": SC.X6_ONLY if name in x6 else [],
                         "static_pass": name not in x6})
            metas.append({"fullName": name, "description": "demo", "order": i})
        recs.append({"repo": "o/excluded", "order": 99, "reasons": ["X12 does not import scikit-learn"], "static_pass": False})
        (out / pop / "screening.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        (out / pop / "order.json").write_text(json.dumps({"repositories": metas}))
    return out, add


def scripted(answers):
    it = iter(answers)
    return lambda prompt: next(it)


def test_refuses_before_registration(env, monkeypatch):
    out, add = env
    add("P4", {"o/a": {"train.py": TRAIN}})
    monkeypatch.setattr(SC, "committed_and_clean", lambda p: False)
    lines = []
    assert RV.main(["--population", "P4"], read=scripted([]), write=lines.append) == 2
    assert "register the protocol first" in lines[-1]


def test_review_records_decisions_in_order_and_shows_channel_lines(env):
    out, add = env
    add("P4", {"o/a": {"train.py": TRAIN, "README.md": "Demo"}, "o/b": {"train.py": "print(1)\n"}})
    shown = []
    answers = ["e", "python train.py", "", "reads data/train.csv relative to cwd; SEED env var",
               "x", "M6", "no real channel"]
    assert RV.main(["--population", "P4"], read=scripted(answers), write=shown.append) == 0
    d = [json.loads(l) for l in (out / "P4" / "manual_review.jsonl").read_text().splitlines()]
    assert [x["repo"] for x in d] == ["o/a", "o/b"]                                       # seeded order, no skipping
    assert d[0]["decision"] == "eligible" and d[0]["entry_point"] == "python train.py" and d[0]["entry_fingerprints"]
    assert d[1]["decision"] == "exclude" and d[1]["rule"] == "M6"
    text = "\n".join(shown)
    assert "train.py:4: SEED = int(os.environ.get" in text and "train.py:5: df = pd.read_csv('data/train.csv')" in text
    assert "o/excluded" not in text                                                        # only candidates shown


def test_m8_flags_copies_of_accepted_repositories(env):
    out, add = env
    copy = "# my homework\n" + TRAIN.replace("    ", "  ") + "\n\n"
    add("P4", {"o/orig": {"train.py": TRAIN}, "o/copy": {"train.py": copy}, "o/same": {"train.py": TRAIN}})
    answers = ["e", "python train.py", "", "ok", "x", "M8", "copy of o/orig", "x", "M8", "byte copy"]
    shown = []
    RV.main(["--population", "P4"], read=scripted(answers), write=shown.append)
    d = [json.loads(l) for l in (out / "P4" / "manual_review.jsonl").read_text().splitlines()]
    assert any("near-identical" in f and "o/orig" in f for f in d[1]["duplicate_flags"])
    assert any(f.startswith("byte-identical") for f in d[2]["duplicate_flags"])


def test_x6_only_uses_m2_prime_not_m2(env):
    out, add = env
    add("P4", {"o/net": {"train.py": TRAIN + "import urllib.request\nurllib.request.urlretrieve('https://x/y.csv', 'y.csv')\n"}},
        x6=("o/net",))
    shown = []
    answers = ["x", "M2", "M2'", "data URL is not stable"]                                # M2 rejected, M2' accepted
    RV.main(["--population", "P4"], read=scripted(answers), write=shown.append)
    d = json.loads((out / "P4" / "manual_review.jsonl").read_text())
    assert d["rule"] == "M2'" and d["static_result"] == "X6-only"
    assert "Network access (M2')" in "\n".join(shown)


def test_quit_resumes_and_target_stops_review(env, monkeypatch):
    out, add = env
    add("P4", {f"o/r{i}": {"train.py": TRAIN.replace("0", str(i))} for i in range(4)})
    RV.main(["--population", "P4"], read=scripted(["q"]), write=lambda s: None)
    assert not (out / "P4" / "manual_review.jsonl").exists()
    monkeypatch.setattr(RV, "TARGET", 2)
    shown = []
    answers = ["e", "python train.py", "", "ok", "e", "python train.py", "", "ok"]
    RV.main(["--population", "P4"], read=scripted(answers), write=shown.append)
    assert len((out / "P4" / "manual_review.jsonl").read_text().splitlines()) == 2
    assert "Target reached" in shown[-1]


def test_p5_waits_until_p4_is_exhausted_and_status(env):
    out, add = env
    add("P4", {"o/a": {"train.py": TRAIN}})
    add("P5", {"o/z": {"train.py": TRAIN}})
    lines = []
    assert RV.main(["--population", "P5"], read=scripted([]), write=lines.append) == 2
    assert "only after P4" in lines[-1]
    lines = []
    RV.main(["--status"], write=lines.append)
    assert "P4: 2 screened, 1 candidates, 0 reviewed, 0 eligible" in lines[0]
