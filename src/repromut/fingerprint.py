"""Normalised array fingerprints and tolerance comparisons.

Two comparison modes are deliberately kept separate:

* ``fingerprint_*`` -- cheap SHA-256 hashes of arrays rounded to ``DECIMALS``.
  This is what a practical auditor can store and compare. It can, in rare
  cases, disagree with a tolerance comparison when a value sits on a rounding
  boundary.
* ``stage_allclose`` -- full-array comparison with absolute/relative
  tolerances. The benchmark oracle uses this as ground truth.
"""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

import numpy as np

DECIMALS = 8
ORACLE_ATOL = 1e-9
ORACLE_RTOL = 1e-9


def normalize(arr) -> np.ndarray:
    a = np.asarray(arr)
    if a.dtype.kind in "fc":
        a = np.round(a.astype(np.float64), DECIMALS)
        a[a == 0] = 0.0  # collapse -0.0 to 0.0
        a[np.isnan(a)] = np.nan  # canonical NaN payload
    elif a.dtype.kind in "iub":
        a = a.astype(np.int64)
    else:
        raise TypeError(f"unsupported dtype for fingerprinting: {a.dtype}")
    return np.ascontiguousarray(a)


def fingerprint_array(arr) -> str:
    a = normalize(arr)
    h = hashlib.sha256()
    h.update(str(a.dtype).encode())
    h.update(json.dumps(list(a.shape)).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def fingerprint_stage(arrays: Mapping[str, np.ndarray]) -> str:
    h = hashlib.sha256()
    for name in sorted(arrays):
        h.update(name.encode())
        h.update(fingerprint_array(arrays[name]).encode())
    return h.hexdigest()


def fingerprint_json(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def stage_allclose(
    a: Mapping[str, np.ndarray],
    b: Mapping[str, np.ndarray],
    atol: float = ORACLE_ATOL,
    rtol: float = ORACLE_RTOL,
) -> bool:
    if set(a) != set(b):
        return False
    for name in a:
        x, y = np.asarray(a[name]), np.asarray(b[name])
        if x.shape != y.shape:
            return False
        if x.dtype.kind in "fc" or y.dtype.kind in "fc":
            if not np.allclose(x.astype(np.float64), y.astype(np.float64),
                               atol=atol, rtol=rtol, equal_nan=True):
                return False
        elif not np.array_equal(x, y):
            return False
    return True
