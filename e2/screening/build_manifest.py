import json
from pathlib import Path
W = Path("/Users/mac/repromut-e2-work")
MANUAL = {
 "Phoenix-dev11/ADHD_recognition": ("exclude","M5","mental-health inference about people"),
 "balins/fuzzytree": ("exclude","M6","example uses unseeded synthetic data; no env/cache/cwd-path/default-change channel on the computation path"),
 "edikedik/eBoruta": ("exclude","M1","library; no batch experiment script (notebooks only)"),
 "smarie/python-m5p": ("exclude","M1","library; entry points are CI/nox tooling"),
 "Riccorl/ml-malware-classifier": ("exclude","M5","security / malware detection"),
 "pymc-learn/pymc-learn": ("exclude","M1","library; only setup.py entry"),
 "llpk79/Job-finder": ("exclude","M2","scrapes job sites at runtime"),
 "amirmohammadkz/personality_detection": ("exclude","M5","personality inference about people"),
 "fmind/mlops-python-package": ("eligible","", "MLflow tracking/registry location via env vars; local SQLite/registry store; config-relative data paths"),
 "HusseinYoussef/Arabic-OCR": ("exclude","M2","dataset shipped only as .rar requiring an external extraction tool"),
 "Azure/mlops-starter-sklearn": ("exclude","M6","local training step has no hidden-state channel; other steps need Azure services"),
 "rifqiharrys/sdb_gui": ("exclude","M1","GUI application"),
 "laplaces42/sign-language-interpreter": ("exclude","M1","interactive webcam application"),
 "ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques": ("eligible","", "Re-reviewed under A1 (S16); previously excluded only for X6 (nltk.download). train.py reads data/sample_data.csv relative to the working directory (cwd/path channel); prints accuracy and confusion matrix; NLTK punkt/stopwords prefetched at build"),
 "mrcaidev/kgqa": ("exclude","M1","web backend requiring a database"),
 "kingabzpro/FastAPI-for-ML": ("exclude","M1","web server"),
 "LuciaLlavero/ryuzaki_bot": ("exclude","M1","interactive chatbot"),
 "vincenzo-afk/SHADOWGHOST": ("exclude","M1","web application backend"),
 "iamgooold/malicious-url-detection-using-ml": ("exclude","M5","security / malicious-URL detection"),
 "rvandewater/ReciPies": ("exclude","M5","clinical ICU demonstration data"),
 "xinshuowl/DeltaForce-Trader": ("exclude","M5","trading automation"),
 "sandudul/BMI-Category-Predictor": ("exclude","M5","health (BMI) prediction"),
 "scikit-learn-contrib/stability-selection": ("exclude","M6","no hidden-state channel on the computation path"),
 "timzatko/Sklearn-Nature-Inspired-Algorithms": ("exclude","M1","examples are notebooks"),
 "architdatar/ml_uncertainty": ("exclude","M1","examples are notebooks"),
 "AmirhosseinHonardoust/Subscription-Loyalty-Risk-Radar": ("eligible","", "load_clean() silently reuses data/processed/shopping_behavior_clean.parquet if present (stale-cache channel)"),
 "ahmedbesbes/playground": ("exclude","M1","Streamlit app"),
 "astrogilda/tsbootstrap": ("exclude","M1","library; tools/profiling scripts only"),
 "iamgooold/sql-injection-attack-detection": ("exclude","M5","security / attack detection"),
 "thuijskens/scikit-hyperband": ("exclude","M6","no hidden-state channel on the computation path"),
 "AutoViML/pandas_dq": ("exclude","M1","library module"),
 "kbhujbal/SubmarineShield-underwater_anomaly_recognition_svm": ("exclude","M5","defence/military framing (conservative)"),
 "machine-learning-apps/ml-template-azure": ("exclude","M6","environment reads serve the Azure run context only; requires Azure ML SDK"),
 "getindata/kedro-snowflake": ("exclude","M2","requires Snowflake service"),
 "GrannyProgramming/AzureMLOpsInProduction": ("exclude","M2","requires Azure cloud services"),
 "arthurhenrique/cookiecutter-fastapi": ("exclude","M1","project template; bundled sample is a pregnancy model (also M5)"),
 "loglabs/mltrace": ("exclude","M1","library; tests only"),
 "City-of-Helsinki/mlops-template": ("exclude","M1","API server; pipeline steps are notebooks"),
 "george0st/qgate-sln-mlrun": ("exclude","M2","requires an MLRun service"),
 # --- Amendment A1: repositories excluded only by X6, reviewed under M1-M7 with M2' (approved 2026-11-09) ---
 "laplaces42/mlb_game_predictor": ("exclude","M2'","scrapes live sports-statistics web pages at run time; no stable pinned source"),
 "sagnik1511/Tabular-AutoML": ("eligible","", "A1 review. Its X6 match was a false positive (`fetch_metric_scores(`, see S8). It reads tab_automl/datasets/*.csv relative to the working directory (real cwd/path channel)."),
 "BGU-CS-VIL/pdc-dp-means": ("exclude","M1","library; the experiment code (paper_code) needs R (rpy2/maotai), torchvision and a patched scikit-learn (DPMeans); the other entry points are unit tests"),
 "Neuraxio/Neuraxle": ("exclude","M4","framework library; its examples are API demonstrations that only assert and print nothing numerical; the Boston examples need load_boston, which was removed in scikit-learn 1.2"),
 "CmsChase/cf-difficulty-prediction": ("exclude","M2'","the pipeline starts from a live Codeforces API fetch; the README says the snapshot is not fully committed"),
 "thatipamula-jashwanth/smart-knn": ("exclude","M6","the only relative path is the output directory; no env/cache/default-change channel on the computation path"),
 "AutoViML/Auto_ViML": ("exclude","M1","library; the only entry is the package __init__"),
 "a-wozniakowski/scikit-physlearn": ("exclude","M6","PCA appears only in a docstring; examples have no env/cache/cwd channel on the computation path"),
 "azukds/tubular": ("exclude","M1","library; the entry points are profiling/utility scripts"),
 "fnnx-ai/scikit-llm": ("exclude","M2'","requires LLM APIs or downloaded LLM weights"),
 "scikit-learn-contrib/sklearn-ann": ("exclude","M3","RNN-DBSCAN on 70,000x784 MNIST across several ANN back-ends plus a full-data silhouette score; not plausible within 10 min on 2 CPUs"),
 "soda-inria/sklearn-numba-dpex": ("exclude","M3","requires an Intel GPU / numba-dpex stack"),
 "csinva/disentangled-attribution-curves": ("exclude","M1","experiment scripts hard-code the author's cluster paths (/scratch/users/...) and import a missing module (../scores/interactions); not runnable without modifying third-party code"),
 "qiancao/hskl": ("exclude","M4","the example writes only PNG overlays; no printed metrics or numerical output"),
 "youngcoder45/Student-Performance-Predictor": ("eligible","", "A1 review. load_or_create_dataset() silently reuses data/processed or data/raw/student_performance.csv when present (stale-cache channel). The raw UCI zip is prefetched at build time."),
 "ContextLab/data-wrangler": ("exclude","M1","library; scripts are benchmarks/demo tooling"),
 "ThreeHats/auto-wall": ("exclude","M1","GUI application"),
 "skfolio/skfolio": ("exclude","M1","library (also portfolio finance, M5 conservative)"),
 "probabl-ai/skore-skills": ("exclude","M1","AI-assistant skill templates and tooling, not an experiment"),
 "callmevojtko/Recommended-Bets-By-Email-MLB": ("exclude","M5","sports-betting recommendations"),
 "georgedouzas/sports-betting": ("exclude","M5","sports-betting"),
 "Ayege/descubreplayas": ("exclude","M2'","live satellite/ocean APIs and a Supabase database"),
 "arv-anshul/yt-watch-history": ("exclude","M2'","personal Google Takeout data and the YouTube API"),
 "Azure/aml-run": ("exclude","M2'","GitHub Action requiring Azure ML"),
 "qnbhd/mljet": ("exclude","M1","deployment tool; the examples build services"),
 "data-max-hq/ab-testing-in-ml": ("exclude","M2'","training data is Reddit comments from a third-party repository with no stated data licence; also needs seldon-core and a spaCy model; outputs are dill pickles only"),
 "Paulescu/hands-on-train-and-deploy-ml": ("exclude","M2'","crypto prices from a live exchange API (also M5 conservative)"),
 "asehmi/using_chatgpt_kedro_streamlit_app": ("exclude","M5","crypto price forecasting (trading signal, conservative); committed exchange data with no stated licence (M7)"),
 "MG-Cafe/MLOps_Workshop": ("exclude","M2'","requires Azure ML"),
 "jwalsh/aif-c01": ("exclude","M2'","requires AWS Bedrock/S3"),
 "eraneos/snowflake-mlops": ("exclude","M2'","requires Snowflake"),
 "jerife/MLOps-on-kubernetes": ("exclude","M1","Kubeflow pipeline requiring Kubernetes and S3"),
}
ELIGIBLE_DETAIL = {
 "fmind/mlops-python-package": {
   "install": "uv sync --frozen from committed uv.lock (Python >=3.14), build stage only",
   "entry_point": "python -m bikes confs/training.yaml (then confs/inference.yaml for the inference cases)",
   "expected_runtime": "1-5 min per run (statically estimated; to be measured in pilot)",
   "network_during_run": "none required (local SQLite MLflow store)",
   "output_adapter": "metrics logged to the local MLflow store + inference output file declared in confs/inference.yaml; stdout numbers",
   "tolerance": {"rtol": 1e-6, "atol": 1e-9},
   "applicable_mutations": ["M-ENV: MLFLOW_TRACKING_URI / MLFLOW_REGISTRY_URI pointing to a pre-populated store", "M-CACHE: stale registered model in the local registry before inference", "M-PATH: shadow data/*.parquet under an alternative working directory"],
   "controls": ["C-ENV","C-CACHE","C-PATH"],
   "data": "UCI Bike Sharing dataset bundled (data/hour.csv, attribution in data/Readme.txt)"},
 "AmirhosseinHonardoust/Subscription-Loyalty-Risk-Radar": {
   "install": "pip install from requirements.txt resolved by uv with --exclude-newer 2026-11-01; streamlit excluded (UI only)",
   "entry_point": "python -m src.cli train-all (after prepare-data); evaluate",
   "expected_runtime": "<2 min per run (statically estimated)",
   "network_during_run": "none",
   "output_adapter": "reports/metrics/*.json written by training + stdout numbers",
   "tolerance": {"rtol": 1e-6, "atol": 1e-9},
   "applicable_mutations": ["M-CACHE: stale data/processed/shopping_behavior_clean.parquet produced from a 90%-row perturbation of the raw CSV"],
   "controls": ["C-ENV","C-CACHE","C-PATH","C-DEP"],
   "data": "data/raw/shopping_behavior.csv (Kaggle-derived; dataset licence not stated in repository — local use only, not redistributed)"},
 "ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques": {
   "install": "requirements.txt resolved by uv with --exclude-newer 2026-11-01; NLTK punkt/punkt_tab/stopwords prefetched at build (A1, SHA-256 recorded)",
   "entry_point": "python train.py", "cwd": "",
   "expected_runtime": "<1 min (150 rows)", "network_during_run": "none (nltk.download fails offline without raising; data prefetched)",
   "output_adapter": "stdout numbers (accuracy, confusion matrix)",
   "tolerance": {"rtol": 1e-6, "atol": 1e-9},
   "applicable_mutations": ["M-PATH: shadow data/sample_data.csv (90% rows) in the sibling cwd"],
   "controls": ["C-ENV","C-CACHE","C-PATH","C-DEP"],
   "data": "data/sample_data.csv, committed in the MIT repository (origin not stated; local use only, aggregate reporting)"},
 "sagnik1511/Tabular-AutoML": {
   "install": "requirements.txt (UTF-16; pins scikit-learn 1.0.2, xgboost 1.5.2, lightgbm 3.3.2) resolved by uv with --exclude-newer 2026-11-01 under a compatible Python (3.9/3.10), build stage only",
   "entry_point": "python test.py (from repository root)",
   "expected_runtime": "<2 min per run (statically estimated)",
   "network_during_run": "none (datasets committed)",
   "output_adapter": "per-model metric dictionaries printed to stdout (classification accuracy; regression mse/msle)",
   "tolerance": {"rtol": 1e-6, "atol": 1e-9},
   "applicable_mutations": ["M-PATH: run from a working directory where tab_automl/datasets/Iris.csv (or wine.csv) resolves to a perturbed copy"],
   "controls": ["C-ENV","C-CACHE","C-PATH","C-DEP"],
   "data": "tab_automl/datasets/Iris.csv and wine.csv, committed (UCI-origin datasets; the committed copies state no licence — local use only, aggregate reporting)"},
 "youngcoder45/Student-Performance-Predictor": {
   "install": "requirements.txt/pyproject resolved by uv with --exclude-newer 2026-11-01; build stage prefetches the UCI student.zip (SHA-256 pinned) into data/raw/",
   "entry_point": "python -m src.train",
   "expected_runtime": "2-6 min per run (RandomizedSearchCV n_iter=20 over 395 rows; statically estimated, to be measured in pilot)",
   "network_during_run": "none (archive prefetched; the code downloads only if data/raw/student.zip is absent)",
   "output_adapter": "JSON metrics written by save_json under reports/ + stdout numbers",
   "tolerance": {"rtol": 1e-6, "atol": 1e-9},
   "applicable_mutations": ["M-CACHE: stale data/raw/student_performance.csv (or data/processed/student_performance_processed.csv) built from a perturbed copy of the raw data"],
   "controls": ["C-ENV","C-CACHE","C-PATH","C-DEP"],
   "data": "UCI Student Performance (dataset 320), fetched at build time from archive.ics.uci.edu; licence to be recorded from the UCI dataset page before execution"},
}
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from manual_p3 import MANUAL_P3, ELIGIBLE_DETAIL_P3
MANUAL.update(MANUAL_P3)
ELIGIBLE_DETAIL.update(ELIGIBLE_DETAIL_P3)
rows = []
for pop, d in (("P1-topic:scikit-learn", W/"screening"), ("P2-topic:mlops", W/"screening_p2"), ("P3-topic:sklearn", W/"screening_p3")):
    recs = {json.loads(l)["repo"]: json.loads(l) for l in (d/"screening.jsonl").read_text().splitlines()}
    rs = d/"screening_rescreen.jsonl"
    if rs.exists():
        for l in rs.read_text().splitlines():
            r = json.loads(l); recs[r["repo"]] = {**r, "note": "re-screened after extraction fix (S4)"}
    for name, r in sorted(recs.items(), key=lambda kv: kv[1].get("order", 1e9)):
        m = MANUAL.get(name)
        row = {"population": pop, "order": r.get("order"), "repo": name, "url": r.get("url"),
               "commit": r.get("commit"), "license_spdx": r.get("license_spdx"), "license_source": r.get("license_path"),
               "stars": r.get("stars"), "automated_exclusions": r.get("reasons", []), "static_pass": r.get("static_pass", False),
               "hidden_state_channels_detected": r.get("channels"),
               "manual_review": None if not m else {"decision": m[0], "rule": m[1], "reason": m[2]},
               "eligible": bool(m and m[0] == "eligible")}
        if row["eligible"]:
            row.update(ELIGIBLE_DETAIL[name])
        rows.append(row)
out = {"generated_utc": __import__("datetime").datetime.utcnow().isoformat()+"Z",
       "selection_seed_text": "ReproMut-E2|10.5281/zenodo.24048206 (+ '|P2', '|P3')",
       "snapshots_utc": {"P1": (W/"screening/snapshot_utc.txt").read_text().strip(), "P2": (W/"screening_p2/snapshot_utc.txt").read_text().strip(), "P3": (W/"screening_p3/snapshot_utc.txt").read_text().strip()},
       "n_screened": len(rows), "n_static_pass": sum(r["static_pass"] for r in rows),
       "n_eligible": sum(r["eligible"] for r in rows), "repositories": rows}
Path("/Users/mac/Desktop/dev/repromut/e2/REPOSITORY-MANIFEST.json").write_text(json.dumps(out, indent=1))
print(out["n_screened"], out["n_static_pass"], out["n_eligible"])
import collections
print(collections.Counter(x.split(" ")[0] for r in rows for x in r["automated_exclusions"]).most_common())
print(collections.Counter(r["manual_review"]["rule"] for r in rows if r["manual_review"] and r["manual_review"]["decision"]=="exclude"))
