"""Output adapters: turn a run's stdout and declared output files into named float64 arrays.

Only data formats are parsed (text, CSV, JSON, NPY, NPZ). Pickles are never loaded on the
host; they are summarised inside the container by `pickle_extractor.py` and arrive as JSON.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, field

import numpy as np

import re

from repromut.external import extract_numbers as _e1_extract_numbers

# Pilot adapter fix (DEVIATIONS D1): lines carrying a wall-clock time stamp (e.g. "[03:49:44] WARNING")
# are excluded in addition to E1's TIMING_RE lines. A clock reading is not an experiment result.
CLOCK_RE = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")
# Pilot adapter fix (DEVIATIONS D5): lines reporting registry/run identifiers ("Model version: 2",
# "run_id ...") carry bookkeeping numbers, not experiment results.
IDENT_RE = re.compile(r"(?i)\bversion\b|\brun[_ ]?id\b")
# D9 (registered before the remaining repositories' outcome runs): calendar date stamps, e.g. run folders
# named "20261109-101010" or log dates "2026-11-09", are bookkeeping, not results.
DATE_RE = re.compile(r"\b20\d{2}-?[01]\d-?[0-3]\d[-_T]\d{6}\b|\b20\d{2}-[01]\d-[0-3]\d\b")


def extract_numbers(text: str) -> list[float]:
    keep = (l for l in text.splitlines() if not (CLOCK_RE.search(l) or IDENT_RE.search(l) or DATE_RE.search(l)))
    return _e1_extract_numbers("\n".join(keep))

RTOL = 1e-6
ATOL = 1e-9
DECIMALS = 8
MAX_BYTES = 5 * 1024 * 1024


@dataclass
class AdapterSpec:
    """Registered per repository before outcome runs (protocol section 6)."""
    stdout: bool = True
    files: list[str] = field(default_factory=list)      # declared output paths, relative to the work copy
    convert: list[str] = field(default_factory=list)    # parquet/pickle: converted in-container, never loaded on the host

    @classmethod
    def from_dict(cls, d: dict) -> "AdapterSpec":
        return cls(stdout=d.get("stdout", True), files=list(d.get("files", [])),
                   convert=list(d.get("convert", [])) + list(d.get("pickles", [])))


def _canon(a) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64).ravel().copy()
    a[a == 0] = 0.0          # -0.0 -> 0.0; NaN stays NaN and is compared with equal_nan
    return a


def _json_numbers(obj, out: list[float]) -> None:
    if isinstance(obj, (bool, int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for k in sorted(obj, key=str):
            _json_numbers(obj[k], out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _json_numbers(v, out)
    # strings and None carry no numeric result


def _csv_numbers(text: str) -> list[float]:
    out: list[float] = []
    for row in csv.reader(io.StringIO(text)):
        for cell in row:
            try:
                out.append(float(cell))
            except ValueError:
                continue
    return out


def parse_file(name: str, data: bytes) -> dict[str, np.ndarray]:
    """Parse one declared output file into named arrays. Unknown formats raise ValueError."""
    data = data[:MAX_BYTES]
    low = name.lower()
    if low.endswith(".npy"):
        return {name: _canon(np.load(io.BytesIO(data), allow_pickle=False))}
    if low.endswith(".npz"):
        with np.load(io.BytesIO(data), allow_pickle=False) as z:
            return {f"{name}:{k}": _canon(z[k]) for k in sorted(z.files)}
    text = data.decode("utf-8", errors="replace")
    if low.endswith(".json"):
        nums: list[float] = []
        _json_numbers(json.loads(text), nums)
        return {name: _canon(nums)}
    if low.endswith(".csv"):
        return {name: _canon(_csv_numbers(text))}
    if low.endswith((".txt", ".log", ".yaml", ".yml")):
        return {name: _canon(extract_numbers(text))}
    raise ValueError(f"no adapter for {name}")


def collect(spec: AdapterSpec, stdout: str, files: dict[str, bytes],
            converted: dict[str, list | None] | None = None) -> dict[str, np.ndarray]:
    """Normalised outputs in the adapter's declared order. A missing declared file is an explicit NaN marker."""
    out: dict[str, np.ndarray] = {}
    if spec.stdout:
        out["stdout"] = _canon(extract_numbers(stdout[:MAX_BYTES]))
    for name in spec.files:
        if name in files:
            out.update(parse_file(name, files[name]))
        else:
            out[f"{name}:<missing>"] = np.array([np.nan])
    for name in spec.convert:
        vals = (converted or {}).get(name)
        out[f"{name}:<converted>"] = _canon([np.nan if v is None else v for v in vals] if vals is not None else [np.nan])
    return out


def first_difference(a: dict[str, np.ndarray], b: dict[str, np.ndarray],
                     rtol: float = RTOL, atol: float = ATOL) -> str | None:
    """Name of the first differing artifact in declared order, or None if all agree within tolerance."""
    for k in list(a) + [k for k in b if k not in a]:
        if k not in a or k not in b:
            return k
        x, y = a[k], b[k]
        if x.shape != y.shape or not np.allclose(x, y, rtol=rtol, atol=atol, equal_nan=True):
            return k
    return None


def equal(a: dict[str, np.ndarray], b: dict[str, np.ndarray],
          rtol: float = RTOL, atol: float = ATOL) -> bool:
    return first_difference(a, b, rtol, atol) is None


def fingerprint(outputs: dict[str, np.ndarray], decimals: int = DECIMALS) -> str:
    """SHA-256 of 8-decimal-rounded outputs (auditor D's fingerprint, as in E1)."""
    h = hashlib.sha256()
    for k, v in outputs.items():
        arr = np.round(v, decimals)
        arr[arr == 0] = 0.0
        h.update(k.encode())
        h.update(json.dumps([None if math.isnan(x) else x for x in arr.tolist()]).encode())
    return h.hexdigest()


def to_jsonable(outputs: dict[str, np.ndarray]) -> dict[str, list]:
    return {k: [None if math.isnan(x) else x for x in v.tolist()] for k, v in outputs.items()}


def from_jsonable(d: dict[str, list]) -> dict[str, np.ndarray]:
    return {k: np.array([np.nan if x is None else x for x in v], dtype=np.float64) for k, v in d.items()}
