"""Each mutation changes exactly what it claims, and the oracle confirms labels."""

import pytest

from repromut.auditors import declared_manifest
from repromut.experiments import build_catalog
from repromut.mutations import BY_ID, CATALOG, CONTROL, POSITIVE, applicable
from repromut.oracle import observe
from repromut.runner import execute

CATALOG_SPECS = build_catalog()
CASES = [(s, m) for s in CATALOG_SPECS for m in applicable(s)]


def test_catalog_counts():
    assert sum(m.kind == POSITIVE for m in CATALOG) == 12
    assert sum(m.kind == CONTROL for m in CATALOG) == 7
    assert len(BY_ID) == len(CATALOG)


def test_apply_does_not_mutate_input():
    spec = CATALOG_SPECS[0]
    before = repr(spec.config)
    for m in applicable(spec):
        m.apply(spec)
    assert repr(spec.config) == before and spec.cache is None and not spec.dotenv


def test_inapplicable_mutation_raises():
    clu = next(s for s in CATALOG_SPECS if s.config["task"] == "clustering")
    with pytest.raises(ValueError):
        BY_ID["split_seed_changed"].apply(clu)


COSMETIC = [(s, m) for s, m in CASES if m.family == "cosmetic"]


@pytest.mark.parametrize("spec,mut", COSMETIC,
                         ids=[f"{s.config['name']}:{m.id}" for s, m in COSMETIC])
def test_cosmetic_controls_leave_declared_manifest_unchanged(spec, mut):
    out = mut.apply(spec)
    assert declared_manifest(out.config) == declared_manifest(spec.config)
    assert out.runtime_env == spec.runtime_env and out.cache is None and not out.dotenv


def test_hidden_mutations_do_not_touch_config():
    spec = next(s for s in CATALOG_SPECS if s.config["model"]["name"] == "logreg")
    for mid in ("env_override", "stale_cache", "dependency_default_drift"):
        out = BY_ID[mid].apply(spec)
        assert out.config == spec.config, mid
    assert BY_ID["env_override"].apply(spec).dotenv
    assert BY_ID["stale_cache"].apply(spec).cache is not None
    assert BY_ID["dependency_default_drift"].apply(spec).runtime_env["simlib"] == "2.0.0"


_BASELINES: dict = {}


def _baseline(spec):
    name = spec.config["name"]
    if name not in _BASELINES:
        _BASELINES[name] = execute(spec)
    return _BASELINES[name]


@pytest.mark.slow
@pytest.mark.parametrize("spec,mut", CASES,
                         ids=[f"{s.config['name']}:{m.id}" for s, m in CASES])
def test_oracle_confirms_declared_label_and_stage(spec, mut):
    obs = observe(mut.apply(spec), _baseline(spec), repeats=3)
    if mut.kind == POSITIVE:
        assert obs.result_changed
        assert obs.first_stage == mut.expected_stage
    else:
        assert not obs.result_changed
        assert obs.first_stage is None
