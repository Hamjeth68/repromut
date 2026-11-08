import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from repromut.fingerprint import (DECIMALS, fingerprint_array, fingerprint_json,
                                  fingerprint_stage, normalize, stage_allclose)

floats = arrays(np.float64, st.integers(1, 50),
                elements=st.floats(-1e6, 1e6, allow_nan=False))


@given(floats)
@settings(max_examples=200, deadline=None)
def test_fingerprint_is_deterministic_and_copy_invariant(a):
    assert fingerprint_array(a) == fingerprint_array(a.copy())


@given(floats)
@settings(max_examples=200, deadline=None)
def test_fingerprint_equals_fingerprint_of_rounded(a):
    assert fingerprint_array(a) == fingerprint_array(np.round(a, DECIMALS))


def test_negative_zero_and_nan_are_canonical():
    assert fingerprint_array(np.array([0.0, np.nan])) == fingerprint_array(np.array([-0.0, np.nan]))


def test_integer_widths_are_equivalent():
    assert fingerprint_array(np.array([1, 2], np.int32)) == fingerprint_array(np.array([1, 2], np.int64))


def test_shape_is_part_of_fingerprint():
    a = np.arange(6.0)
    assert fingerprint_array(a) != fingerprint_array(a.reshape(2, 3))


def test_meaningful_change_alters_fingerprint():
    a = np.linspace(0, 1, 10)
    b = a.copy()
    b[3] += 1e-6
    assert fingerprint_array(a) != fingerprint_array(b)


def test_unsupported_dtype_rejected():
    import pytest
    with pytest.raises(TypeError):
        normalize(np.array(["a"]))


def test_stage_fingerprint_independent_of_key_order():
    a, b = np.arange(3.0), np.arange(4)
    assert fingerprint_stage({"x": a, "y": b}) == fingerprint_stage({"y": b, "x": a})


def test_json_fingerprint_independent_of_key_order():
    assert fingerprint_json({"a": 1, "b": [1, 2]}) == fingerprint_json({"b": [1, 2], "a": 1})


def test_allclose_tolerance_and_structure():
    a = {"x": np.array([1.0, 2.0])}
    assert stage_allclose(a, {"x": np.array([1.0, 2.0 + 1e-12])})
    assert not stage_allclose(a, {"x": np.array([1.0, 2.0 + 1e-6])})
    assert not stage_allclose(a, {"z": np.array([1.0, 2.0])})
    assert not stage_allclose(a, {"x": np.array([1.0])})
