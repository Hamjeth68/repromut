"""Tests for e3/screening/snapshot.py. No network: a fake search endpoint stands in for GitHub."""
from __future__ import annotations

import json
import random
import re
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "e3" / "screening"))
import snapshot as SN  # noqa: E402


def _item(name: str, i: int) -> dict:
    return {"id": i, "full_name": name, "html_url": f"https://github.com/{name}", "description": None,
            "created_at": "2024-01-01T00:00:00Z", "pushed_at": "2024-02-01T00:00:00Z", "default_branch": "main",
            "archived": False, "fork": False, "language": "Python",
            "license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"}, "size": 10,
            "stargazers_count": 1, "topics": ["scikit-learn"]}


class FakeSearch:
    """A stand-in for GitHub search over a fixed dataset: {base query: [(name, created date)]}.
    Honours created:a..b, pages of 100, and can make page 2+ unreliable like the real endpoint."""
    def __init__(self, data, incomplete_first=0, flaky_pages=False):
        self.data, self.incomplete_left, self.flaky = data, incomplete_first, flaky_pages
        self.calls = []

    def __call__(self, q: str, page: int) -> dict:
        self.calls.append((q, page))
        m = re.search(r" created:(\S+)\.\.(\S+)$", q)
        base, (a, b) = q[:m.start()], m.groups()
        rows = sorted(n for n, c in self.data.get(base, []) if a <= c <= b)
        chunk = rows[(page - 1) * SN.PER_PAGE: page * SN.PER_PAGE]
        if self.flaky and page > 1:
            chunk = rows[:5] + chunk[5:]          # later pages repeat earlier results, as observed live
        inc = False
        if self.incomplete_left > 0:
            self.incomplete_left -= 1
            inc = True
        return {"total_count": len(rows), "incomplete_results": inc,
                "items": [_item(n, zlib.crc32(n.encode())) for n in chunk]}


def dated(prefix: str, n: int, start="2024-01-01", days=300):
    import datetime as _dt
    d0 = _dt.date.fromisoformat(start)
    return [(f"{prefix}/r{i:04d}", (d0 + _dt.timedelta(days=i % days)).isoformat()) for i in range(n)]


# ----------------------------------------------------------------------------- protocol consistency
def test_queries_match_the_protocol_text():
    text = (ROOT / "e3" / "E3-PROTOCOL-DRAFT.md").read_text()
    blocks = re.findall(r"```\n(.*?)```", text, re.S)
    tokens = lambda s: set(s.split())
    p4_block = next(b for b in blocks if "topic:scikit-learn" in b and "stars:<10" in b)
    p5_block = next(b for b in blocks if "topic:<T>" in b)
    assert tokens(SN.query(SN.P4_BASE, SN.WINDOW)) == tokens(p4_block)
    assert tokens(SN.query("topic:<T> " + SN.P5_BASE, SN.WINDOW)) == tokens(p5_block)


def test_slices_and_seeds_match_the_protocol():
    p4 = [s for s in SN.SLICES if s[0] == "P4"]
    p5 = [s for s in SN.SLICES if s[0] == "P5"]
    assert [s[3] for s in p4] == [("2018-01-01", "2022-12-31"), ("2023-01-01", "2023-12-31"),
                                  ("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-06-30"),
                                  ("2025-07-01", "2025-12-31"), ("2026-01-01", "2026-03-31"),
                                  ("2026-04-01", "2026-06-30")]
    assert len(p5) == 8
    assert {s[2].split()[0] for s in p5} == {"topic:random-forest", "topic:xgboost", "topic:regression",
                                             "topic:logistic-regression", "topic:feature-engineering",
                                             "topic:supervised-learning", "topic:classification"}
    assert SN.seed_of(SN.SEED_TEXT["P4"]) == 701390840 and SN.seed_of(SN.SEED_TEXT["P5"]) == 3756357948
    assert "701390840" in (ROOT / "e3" / "E3-PROTOCOL-DRAFT.md").read_text()


def test_halve_gives_inclusive_non_overlapping_halves():
    assert SN.halve(("2026-04-01", "2026-06-30")) == [("2026-04-01", "2026-05-16"), ("2026-05-17", "2026-06-30")]
    with pytest.raises(ValueError):
        SN.halve(("2026-04-01", "2026-04-01"))


# ----------------------------------------------------------------------------- fetching
def test_small_slice_is_one_query_and_verified():
    get = FakeSearch({"B": dated("o", 60)})
    s = SN.fetch_slice("P4", "P4-x", "B", ("2024-01-01", "2024-12-31"), get, log=lambda m: None)
    assert s["verified"] and s["n_items"] == 60 and s["total_count"] == 60 and len(s["parts"]) == 1
    assert all(page == 1 for _, page in get.calls)
    assert set(s["items"][0]) >= {"id", "fullName", "url", "license", "stargazersCount", "description"}


def test_large_slice_is_split_until_each_part_fits_one_page_never_paginating():
    get = FakeSearch({"B": dated("o", 450)}, flaky_pages=True)     # pagination would corrupt this
    s = SN.fetch_slice("P4", "P4-x", "B", ("2024-01-01", "2024-12-31"), get, log=lambda m: None)
    assert s["verified"] and s["n_items"] == 450 and len(s["parts"]) >= 5
    assert all(p["total_count"] <= SN.PER_PAGE for p in s["parts"])
    assert all(page == 1 for _, page in get.calls)
    ranges = [tuple(p["created"]) for p in s["parts"]]               # parts partition the slice range
    assert ranges[0][0] == "2024-01-01" and ranges[-1][1] == "2024-12-31"
    import datetime as _dt
    for (a1, b1), (a2, b2) in zip(ranges, ranges[1:]):
        assert _dt.date.fromisoformat(b1) + _dt.timedelta(days=1) == _dt.date.fromisoformat(a2)


