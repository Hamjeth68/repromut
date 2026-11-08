import json

import numpy as np
import pytest

from repromut import STAGES
from repromut.experiments import build_catalog, derive_seed
from repromut.fingerprint import stage_allclose
from repromut.runner import (apply_overrides, execute, parse_dotenv, read_package,
                             resolve_seed, run_package, write_package)
from repromut import simlib


@pytest.fixture(scope="module")
def catalog():
    return build_catalog()


def test_catalog_shape(catalog):
    names = [s.config["name"] for s in catalog]
    assert len(names) == 28 and len(set(names)) == 28
    assert {s.config["task"] for s in catalog} == {"binary", "multiclass", "regression", "clustering"}


def test_seed_derivation_is_stable():
    assert derive_seed("x", "data") == derive_seed("x", "data")
    assert derive_seed("x", "data") != derive_seed("x", "split")


@pytest.mark.parametrize("idx", range(28))
def test_every_baseline_is_deterministic(catalog, idx):
    spec = catalog[idx]
    a, b = execute(spec), execute(spec)
    for s in STAGES:
        assert stage_allclose(a.arrays[s], b.arrays[s], atol=0, rtol=0), (spec.config["name"], s)


def test_package_round_trip(tmp_path, catalog):
    spec = catalog[0].copy()
    spec.dotenv = {"REPROMUT_OVERRIDE__model__params__C": "0.5"}
    spec.cache = {"Xtr": np.zeros((2, 2)), "Xte": np.ones((1, 2))}
    write_package(spec, tmp_path)
    back = read_package(tmp_path)
    assert back.config == spec.config
    assert back.dotenv == spec.dotenv
    assert np.array_equal(back.cache["Xte"], spec.cache["Xte"])


def test_disk_and_memory_execution_agree(tmp_path, catalog):
    spec = catalog[5]
    write_package(spec, tmp_path)
    a, b = execute(spec), run_package(tmp_path)
    assert a.metrics == b.metrics


def test_reversed_key_order_is_cosmetic(tmp_path, catalog):
    spec = catalog[0].copy()
    spec.key_order_reversed = True
    write_package(spec, tmp_path)
    raw = json.loads((tmp_path / "experiment.json").read_text())
    assert list(raw)[0] == list(spec.config)[-1]
    assert raw == spec.config


def test_overrides_and_dotenv_parsing():
    env = parse_dotenv("# comment\nREPROMUT_OVERRIDE__model__params__C=0.01\nOTHER=1\n\n")
    cfg = apply_overrides({"model": {"params": {"C": 1.0}}}, env)
    assert cfg["model"]["params"]["C"] == 0.01


def test_runner_ignores_process_environment(monkeypatch, catalog):
    spec = catalog[0]
    base = execute(spec).metrics
    monkeypatch.setenv("REPROMUT_OVERRIDE__model__params__C", "0.0001")
    assert execute(spec).metrics == base


def test_seed_resolution():
    assert resolve_seed(5) == 5
    assert resolve_seed(None) is None
    assert isinstance(resolve_seed("time"), int)
    with pytest.raises(ValueError):
        resolve_seed("seven")
    with pytest.raises(ValueError):
        resolve_seed(True)


def test_simlib_default_changes_at_2():
    assert simlib.default_scaler("1.4.1") == "standard"
    assert simlib.default_scaler("2.0.0") == "robust"
    with pytest.raises(ValueError):
        simlib.parse_version("2.x")
