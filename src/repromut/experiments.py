"""The fixed catalog of baseline experiment packages (28 in v0.1).

Seeds follow a documented hierarchy: every seed is derived from
``MASTER_SEED`` via SHA-256 of ``"<master>/<experiment>/<role>"``, so any seed
can be recomputed from the experiment name alone.
"""

from __future__ import annotations

import hashlib

from .runner import PackageSpec
from . import simlib

MASTER_SEED = 20261108
SCHEMA_VERSION = "0.1"


def derive_seed(experiment: str, role: str, master: int = MASTER_SEED) -> int:
    digest = hashlib.sha256(f"{master}/{experiment}/{role}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


CLASSIFIERS = {
    "logreg": {"max_iter": 1000, "tol": 1e-6, "C": 1.0},
    "rf_clf": {"n_estimators": 50, "n_jobs": 1},
    "knn_clf": {"n_neighbors": 7, "weights": "distance", "n_jobs": 1},
    "gnb": {"var_smoothing": 1e-9},
}
REGRESSORS = {
    "ridge": {"alpha": 1.0},
    "rf_reg": {"n_estimators": 50, "n_jobs": 1},
    "knn_reg": {"n_neighbors": 7, "weights": "distance", "n_jobs": 1},
    "sgd_reg": {"max_iter": 2000, "tol": 1e-6, "alpha": 1e-4},
}
CLUSTERERS = {
    "kmeans": {"n_clusters": 3, "n_init": 3, "max_iter": 300, "tol": 1e-6},
    "gmm": {"n_components": 3, "max_iter": 200, "tol": 1e-6},
}


def _base(name: str, task: str, data: dict, model: str, params: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "run_name": f"{name}-run",
        "output_dir": "outputs",
        "notes": "",
        "logging": {"level": "INFO"},
        "task": task,
        "seeds": {r: derive_seed(name, r) for r in ("data", "split", "model")},
        "data": data,
        "split": {"test_size": 0.3},
        "preprocess": {"scaler": "default", "use_cache": True},
        "model": {"name": model, "params": dict(params)},
        "evaluation": {"refit_scaler_on_test": False},
        "dependencies": {"simlib": ">=1.0"},
    }


def _clf_data(n_classes: int, imbalanced: bool) -> dict:
    weights = None
    if imbalanced:
        weights = [0.85] if n_classes == 2 else [0.6, 0.3]
    return {"n_samples": 400, "n_features": 10, "n_informative": 5,
            "n_redundant": 2, "n_classes": n_classes, "weights": weights,
            "flip_y": 0.01, "class_sep": 1.0, "dtype": "float64",
            "row_order": "as_generated"}


def build_catalog() -> list[PackageSpec]:
    specs: list[PackageSpec] = []
    for task, n_classes in (("binary", 2), ("multiclass", 3)):
        for model, params in CLASSIFIERS.items():
            for variant in ("balanced", "imbalanced"):
                name = f"{task[:3]}-{model}-{variant}"
                data = _clf_data(n_classes, variant == "imbalanced")
                specs.append(PackageSpec(_base(name, task, data, model, params)))
    for model, params in REGRESSORS.items():
        for variant, noise in (("lownoise", 5.0), ("highnoise", 25.0)):
            name = f"reg-{model}-{variant}"
            data = {"n_samples": 400, "n_features": 10, "n_informative": 5,
                    "noise": noise, "dtype": "float64", "row_order": "as_generated"}
            specs.append(PackageSpec(_base(name, "regression", data, model, params)))
    for model, params in CLUSTERERS.items():
        for variant, std in (("separated", 1.0), ("overlapping", 3.0)):
            name = f"clu-{model}-{variant}"
            data = {"n_samples": 400, "n_features": 5, "centers": 3,
                    "cluster_std": std, "center_box": [-10.0, 10.0],
                    "dtype": "float64", "row_order": "as_generated"}
            specs.append(PackageSpec(_base(name, "clustering", data, model, params)))
    for s in specs:
        s.runtime_env = {"simlib": simlib.DEFAULT_VERSION}
    return specs
