"""E2 static pre-screen. Reads third-party repositories AS TEXT ONLY. Never executes them.

Population: union of raw_*.json (GitHub search snapshot). Order: seeded shuffle.
For each repository: resolve default-branch commit SHA, download tarball of that SHA,
extract with tarfile 'data' filter into an isolated folder, apply static rules.
Writes screening.jsonl (one record per repository, including exclusions).
"""
import hashlib, io, json, os, re, subprocess, sys, tarfile, time
from pathlib import Path
import random

HERE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
SEED_TEXT = "ReproMut-E2|10.5281/zenodo.24048206" + (("|" + sys.argv[2]) if len(sys.argv) > 2 else "")
ALLOWED = {"mit", "bsd-3-clause", "bsd-2-clause", "apache-2.0"}
OWN_ACCOUNTS = {"hamjeth68", "hamjeth-dev-ai"}
HIGH_STAKES = re.compile(r"(?i)\b(adhd|autis|mental|psych|personality|depress|bmi\b|obes|malware|intrusion|phishing|sql.?injection|cyber|trader|gambl|betting|medic|health|clinic|patient|cancer|tumou?r|diabet|heart|cardio|covid|disease|diagnos|hospital|drug|mri|x-?ray|ecg|eeg|alzheim|parkinson|stroke|credit|loan|fraud|stock|trading|financ|bank|insurance|legal|court|crime|criminal|surveillance|face.?recogn|biometric|weapon|military)")
MEDICAL_DATA = re.compile(r"load_breast_cancer|load_diabetes|fetch_.*(?:cancer|heart)|heart\.csv|diabetes\.csv|cancer\.csv")
NETWORK = re.compile(r"nltk\.download|spacy\.cli\.download|from_pretrained|hf_hub_download|urlopen|urlretrieve|requests\.(?:get|post)|\bwget\b|kaggle|fetch_openml|fetch_[a-z0-9_]+\(|keras\.datasets|download\s*=\s*True|load_dataset\(|gdown|boto3|s3://|https?://[^\s'\"]+\.(?:csv|zip|gz|tgz|npz|pkl|json|txt|parquet)")
HEAVY = re.compile(r"(?im)^\s*(?:import|from)\s+(torch|tensorflow|keras|jax|mxnet|paddle|cupy|xgboost\.dask|pyspark)\b")
SECRETS = re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*=\s*['\"][^'\"]{8,}")
ENTRY = re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]")
ENV = re.compile(r"os\.environ|os\.getenv|getenv\(|load_dotenv|environ\.get")
CACHE = re.compile(r"joblib\.Memory|Memory\(|os\.path\.exists\([^)]*\)\s*:?[^\n]*\n[^\n]*(?:load|read_|pickle)|if\s+(?:not\s+)?os\.path\.(?:exists|isfile)\(|Path\([^)]*\)\.exists\(\)|cache", re.S)
RELPATH = re.compile(r"""(?:read_csv|open|np\.load|loadtxt|read_excel|read_json|joblib\.load|pickle\.load)\(\s*['"](?!/)(?:\./|\.\./)?[\w\-./]+['"]""")
SKLEARN = re.compile(r"(?m)^\s*(?:from|import)\s+sklearn")
DEFAULT_CHANGE = {   # documented default changes, verified against the scikit-learn changelog before any run
    "KMeans_n_init(1.3->1.4)": re.compile(r"\b(?:MiniBatch)?KMeans\((?![^)]*n_init)"),
    "TSNE_init_lr(1.1->1.2)": re.compile(r"\bTSNE\((?![^)]*init)"),
    "AdaBoost_algorithm(1.5->1.6)": re.compile(r"\bAdaBoostClassifier\((?![^)]*algorithm)"),
    "LinearSVC_dual(1.4->1.5)": re.compile(r"\bLinearSVC\((?![^)]*dual)"),
    "PCA_svd_solver(1.4->1.5)": re.compile(r"\bPCA\((?![^)]*svd_solver)"),
}
PIN_SKLEARN = re.compile(r"(?im)^\s*scikit[-_]learn\s*==")

def gh(*args, raw=False):
    out = subprocess.run(["gh", "api", *args], capture_output=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode()[:200])
    return out.stdout if raw else json.loads(out.stdout)

def population():
    repos = {}
    skip = set()
    # Remove repositories already screened in earlier populations (dirs named screening* sorting before this one).
    for prev in sorted(HERE.parent.glob("screening*")):
        if prev.name < HERE.name and (prev / "screening.jsonl").exists():
            skip |= {json.loads(l)["repo"].lower() for l in (prev / "screening.jsonl").read_text().splitlines()}
    for f in sorted(HERE.glob("raw_*.json")):
        for r in json.loads(f.read_text()):
            if r["fullName"].lower() not in skip:
                repos[r["fullName"].lower()] = r
    names = sorted(repos)
    seed = int(hashlib.sha256(SEED_TEXT.encode()).hexdigest(), 16) % 2**32
    random.Random(seed).shuffle(names)
    return [repos[n] for n in names]

