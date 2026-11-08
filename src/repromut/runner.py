"""Execute an experiment package and capture per-stage artifacts.

An experiment package is a directory containing:

* ``experiment.json``     -- the declared configuration (required)
* ``.runtime_env.json``   -- the resolved execution environment (simlib version)
* ``.env``                -- optional ``KEY=VALUE`` lines; keys starting with
                             ``REPROMUT_OVERRIDE__`` silently override config
                             values (a deliberately realistic hidden-config
                             pattern)
* ``.cache/preprocessed.npz`` -- optional cached preprocessing output. When
                             ``preprocess.use_cache`` is true the runner loads
                             it *without validating its key* (a realistic
                             stale-cache bug pattern).

The runner never reads the real process environment, so benchmark runs are
hermetic.
"""

from __future__ import annotations

import copy
import json
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from sklearn import cluster, datasets, ensemble, linear_model, metrics, mixture
from sklearn import naive_bayes, neighbors, preprocessing
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import train_test_split

from . import simlib

OVERRIDE_PREFIX = "REPROMUT_OVERRIDE__"
CONFIG_FILE = "experiment.json"
RUNTIME_ENV_FILE = ".runtime_env.json"
DOTENV_FILE = ".env"
CACHE_FILE = ".cache/preprocessed.npz"

SUPERVISED = ("binary", "multiclass", "regression")
CLASSIFICATION = ("binary", "multiclass")


@dataclass
class PackageSpec:
    """In-memory representation of an experiment package."""

    config: dict
    runtime_env: dict = field(default_factory=lambda: {"simlib": simlib.DEFAULT_VERSION})
    dotenv: dict = field(default_factory=dict)
    cache: dict | None = None  # name -> ndarray
    key_order_reversed: bool = False  # cosmetic serialisation detail only

    def copy(self) -> "PackageSpec":
        return copy.deepcopy(self)


@dataclass
class RunResult:
    arrays: dict[str, dict[str, np.ndarray]]
    metrics: dict[str, float]
    effective_config: dict
    resolved_seeds: dict
    elapsed_s: float


# --------------------------------------------------------------------------
# Package I/O
# --------------------------------------------------------------------------

def _reverse_keys(obj):
    if isinstance(obj, dict):
        return {k: _reverse_keys(obj[k]) for k in reversed(list(obj))}
    return obj


