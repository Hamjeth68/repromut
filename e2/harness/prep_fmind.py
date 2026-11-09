"""Prepare registered stale/shadow artifacts for fmind/mlops-python-package (before outcome runs).

All third-party code runs in the offline, isolated container (repromut.e2.container):
1. Perturb the training parquet files (first 90% of rows) with OUR script inside the repo image.
2. Produce the stale MLflow store (mlflow.db + mlruns) by running the repository's own pipeline
   on the perturbed training data, in the same layout (/work/repo) the cases use.
Usage: python e2/harness/prep_fmind.py <image-id>
"""
import glob
import shutil
import sys
from pathlib import Path

from repromut.e2 import container as C
from repromut.e2.cases import BASELINE, CaseSpec, materialise

WORK = Path.home() / "repromut-e2-work"
ART = WORK / "artifacts" / "fmind__mlops-python-package"
PERTURB = '''
import sys, pandas as pd
for rel in sys.argv[1:]:
    df = pd.read_parquet(rel)
    df.iloc[: int(len(df) * 0.9)].to_parquet("/work/.repromut/out/" + rel.replace("/", "__"))
'''


def main(image: str) -> None:
    tree = Path(glob.glob(str(WORK / "screening/src/fmind__mlops-python-package/*"))[0])
    ART.mkdir(parents=True, exist_ok=True)
    root = WORK / "runs" / "prep_fmind"
    shutil.rmtree(root, ignore_errors=True)
    cwd, _, repo = materialise(BASELINE, tree, root, ART, ["bikes"])
    tool = root / ".repromut"
    (tool / "out").mkdir(parents=True)
    (tool / "perturb.py").write_text(PERTURB)
    for p in [tool, tool / "out"]:
        p.chmod(0o777)
    names = ["data/inputs_train.parquet", "data/targets_train.parquet"]
    r = C.run(C.ContainerSpec(image, root, cwd, ["python", "-I", "/work/.repromut/perturb.py", *names]),
              [f".repromut/out/{n.replace('/', '__')}" for n in names])
    assert r.status == "ok", r.stderr[-2000:]
    for n in names:
        (ART / ("p90__" + n.replace("/", "__"))).write_bytes(r.files[f".repromut/out/{n.replace('/', '__')}"])
    for n in ["confs/pipeline.yaml", "data/inputs_test.parquet", "data/targets_test.parquet"]:
        shutil.copyfile(tree / n, ART / ("copy__" + n.replace("/", "__")))
    shutil.rmtree(root)
    # Stale store: the repository's own pipeline on the perturbed training data.
    case = CaseSpec("prep", "M-CACHE", "positive", pre_files={
        "data/inputs_train.parquet": "p90__data__inputs_train.parquet",
        "data/targets_train.parquet": "p90__data__targets_train.parquet"})
    cwd, argv, repo = materialise(case, tree, root, ART, ["bikes", "confs/pipeline.yaml"])
    r = C.run(C.ContainerSpec(image, root, cwd, argv, {}, 600), [])
    assert r.status == "ok", r.stderr[-2000:]
    for n in ["mlflow.db", "mlruns"]:
        dst = ART / ("stale__" + n)
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        (shutil.copytree if (repo / n).is_dir() else shutil.copyfile)(repo / n, dst)
    shutil.rmtree(root)
    print("prepared:", sorted(p.name for p in ART.iterdir()))


if __name__ == "__main__":
    main(sys.argv[1])