def screen(meta):
    name = meta["fullName"]
    rec = {"repo": name, "url": meta["url"], "stars": meta["stargazersCount"],
           "license_search": (meta.get("license") or {}).get("key"), "reasons": []}
    owner = name.split("/")[0].lower()
    if owner in OWN_ACCOUNTS:
        rec["reasons"].append("X4 own repository")
    if HIGH_STAKES.search(f"{name} {meta.get('description') or ''}"):
        rec["reasons"].append("X3 high-stakes domain (name/description)")
    if rec["license_search"] not in ALLOWED:
        rec["reasons"].append("X1 licence not in allowed set")
    info = gh(f"repos/{name}")
    lic = gh(f"repos/{name}/license") if info.get("license") else None
    rec["license_spdx"] = (info.get("license") or {}).get("spdx_id")
    rec["license_path"] = lic.get("path") if lic else None
    if not rec["license_path"]:
        rec["reasons"].append("X1 no licence file")
    sha = gh(f"repos/{name}/commits/{info['default_branch']}")["sha"]
    rec["commit"] = sha
    dest = HERE / "src" / name.replace("/", "__")
    if not dest.exists():
        blob = gh(f"repos/{name}/tarball/{sha}", raw=True)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            skipped = 0
            for m in tf.getmembers():
                try:
                    tf.extract(m, dest, filter="data")
                except (tarfile.FilterError, OSError):
                    skipped += 1   # unsafe/unsupported member (e.g. absolute symlink): never extracted
            rec["archive_members_skipped"] = skipped
    py = [p for p in dest.rglob("*.py") if p.is_file() and not p.is_symlink() and p.stat().st_size < 300_000]
    nb = [p for p in dest.rglob("*.ipynb") if p.is_file()]
    text = "\n".join(p.read_text(errors="ignore") for p in py)
    readme = "\n".join(p.read_text(errors="ignore")[:20000] for p in dest.rglob("README*") if p.is_file())
    reqs = "\n".join(p.read_text(errors="ignore") for p in dest.rglob("*") if p.is_file() and re.search(r"requirements.*\.txt$|setup\.py$|pyproject\.toml$|environment.*\.ya?ml$|Pipfile$", p.name))
    rec["n_py"], rec["n_ipynb"] = len(py), len(nb)
    if HIGH_STAKES.search(readme[:4000]):
        rec["reasons"].append("X3 high-stakes domain (README)")
    if MEDICAL_DATA.search(text):
        rec["reasons"].append("X10 medical dataset in code")
    if not py:
        rec["reasons"].append("X5 no Python source (notebooks only)")
    entries = [str(p.relative_to(dest).as_posix()).split("/", 1)[-1] for p in py if ENTRY.search(p.read_text(errors="ignore"))]
    rec["entry_candidates"] = entries[:10]
    if py and not entries:
        rec["reasons"].append("X5 no script entry point")
    if NETWORK.search(text):
        rec["reasons"].append("X6 network/data download in code")
    if HEAVY.search(text):
        rec["reasons"].append("X8 heavy framework (torch/tensorflow/jax/...)")
    if SECRETS.search(text):
        rec["reasons"].append("X11 hard-coded credential pattern")
    if not SKLEARN.search(text):
        rec["reasons"].append("X12 does not import scikit-learn")
    ch = {"env": bool(ENV.search(text)), "cache": bool(CACHE.search(text)),
          "relpath": bool(RELPATH.search(text)),
          "dep_default": sorted(k for k, rx in DEFAULT_CHANGE.items() if rx.search(text)) if not PIN_SKLEARN.search(reqs) else []}
    rec["channels"] = ch
    rec["sklearn_pinned"] = bool(PIN_SKLEARN.search(reqs))
    if not (ch["env"] or ch["cache"] or ch["relpath"] or ch["dep_default"]):
        rec["reasons"].append("X9 no hidden-state channel detected")
    rec["static_pass"] = not rec["reasons"]
    return rec

def main():
    out = HERE / "screening.jsonl"
    done = {json.loads(l)["repo"] for l in out.read_text().splitlines()} if out.exists() else set()
    pop = population()
    (HERE / "population_order.json").write_text(json.dumps([r["fullName"] for r in pop], indent=1))
    shard = os.environ.get("PRESCREEN_SHARD")  # optional "k/n": parallel workers over disjoint orders; results are order-indexed
    k, n = (int(x) for x in shard.split("/")) if shard else (0, 1)
    for i, meta in enumerate(pop):
        if i % n != k or meta["fullName"] in done:
            continue
        try:
            rec = screen(meta)
        except Exception as e:  # infrastructure failure, recorded not hidden
            rec = {"repo": meta["fullName"], "url": meta["url"], "reasons": [f"INFRA {e}"], "static_pass": False}
        rec["order"] = i
        with out.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(i, rec["repo"], "PASS" if rec["static_pass"] else rec["reasons"][:2], flush=True)

if __name__ == "__main__":
    main()