def write_package(spec: PackageSpec, dest: Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    cfg = _reverse_keys(spec.config) if spec.key_order_reversed else spec.config
    (dest / CONFIG_FILE).write_text(json.dumps(cfg, indent=2) + "\n")
    (dest / RUNTIME_ENV_FILE).write_text(json.dumps(spec.runtime_env, indent=2) + "\n")
    if spec.dotenv:
        lines = [f"{k}={v}" for k, v in spec.dotenv.items()]
        (dest / DOTENV_FILE).write_text("\n".join(lines) + "\n")
    if spec.cache is not None:
        (dest / CACHE_FILE).parent.mkdir(parents=True, exist_ok=True)
        np.savez(dest / CACHE_FILE, **spec.cache)
    return dest


def parse_dotenv(text: str) -> dict:
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def read_package(path: Path) -> PackageSpec:
    path = Path(path)
    config = json.loads((path / CONFIG_FILE).read_text())
    runtime_env = {"simlib": simlib.DEFAULT_VERSION}
    if (path / RUNTIME_ENV_FILE).exists():
        runtime_env = json.loads((path / RUNTIME_ENV_FILE).read_text())
    dotenv = {}
    if (path / DOTENV_FILE).exists():
        dotenv = parse_dotenv((path / DOTENV_FILE).read_text())
    cache = None
    if (path / CACHE_FILE).exists():
        with np.load(path / CACHE_FILE) as z:
            cache = {k: z[k] for k in z.files}
    return PackageSpec(config=config, runtime_env=runtime_env, dotenv=dotenv, cache=cache)


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

def _parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def apply_overrides(config: dict, env: Mapping[str, str]) -> dict:
    cfg = copy.deepcopy(config)
    for key in sorted(env):
        if not key.startswith(OVERRIDE_PREFIX):
            continue
        path = key[len(OVERRIDE_PREFIX):].split("__")
        node = cfg
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = _parse_value(env[key])
    return cfg


def resolve_seed(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("seed must not be boolean")
    if isinstance(value, int):
        return value
    if value == "time":
        return time.time_ns() % (2**32)
    raise ValueError(f"unsupported seed value: {value!r}")


def _rescale(X: np.ndarray, seed: int | None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    scales = 10 ** rng.uniform(-1, 2, X.shape[1])
    shifts = rng.normal(0, 50, X.shape[1])
    return X * scales + shifts


def generate_data(task: str, d: dict, seed: int | None):
    n, p = d["n_samples"], d["n_features"]
    if task in CLASSIFICATION:
        X, y = datasets.make_classification(
            n_samples=n, n_features=p, n_informative=d["n_informative"],
            n_redundant=d.get("n_redundant", 2), n_classes=d["n_classes"],
            weights=d.get("weights"), flip_y=d["flip_y"],
            class_sep=d.get("class_sep", 1.0), shift=None, scale=None,
            random_state=seed,
        )
    elif task == "regression":
        X, y = datasets.make_regression(
            n_samples=n, n_features=p, n_informative=d["n_informative"],
            noise=d["noise"], random_state=seed,
        )
        X = _rescale(X, seed)
    elif task == "clustering":
        X, y = datasets.make_blobs(
            n_samples=n, n_features=p, centers=d["centers"],
            cluster_std=d["cluster_std"], center_box=tuple(d["center_box"]),
            random_state=seed,
        )
        X = _rescale(X, seed)
    else:
        raise ValueError(f"unknown task: {task}")
    X = X.astype(d.get("dtype", "float64"))
    if d.get("row_order", "as_generated") == "sorted_by_target":
        order = np.argsort(y, kind="stable")
        X, y = X[order], y[order]
    return X, y


def make_scaler(name: str, runtime_env: Mapping[str, str]):
    if name == "default":
        name = simlib.default_scaler(runtime_env.get("simlib", simlib.DEFAULT_VERSION))
    if name == "standard":
        return preprocessing.StandardScaler()
    if name == "robust":
        return preprocessing.RobustScaler()
    if name == "none":
        return preprocessing.FunctionTransformer()
    raise ValueError(f"unknown scaler: {name}")


MODEL_FACTORIES = {
    "logreg": linear_model.LogisticRegression,
    "rf_clf": ensemble.RandomForestClassifier,
    "knn_clf": neighbors.KNeighborsClassifier,
    "gnb": naive_bayes.GaussianNB,
    "ridge": linear_model.Ridge,
    "rf_reg": ensemble.RandomForestRegressor,
    "knn_reg": neighbors.KNeighborsRegressor,
    "sgd_reg": linear_model.SGDRegressor,
    "kmeans": cluster.KMeans,
    "gmm": mixture.GaussianMixture,
}
SEEDED_MODELS = {"logreg", "rf_clf", "rf_reg", "sgd_reg", "kmeans", "gmm", "ridge"}


def build_model(m: dict, seed: int | None):
    name = m["name"]
    params = dict(m.get("params", {}))
    if name in SEEDED_MODELS:
        params["random_state"] = seed
    return MODEL_FACTORIES[name](**params)


def _canonical_labels(labels: np.ndarray) -> np.ndarray:
    mapping, out = {}, np.empty_like(labels)
    for i, lab in enumerate(labels):
        out[i] = mapping.setdefault(int(lab), len(mapping))
    return out


def execute(spec: PackageSpec, environ: Mapping[str, str] | None = None) -> RunResult:
    """Run one package spec and return all stage artifacts."""
    start = time.perf_counter()
    env = dict(spec.dotenv)
    if environ:
        env.update(environ)
    cfg = apply_overrides(spec.config, env)
    task = cfg["task"]
    seeds = {k: resolve_seed(cfg["seeds"].get(k)) for k in ("data", "split", "model")}
    arrays: dict[str, dict[str, np.ndarray]] = {}

    X, y = generate_data(task, cfg["data"], seeds["data"])
    arrays["data"] = {"X": X, "y": y}

    idx = np.arange(len(y))
    if task in SUPERVISED:
        strat = y if task in CLASSIFICATION else None
        tr, te = train_test_split(idx, test_size=cfg["split"]["test_size"],
                                  random_state=seeds["split"], stratify=strat)
    else:
        tr, te = idx, idx
    arrays["split"] = {"train_idx": tr, "test_idx": te}

    pp = cfg["preprocess"]
    if pp.get("use_cache") and spec.cache is not None:
        Xtr, Xte = spec.cache["Xtr"], spec.cache["Xte"]
    else:
        scaler = make_scaler(pp["scaler"], spec.runtime_env)
        Xtr = scaler.fit_transform(X[tr])
        if cfg.get("evaluation", {}).get("refit_scaler_on_test"):
            Xte = make_scaler(pp["scaler"], spec.runtime_env).fit_transform(X[te])
        else:
            Xte = scaler.transform(X[te])
    arrays["preprocess"] = {"Xtr": np.asarray(Xtr), "Xte": np.asarray(Xte)}

    model = build_model(cfg["model"], seeds["model"])
    ytr, yte = y[tr], y[te]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        if task in CLASSIFICATION:
            model.fit(Xtr, ytr)
            proba = model.predict_proba(Xte)
            pred = model.classes_[np.argmax(proba, axis=1)]
            scores = proba
            m = {
                "accuracy": metrics.accuracy_score(yte, pred),
                "balanced_accuracy": metrics.balanced_accuracy_score(yte, pred),
                "log_loss": metrics.log_loss(yte, proba, labels=model.classes_),
            }
        elif task == "regression":
            model.fit(Xtr, ytr)
            scores = model.predict(Xte)
            m = {
                "r2": metrics.r2_score(yte, scores),
                "mae": metrics.mean_absolute_error(yte, scores),
                "rmse": float(np.sqrt(metrics.mean_squared_error(yte, scores))),
            }
        else:
            labels = model.fit_predict(Xtr)
            scores = _canonical_labels(labels)
            objective = (float(model.inertia_) if hasattr(model, "inertia_")
                         else float(model.lower_bound_))
            n_found = len(np.unique(labels))
            m = {
                "ari": metrics.adjusted_rand_score(yte, labels),
                "silhouette": (metrics.silhouette_score(Xtr, labels)
                               if n_found > 1 else float("nan")),
                "objective": objective,
            }
    arrays["model"] = {"scores": np.asarray(scores)}
    if task == "clustering":
        arrays["model"]["objective"] = np.array([objective])
    m = {k: float(v) for k, v in sorted(m.items())}
    arrays["metrics"] = {"values": np.array(list(m.values()), dtype=np.float64)}
    return RunResult(arrays=arrays, metrics=m, effective_config=cfg,
                     resolved_seeds=seeds, elapsed_s=time.perf_counter() - start)


def run_package(path: Path, environ: Mapping[str, str] | None = None) -> RunResult:
    return execute(read_package(path), environ=environ)