def test_incomplete_results_are_retried():
    get = FakeSearch({"B": dated("o", 30)}, incomplete_first=2)
    s = SN.fetch_slice("P4", "P4-x", "B", ("2024-01-01", "2024-12-31"), get, log=lambda m: None)
    assert s["verified"] and s["parts"][0]["attempts"] == 2


def test_single_day_over_one_page_falls_back_to_pagination_and_reports_it():
    rows = [(f"o/r{i:03d}", "2024-05-05") for i in range(150)]
    get = FakeSearch({"B": rows}, flaky_pages=True)
    s = SN.fetch_slice("P4", "P4-x", "B", ("2024-05-05", "2024-05-05"), get, log=lambda m: None)
    assert not s["verified"] and not s["parts"][0]["fits_one_page"]   # flagged, never silently accepted
    ok = SN.fetch_slice("P4", "P4-x", "B", ("2024-05-05", "2024-05-05"), FakeSearch({"B": rows}), log=lambda m: None)
    assert ok["verified"] and ok["n_items"] == 150


# ----------------------------------------------------------------------------- order
def _slice(names):
    return {"items": [SN.normalise(_item(n, i)) for i, n in enumerate(names)]}


def test_build_order_dedupes_removes_e2_and_shuffles_with_the_registered_seed():
    s1, s2 = _slice(["X/One", "o/two", "o/three"]), _slice(["o/two", "o/four"])
    o = SN.build_order("P4", [s1, s2], e2_names={"x/one"}, p4_order=None)
    assert o["n_in_snapshot"] == 4 and o["removed_already_screened_in_e2"] == ["x/one"] and o["n_ordered"] == 3
    expected = sorted(["o/two", "o/three", "o/four"])
    random.Random(701390840).shuffle(expected)
    assert [r["fullName"].lower() for r in o["repositories"]] == expected
    assert [r["order"] for r in o["repositories"]] == [0, 1, 2]


def test_p5_order_excludes_p4_by_name_and_by_id():
    p4 = [dict(SN.normalise(_item("o/shared", 7)), order=0), dict(SN.normalise(_item("o/renamed-old", 99)), order=1)]
    p5_items = [SN.normalise(_item("O/Shared", 7)), SN.normalise(_item("o/renamed-new", 99)), SN.normalise(_item("o/only-p5", 5))]
    o = SN.build_order("P5", [{"items": p5_items}], e2_names=set(), p4_order=p4)
    assert o["removed_in_p4"] == ["o/renamed-new", "o/shared"]
    assert [r["fullName"] for r in o["repositories"]] == ["o/only-p5"] and o["seed"] == 3756357948


# ----------------------------------------------------------------------------- refusals and full run
def _isolate(monkeypatch, tmp_path, clean=True):
    monkeypatch.setattr(SN, "OUT", tmp_path / "screening")
    monkeypatch.setattr(SN, "SNAP", tmp_path / "screening" / "snapshot")
    monkeypatch.setattr(SN, "protocol_state", lambda: {"git_head": "abc1234", "protocol_tracked": True,
                                                        "protocol_clean": clean})
    monkeypatch.delenv("REPROMUT_GITHUB_TOKEN", raising=False)


def test_refuses_when_protocol_has_local_changes(monkeypatch, tmp_path, capsys):
    _isolate(monkeypatch, tmp_path, clean=False)
    assert SN.main(["--dry-run"]) == 2 and "must be committed" in capsys.readouterr().out


def test_dry_run_fetches_nothing(monkeypatch, tmp_path, capsys):
    _isolate(monkeypatch, tmp_path)
    def boom(q, page):
        raise AssertionError("network used in dry run")
    assert SN.main(["--dry-run"], get=boom) == 0
    assert not (tmp_path / "screening").exists()


def test_full_run_saves_snapshot_and_orders_then_refuses_to_overwrite(monkeypatch, tmp_path, capsys):
    _isolate(monkeypatch, tmp_path)
    data: dict[str, list] = {}
    for pop, name, base, created in SN.SLICES:
        data.setdefault(base, []).extend((f"{name.lower()}/repo{i}", created[0]) for i in range(3))
    data[SN.P4_BASE].append(("fmind/mlops-python-package", "2020-06-01"))              # screened in E2
    assert SN.main([], get=FakeSearch(data)) == 0
    man = json.loads((tmp_path / "screening" / "snapshot" / "MANIFEST.json").read_text())
    assert man["all_slices_verified"] and len(man["slices"]) == 15 and man["authenticated"] is False
    assert "REPROMUT_GITHUB_TOKEN" not in json.dumps(man)
    p4 = json.loads((tmp_path / "screening" / "P4" / "order.json").read_text())
    assert p4["n_in_snapshot"] == 22 and p4["removed_already_screened_in_e2"] == ["fmind/mlops-python-package"]
    assert p4["n_ordered"] == 21
    first = (tmp_path / "screening" / "P4" / "order.json").read_text()
    assert SN.main(["--order-only"]) == 0                                   # rebuilds identically
    assert (tmp_path / "screening" / "P4" / "order.json").read_text() == first
    assert SN.main([]) == 2 and "already exists" in capsys.readouterr().out
