import json
import math

import numpy as np
import pytest

from repromut.cli import main
from repromut.stats import confusion, mcnemar_exact, paired_bootstrap_diff, wilson


def test_wilson_known_values():
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-4)
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    assert all(math.isnan(x) for x in wilson(0, 0))


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(10, 0) == pytest.approx(2 * 0.5 ** 10)


def test_bootstrap_diff_bounds():
    d, lo, hi = paired_bootstrap_diff(np.ones(50), np.zeros(50))
    assert d == lo == hi == 1.0
    with pytest.raises(ValueError):
        paired_bootstrap_diff(np.ones(3), np.ones(2))


def test_confusion():
    c = confusion([True, True, False, False], [True, False, True, False])
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (1, 1, 1, 1)
    assert c["recall"] == c["precision"] == c["fpr"] == 0.5


def test_cli_list(capsys):
    assert main(["list-mutations"]) == 0
    assert "stale_cache" in capsys.readouterr().out


def test_cli_export_and_audit(tmp_path, capsys):
    out = tmp_path / "x"
    assert main(["export", "reg-ridge-lownoise", "--mutation", "env_override",
                 "--out", str(out)]) == 0
    assert main(["audit", str(out / "package"), "--record", str(out / "record.json")]) == 1
    assert "dynamic          flagged=True" in capsys.readouterr().out
    clean = tmp_path / "clean"
    assert main(["export", "reg-ridge-lownoise", "--out", str(clean)]) == 0
    assert main(["audit", str(clean / "package"), "--record", str(clean / "record.json")]) == 0


def test_cli_bench_smoke(tmp_path):
    out = tmp_path / "bench"
    assert main(["bench", "--smoke", "--out", str(out)]) == 0
    summary = json.loads((out / "summary.json").read_text())
    assert summary["n_experiments"] == 3
    assert summary["oracle_agreement"]["agree"] == summary["n_cases"]
    assert set(summary["methods"]) == {"no_audit", "seed_only", "static_manifest",
                                       "dynamic", "combined"}
    assert summary["methods"]["no_audit"]["tp"] == 0
    assert (out / "cases.jsonl").read_text().count("\n") == summary["n_cases"]
