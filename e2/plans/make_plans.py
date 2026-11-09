"""Generate the registered case plans for the 12 non-pilot repositories (committed BEFORE their outcome runs).

Design rule (PILOT-REPORT, "Implication for the full study"): one M-PATH case per relative input file read
on the computation path (other inputs shadowed as unchanged copies so the case never fails merely with
"file not found"), M-CACHE where a reuse-if-present artifact exists, M-DEP where a registered default change
applies, plus C-ENV, C-CACHE, C-PATH and C-DEP (nearest patch release with a binary wheel, "auto_patch").
Perturbation = first 90% of data rows (header kept), as registered in protocol section 4.
"""
import glob
import json
from pathlib import Path

W = Path.home() / "repromut-e2-work"
OUT = Path(__file__).parent


def tree(pop, slug):
    return glob.glob(str(W / pop / "src" / slug / "*"))[0].replace(str(Path.home()), "~")


def ctrl():
    return [{"case_id": "C-ENV", "family": "C-ENV", "intent": "control", "env": {"REPROMUT_UNUSED_VAR": "1"}},
            {"case_id": "C-CACHE", "family": "C-CACHE", "intent": "control"},
            {"case_id": "C-PATH", "family": "C-PATH", "intent": "control"},
            {"case_id": "C-DEP", "family": "C-DEP", "intent": "control", "image_key": "dep_patch"}]


def mpath(cid, shadows, note=""):
    return {"case_id": cid, "family": "M-PATH", "intent": "positive", "shadow_files": shadows, "note": note}


P = {}
P["ARUNAGIRINATHAN-K/Text-Classifier-using-NLP_Techniques"] = dict(
    source_tree=tree("screening", "ARUNAGIRINATHAN-K__Text-Classifier-using-NLP_Techniques"),
    build={"mode": "requirements", "python": "3.10", "requirements": "requirements.txt",
           "nltk": ["punkt", "punkt_tab", "stopwords"], "variants": {"dep_patch": "auto_patch"}},
    argv=["python", "train.py"], adapter={"stdout": True},
    artifacts={"sample_p90.csv": {"from": "data/sample_data.csv", "method": "perturb_rows"},
               "empty": {"method": "empty"}},
    cases=[mpath("M-PATH-1", {"data/sample_data.csv": "sample_p90.csv", "model/.keep": "empty"})] + ctrl())

P["youngcoder45/Student-Performance-Predictor"] = dict(
    source_tree=tree("screening", "youngcoder45__Student-Performance-Predictor"),
    build={"mode": "requirements", "python": "3.12", "requirements": "requirements.txt",
           "variants": {"dep_patch": "auto_patch"}},
    setup={"add_files": {"data/raw/student.zip": "student.zip"}},
    argv=["python", "-m", "src.train"],
    adapter={"stdout": True, "files": ["models/metrics.json", "reports/figures/regression_model_comparison.csv",
                                       "reports/figures/classification_model_comparison.csv"]},
    artifacts={"student_p90.zip": {"from_artifact": "student.zip", "method": "zip_member_perturb",
                                   "member": "student-mat.csv"}},
    prep=[{"name": "stale", "argv": ["python", "-m", "src.train"],
           "pre_files": {"data/raw/student.zip": "student_p90.zip"},
           "capture": {"data/raw/student_performance.csv": "stale_student_performance.csv"}}],
    cases=[{"case_id": "M-CACHE-1", "family": "M-CACHE", "intent": "positive",
            "pre_files": {"data/raw/student_performance.csv": "stale_student_performance.csv"},
            "note": "standardised CSV produced by the repository's own code from the first 90% of student-mat.csv rows"}]
          + ctrl(),
    notes=["M-PATH not applicable: python -m entry and __file__-anchored paths",
           "student.zip (UCI 320, CC BY 4.0) fetched in a networked build container; SHA-256 in e2/env/datasets.json"])

P["AmirhosseinHonardoust/Subscription-Loyalty-Risk-Radar"] = dict(
    source_tree=tree("screening", "AmirhosseinHonardoust__Subscription-Loyalty-Risk-Radar"),
    build={"mode": "requirements", "python": "3.10", "requirements": "requirements.txt",
           "variants": {"dep_patch": "auto_patch"}},
    argv=["sh", "-c", "python -m src.cli prepare-data && python -m src.cli train-all && python -m src.cli evaluate"],
    adapter={"stdout": True, "files": ["reports/metrics/subscription_metrics.json", "reports/metrics/frequency_metrics.json",
                                       "reports/metrics/subscription_metrics_eval.json", "reports/metrics/frequency_metrics_eval.json"]},
    artifacts={"raw_p90.csv": {"from": "data/raw/shopping_behavior.csv", "method": "perturb_rows"}},
    prep=[{"name": "stale", "argv": ["python", "-m", "src.cli", "prepare-data"],
           "pre_files": {"data/raw/shopping_behavior.csv": "raw_p90.csv"},
           "remove": ["data/processed/shopping_behavior_clean.parquet"],
           "capture": {"data/processed/shopping_behavior_clean.parquet": "stale_clean.parquet"}}],
    cases=[{"case_id": "M-CACHE-1", "family": "M-CACHE", "intent": "positive",
            "pre_files": {"data/processed/shopping_behavior_clean.parquet": "stale_clean.parquet"},
            "note": "load_clean() reuses this file if present; stale version built by the repository from 90% of raw rows"}]
          + ctrl(),
    notes=["README pipeline (prepare-data, train-all, evaluate) run as one declared invocation",
           "M-PATH not applicable: python -m entry and __file__-anchored paths"])

