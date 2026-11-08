import pytest

from repromut.auditors import (audit_combined, audit_dynamic, audit_none, audit_seed_only,
                               audit_static, make_record)
from repromut.experiments import build_catalog
from repromut.mutations import BY_ID
from repromut.runner import execute, write_package


@pytest.fixture(scope="module")
def logreg():
    spec = next(s for s in build_catalog() if s.config["name"] == "bin-logreg-balanced")
    return spec, make_record(spec.config, execute(spec))


def _pkg(tmp_path, spec, mutation=None):
    if mutation:
        spec = BY_ID[mutation].apply(spec)
    return write_package(spec, tmp_path / (mutation or "baseline"))


def test_unmutated_package_passes_every_auditor(tmp_path, logreg):
    spec, record = logreg
    pkg = _pkg(tmp_path, spec)
    for audit in (audit_none, audit_seed_only, audit_static, audit_dynamic, audit_combined):
        assert not audit(pkg, record).flagged, audit.__name__


def test_seed_only_catches_unset_seeds_but_not_hidden_override(tmp_path, logreg):
    spec, record = logreg
    v = audit_seed_only(_pkg(tmp_path, spec, "seed_unset"), record)
    assert v.flagged and v.stage == "data"
    assert not audit_seed_only(_pkg(tmp_path, spec, "env_override"), record).flagged


def test_static_misses_stale_cache_dynamic_localises_it(tmp_path, logreg):
    spec, record = logreg
    pkg = _pkg(tmp_path, spec, "stale_cache")
    assert not audit_static(pkg, record).flagged
    v = audit_dynamic(pkg, record)
    assert v.flagged and v.stage == "preprocess"


def test_dynamic_detects_nondeterminism_via_repeats(tmp_path, logreg):
    spec, record = logreg
    v = audit_dynamic(_pkg(tmp_path, spec, "seed_time_derived"), record, repeats=2)
    assert v.flagged and v.stage == "data"


def test_dynamic_ignores_cosmetic_change_static_too(tmp_path, logreg):
    spec, record = logreg
    pkg = _pkg(tmp_path, spec, "notes_added")
    assert not audit_dynamic(pkg, record).flagged
    assert not audit_static(pkg, record).flagged


def test_static_false_positive_on_harmless_thread_change(tmp_path):
    spec = next(s for s in build_catalog() if s.config["name"] == "reg-rf_reg-lownoise")
    record = make_record(spec.config, execute(spec))
    pkg = _pkg(tmp_path, spec, "thread_count_changed")
    assert audit_static(pkg, record).flagged
    assert not audit_dynamic(pkg, record).flagged


def test_combined_uses_dynamic_stage(tmp_path, logreg):
    spec, record = logreg
    v = audit_combined(_pkg(tmp_path, spec, "train_eval_mismatch"), record)
    assert v.flagged and v.stage == "preprocess"


def test_dynamic_rejects_zero_repeats(tmp_path, logreg):
    spec, record = logreg
    with pytest.raises(ValueError):
        audit_dynamic(_pkg(tmp_path, spec), record, repeats=0)
