"""The v0.1 mutation catalog.

``positive`` mutations are declared result-changing: the shipped package will
not reproduce the reported result. ``control`` mutations are declared
semantics-preserving: the result must still reproduce within tolerance.

Each mutation declares the pipeline stage where its effect should first be
observable (``expected_stage``). The test suite checks every declaration
against an independent execution oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .runner import CLASSIFICATION, SUPERVISED, PackageSpec, execute

POSITIVE = "positive"
CONTROL = "control"


@dataclass(frozen=True)
class Mutation:
    id: str
    family: str
    kind: str
    expected_stage: str | None
    description: str
    applies: Callable[[dict], bool]
    transform: Callable[[PackageSpec], None]  # mutates the copy in place

    def apply(self, spec: PackageSpec) -> PackageSpec:
        if not self.applies(spec.config):
            raise ValueError(f"{self.id} does not apply to {spec.config['name']}")
        out = spec.copy()
        self.transform(out)
        return out


def _always(cfg: dict) -> bool:
    return True


def _supervised(cfg: dict) -> bool:
    return cfg["task"] in SUPERVISED


def _models(*names: str) -> Callable[[dict], bool]:
    return lambda cfg: cfg["model"]["name"] in names


# --- positive transforms ---------------------------------------------------

def _seed_unset(s: PackageSpec) -> None:
    s.config["seeds"] = {k: None for k in s.config["seeds"]}


def _seed_time(s: PackageSpec) -> None:
    s.config["seeds"] = {k: "time" for k in s.config["seeds"]}


def _split_seed(s: PackageSpec) -> None:
    s.config["seeds"]["split"] = s.config["seeds"]["split"] + 1


def _row_order(s: PackageSpec) -> None:
    s.config["data"]["row_order"] = "sorted_by_target"


def _dep_drift(s: PackageSpec) -> None:
    s.runtime_env["simlib"] = "2.0.0"


OVERRIDES = {
    "logreg": ("C", 0.01), "rf_clf": ("max_depth", 2), "knn_clf": ("n_neighbors", 2),
    "gnb": ("var_smoothing", 0.1), "ridge": ("alpha", 100.0), "rf_reg": ("max_depth", 2),
    "knn_reg": ("n_neighbors", 2), "sgd_reg": ("alpha", 0.1),
    "kmeans": ("n_clusters", 4), "gmm": ("n_components", 4),
}


def _env_override(s: PackageSpec) -> None:
    param, value = OVERRIDES[s.config["model"]["name"]]
    s.dotenv[f"REPROMUT_OVERRIDE__model__params__{param}"] = str(value)


def _dtype(s: PackageSpec) -> None:
    s.config["data"]["dtype"] = "float32"


def _stale_cache(s: PackageSpec) -> None:
    stale = s.copy()
    stale.cache = None
    stale.config["seeds"]["data"] = stale.config["seeds"]["data"] + 1000
    res = execute(stale)
    s.cache = {"Xtr": res.arrays["preprocess"]["Xtr"], "Xte": res.arrays["preprocess"]["Xte"]}


def _train_eval_mismatch(s: PackageSpec) -> None:
    s.config["evaluation"]["refit_scaler_on_test"] = True


def _label_noise(s: PackageSpec) -> None:
    d, task = s.config["data"], s.config["task"]
    if task in CLASSIFICATION:
        d["flip_y"] = 0.10
    elif task == "regression":
        d["noise"] = d["noise"] * 3
    else:
        d["cluster_std"] = d["cluster_std"] * 1.5


def _feature_gen(s: PackageSpec) -> None:
    d = s.config["data"]
    if s.config["task"] == "clustering":
        d["center_box"] = [-5.0, 5.0]
    else:
        d["n_informative"] = 3


def _tolerance(s: PackageSpec) -> None:
    p = s.config["model"]["params"]
    p["tol"] = 10.0 if s.config["task"] == "clustering" else 0.1
    p["max_iter"] = 1 if s.config["task"] == "clustering" else 5


# --- control transforms ----------------------------------------------------

def _rename(s: PackageSpec) -> None:
    s.config["run_name"] = s.config["run_name"] + "-renamed"


def _outdir(s: PackageSpec) -> None:
    s.config["output_dir"] = "/tmp/elsewhere/outputs"


def _notes(s: PackageSpec) -> None:
    s.config["notes"] = "Re-run for camera-ready; no scientific changes."


def _loglevel(s: PackageSpec) -> None:
    s.config["logging"]["level"] = "DEBUG"


def _threads(s: PackageSpec) -> None:
    s.config["model"]["params"]["n_jobs"] = 2


def _patch_bump(s: PackageSpec) -> None:
    s.runtime_env["simlib"] = "1.4.1"


def _key_order(s: PackageSpec) -> None:
    s.key_order_reversed = True


SCALE_SENSITIVE = ("logreg", "knn_clf", "ridge", "knn_reg", "sgd_reg", "kmeans", "gmm")
# gmm excluded: on the separated variant EM converges within one iteration, so
# loosening the tolerance does not change the result (found by the oracle).
ITERATIVE = ("logreg", "sgd_reg", "kmeans")
THREADED = ("rf_clf", "rf_reg", "knn_clf", "knn_reg")
# Tree ensembles are invariant to float32 rounding of these features (oracle).
NOT_TREE = ("logreg", "knn_clf", "gnb", "ridge", "knn_reg", "sgd_reg", "kmeans", "gmm")


def _unstratified(cfg: dict) -> bool:
    # Stratified splitting with a stable sort selects the same rows, so
    # label-sorted input does not change classification results (oracle).
    return cfg["task"] == "regression"

CATALOG: tuple[Mutation, ...] = (
    Mutation("seed_unset", "random-state", POSITIVE, "data",
             "All seeds removed (None); library global RNG state is used.", _always, _seed_unset),
    Mutation("seed_time_derived", "random-state", POSITIVE, "data",
             "All seeds derived from wall-clock time at runtime.", _always, _seed_time),
    Mutation("split_seed_changed", "random-state", POSITIVE, "split",
             "Train/test split seed differs from the reported run.", _supervised, _split_seed),
    Mutation("row_order_changed", "data-order", POSITIVE, "data",
             "Input rows arrive sorted by target before splitting.", _unstratified, _row_order),
    Mutation("dependency_default_drift", "dependency", POSITIVE, "preprocess",
             "Unpinned dependency resolves to a version whose default scaler changed.",
             _models(*SCALE_SENSITIVE), _dep_drift),
    Mutation("env_override", "hidden-config", POSITIVE, "model",
             "A shipped .env file silently overrides a model hyperparameter.", _always, _env_override),
    Mutation("dtype_float32", "numeric", POSITIVE, "data",
             "Feature matrix precision reduced to float32.", _models(*NOT_TREE), _dtype),
    Mutation("stale_cache", "caching", POSITIVE, "preprocess",
             "A cached preprocessing artifact from a different data seed is shipped and reused.",
             _always, _stale_cache),
    Mutation("train_eval_mismatch", "config-mismatch", POSITIVE, "preprocess",
             "Scaler is re-fitted on the evaluation split instead of reused from training.",
             _supervised, _train_eval_mismatch),
    Mutation("label_noise_changed", "data-generation", POSITIVE, "data",
             "Generator noise level differs from the reported run.", _always, _label_noise),
    Mutation("feature_generation_changed", "data-generation", POSITIVE, "data",
             "Generator feature structure differs from the reported run.", _always, _feature_gen),
    Mutation("solver_tolerance_loosened", "numeric", POSITIVE, "model",
             "Optimiser tolerance loosened and iteration cap lowered.",
             _models(*ITERATIVE), _tolerance),
    Mutation("run_name_changed", "cosmetic", CONTROL, None,
             "Run label changed.", _always, _rename),
    Mutation("output_dir_changed", "cosmetic", CONTROL, None,
             "Output directory changed to an absolute path.", _always, _outdir),
    Mutation("notes_added", "cosmetic", CONTROL, None,
             "Free-text notes added to the config.", _always, _notes),
    Mutation("log_level_changed", "cosmetic", CONTROL, None,
             "Logging verbosity raised.", _always, _loglevel),
    Mutation("thread_count_changed", "parallelism", CONTROL, None,
             "n_jobs raised for estimators whose results do not depend on it.",
             _models(*THREADED), _threads),
    Mutation("dependency_patch_bump", "dependency", CONTROL, None,
             "Dependency resolves to a patch release with no behavioural change.",
             _always, _patch_bump),
    Mutation("config_key_order_changed", "cosmetic", CONTROL, None,
             "Config keys serialised in a different order.", _always, _key_order),
)

BY_ID = {m.id: m for m in CATALOG}


def applicable(spec: PackageSpec) -> list[Mutation]:
    return [m for m in CATALOG if m.applies(spec.config)]