P["roodriigoooo/clustering_the_vrp"] = dict(
    source_tree=tree("screening_p3", "roodriigoooo__clustering_the_vrp"),
    build={"mode": "imports", "python": "3.10", "extra": ["networkx", "seaborn"], "variants": {"dep_patch": "auto_patch"}},
    argv=["python", "main.py"], cwd_rel="src/core", adapter={"stdout": True},
    artifacts={"data_copy": {"from": "data", "method": "copy_tree"},
               "A-n32-k5_input_nodes_p90.txt": {"from": "data/A-n32-k5_input_nodes.txt", "method": "perturb_rows", "header": False}},
    cases=[mpath("M-PATH-1", {"data": "data_copy", "data/A-n32-k5_input_nodes.txt": "A-n32-k5_input_nodes_p90.txt"},
                 "instance files read via cwd-relative ../../data and data/ paths")] + ctrl())

P["jaideepsinhdabhi/JustDataML"] = dict(
    source_tree=tree("screening_p3", "jaideepsinhdabhi__JustDataML"),
    build={"mode": "uvlock", "python": "3.10",
           "variants": {"dep_patch": "auto_patch", "m_dep": "scikit-learn==1.5.2"}},
    argv=["JDML", "train", "-C", "config_clf.yaml"], cwd_rel="examples", adapter={"stdout": True},
    artifacts={"iris_p90.data": {"from": "examples/Data/bezdekIris.data", "method": "perturb_rows", "header": False},
               "config_clf.yaml": {"from": "examples/config_clf.yaml", "method": "copy"}},
    cases=[mpath("M-PATH-1", {"examples/config_clf.yaml": "config_clf.yaml", "examples/Data/bezdekIris.data": "iris_p90.data"}),
           {"case_id": "M-DEP-1", "family": "M-DEP", "intent": "positive", "image_key": "m_dep",
            "note": "scikit-learn 1.7.2 -> 1.5.2 (AdaBoostClassifier algorithm default before 1.6); only scikit-learn changes"}]
          + ctrl())

P["Bruce-Lee-LY/machine_learning"] = dict(
    source_tree=tree("screening_p3", "Bruce-Lee-LY__machine_learning"),
    build={"mode": "requirements", "python": "3.10", "requirements": "requirements.txt",
           "variants": {"dep_patch": "auto_patch", "m_dep": "scikit-learn==1.4.2"}},
    argv=["python", "unsupervised_learning/KMeans.py"], adapter={"stdout": True},
    prep=[{"name": "stale", "image_key": "m_dep", "argv": ["python", "unsupervised_learning/KMeans.py"],
           "capture": {"model/KMeans/KMeans_blobs.pkl": "stale_KMeans_blobs.pkl"}}],
    cases=[{"case_id": "M-DEP-1", "family": "M-DEP", "intent": "positive", "image_key": "m_dep",
            "note": "KMeans n_init default (10 before 1.4, 'auto' from 1.4); declared pin is 0.22.2"},
           {"case_id": "M-CACHE-1", "family": "M-CACHE", "intent": "positive",
            "pre_files": {"model/KMeans/KMeans_blobs.pkl": "stale_KMeans_blobs.pkl"},
            "note": "model cache reused if present; stale model produced by the same script under the other scikit-learn version"},
           mpath("M-PATH-1", {"model/KMeans/KMeans_blobs.pkl": "stale_KMeans_blobs.pkl"},
                 "cwd-relative model cache path")] + ctrl())

P["nazmul-1117/bangladesh-air-pollution-pattern-mining"] = dict(
    source_tree=tree("screening_p3", "nazmul-1117__bangladesh-air-pollution-pattern-mining"),
    build={"mode": "uvlock", "python": "3.14", "variants": {"dep_patch": "auto_patch"}},
    argv=["python", "main.py"],
    adapter={"stdout": True, "files": ["outputs/results/cluster_summary.csv", "outputs/results/association_rules.csv",
                                       "outputs/results/feature_importance.csv"]},
    artifacts={"raw_p90.csv": {"from": "data/raw/air_quality.csv", "method": "perturb_rows"},
               "cleaned_p90.csv": {"from": "data/processed/air_quality_cleaned.csv", "method": "perturb_rows"}},
    prep=[{"name": "stale", "argv": ["python", "preprocess.py"], "pre_files": {"data/raw/air_quality.csv": "raw_p90.csv"},
           "capture": {"data/processed/air_quality_cleaned.csv": "stale_cleaned.csv"}}],
    cases=[{"case_id": "M-CACHE-1", "family": "M-CACHE", "intent": "positive",
            "pre_files": {"data/processed/air_quality_cleaned.csv": "stale_cleaned.csv"},
            "note": "cleaned CSV produced by preprocess.py from the first 90% of raw rows"},
           mpath("M-PATH-1", {"data/processed/air_quality_cleaned.csv": "cleaned_p90.csv"})] + ctrl())

