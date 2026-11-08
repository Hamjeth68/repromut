"""A simulated third-party library whose defaults change between versions.

Real dependency drift is hard to reproduce deterministically in a benchmark, so
ReproMut models it with this tiny stand-in. Experiment packages declare an
unpinned requirement (``simlib>=1.0``); the execution environment resolves a
concrete version recorded in ``.runtime_env.json``. From version 2.0.0 the
default feature scaler changes from ``standard`` to ``robust``.
"""

from __future__ import annotations

DEFAULT_VERSION = "1.4.0"


def parse_version(version: str) -> tuple[int, ...]:
    parts = version.strip().split(".")
    if not parts or not all(p.isdigit() for p in parts):
        raise ValueError(f"invalid simlib version: {version!r}")
    return tuple(int(p) for p in parts)


def default_scaler(version: str) -> str:
    """Return the scaler used when a config says ``scaler: default``."""
    return "robust" if parse_version(version) >= (2, 0, 0) else "standard"