P["chonzadaniel/Model-Deployment-Using-Flask"] = dict(
    source_tree=tree("screening_p3", "chonzadaniel__Model-Deployment-Using-Flask"),
    build={"mode": "imports", "python": "3.10", "variants": {"dep_patch": "auto_patch"}},
    argv=["python", "training.py"], adapter={"stdout": True},
    artifacts={"salary_p90.csv": {"from": "salaryprediction_data.csv", "method": "perturb_rows"}},
    cases=[mpath("M-PATH-1", {"salaryprediction_data.csv": "salary_p90.csv"})] + ctrl())

P["andi611/Naive-Bayes-and-Decision-Tree-Classifiers"] = dict(
    source_tree=tree("screening_p3", "andi611__Naive-Bayes-and-Decision-Tree-Classifiers"),
    build={"mode": "imports", "python": "3.10", "extra": ["tqdm", "graphviz"], "variants": {"dep_patch": "auto_patch"}},
    setup={"extract_zips": ["data.zip"]},
    argv=["python", "runner.py", "--naive_bayes", "--data_mushroom"], cwd_rel="src", adapter={"stdout": True},
    artifacts={"train_p90.csv": {"from": "data/mushroom/mushroom_train.csv", "method": "perturb_rows"},
               "train.csv": {"from": "data/mushroom/mushroom_train.csv", "method": "copy"},
               "test_p90.csv": {"from": "data/mushroom/mushroom_test.csv", "method": "perturb_rows"},
               "test.csv": {"from": "data/mushroom/mushroom_test.csv", "method": "copy"},
               "empty": {"method": "empty"}},
    cases=[mpath("M-PATH-train", {"data/mushroom/mushroom_train.csv": "train_p90.csv", "data/mushroom/mushroom_test.csv": "test.csv", "result/.keep": "empty"}),
           mpath("M-PATH-test", {"data/mushroom/mushroom_train.csv": "train.csv", "data/mushroom/mushroom_test.csv": "test_p90.csv", "result/.keep": "empty"})]
          + ctrl())

P["thaije/capteam-iglo-titanic-ml"] = dict(
    source_tree=tree("screening_p3", "thaije__capteam-iglo-titanic-ml"),
    build={"mode": "requirements", "python": "3.10", "requirements": "requirements.txt", "variants": {"dep_patch": "auto_patch"}},
    argv=["python", "main.py"], adapter={"stdout": True},
    artifacts={"Data_copy": {"from": "Data", "method": "copy_tree"},
               "train_p90.csv": {"from": "Data/train.csv", "method": "perturb_rows"},
               "test_p90.csv": {"from": "Data/test.csv", "method": "perturb_rows"},
               "empty": {"method": "empty"}},
    cases=[mpath("M-PATH-train", {"Data": "Data_copy", "Data/train.csv": "train_p90.csv", "predictions/.keep": "empty"}),
           mpath("M-PATH-test", {"Data": "Data_copy", "Data/test.csv": "test_p90.csv", "predictions/.keep": "empty"})] + ctrl())

P["NHLOCAL/is-this-bible"] = dict(
    source_tree=tree("screening_p3", "NHLOCAL__is-this-bible"),
    build={"mode": "imports", "python": "3.10", "extra": ["nltk"], "nltk": ["stopwords", "punkt", "punkt_tab"],
           "variants": {"dep_patch": "auto_patch"}},
    argv=["python", "creat_model_bible.py"], cwd_rel="data_creation", adapter={"stdout": True},
    artifacts={"bible_p90.csv": {"from": "data_creation/bible_data.csv", "method": "perturb_rows"}},
    cases=[mpath("M-PATH-1", {"data_creation/bible_data.csv": "bible_p90.csv"})] + ctrl())

P["AmirhosseinHonardoust/Fake-Review-Detector"] = dict(
    source_tree=tree("screening_p3", "AmirhosseinHonardoust__Fake-Review-Detector"),
    build={"mode": "requirements", "python": "3.10", "requirements": "requirements.txt", "variants": {"dep_patch": "auto_patch"}},
    argv=["python", "src/train.py"], adapter={"stdout": True},
    artifacts={"reviews_p90.csv": {"from": "data/reviews_sample.csv", "method": "perturb_rows"}},
    cases=[mpath("M-PATH-1", {"data/reviews_sample.csv": "reviews_p90.csv"})] + ctrl())

for repo, p in P.items():
    plan = {"repo": repo, "images": "from_build", "timeout_s": 600, **p}
    (OUT / (repo.replace("/", "__") + ".json")).write_text(json.dumps(plan, indent=1))
print(len(P), "plans written")
