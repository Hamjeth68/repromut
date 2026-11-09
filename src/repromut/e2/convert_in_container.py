"""Converter that runs INSIDE the isolated container after a case run (our own code, offline).

Usage (in container): python -I convert_in_container.py <cwd> <relpath> [<relpath> ...]
Writes /work/.repromut/out/<relpath with / -> __>.json = {"ok": bool, "values": [...]} so the host
never has to unpickle or parse binary formats produced by untrusted code.
  *.parquet          -> numeric columns, row-major
  *.pkl/.pickle/.joblib -> fitted attributes of an estimator (public names ending in "_") that are numeric
Only the standard library plus numpy/pandas/joblib already present in the repository's image are used.
"""
import json
import math
import os
import sys

OUT = "/work/.repromut/out"


def _flat(x):
    import numpy as np
    try:
        a = np.asarray(x, dtype=float).ravel()
    except (TypeError, ValueError):
        return None
    return [None if math.isnan(v) else float(v) for v in a.tolist()]


def convert(path):
    if path.endswith(".parquet"):
        import pandas as pd
        df = pd.read_parquet(path)
        return _flat(df.select_dtypes("number").to_numpy(dtype=float))
    if path.endswith((".pkl", ".pickle", ".joblib")):
        import joblib
        obj = joblib.load(path)
        vals = []
        for name in sorted(vars(obj)) if hasattr(obj, "__dict__") else []:
            if name.endswith("_") and not name.startswith("_"):
                f = _flat(getattr(obj, name))
                if f is not None:
                    vals.extend(f)
        return vals
    raise ValueError("unsupported")


def main(cwd, rels):
    os.makedirs(OUT, exist_ok=True)
    for rel in rels:
        try:
            res = {"ok": True, "values": convert(os.path.join(cwd, rel))}
        except Exception as e:  # recorded, never hidden
            res = {"ok": False, "error": type(e).__name__}
        with open(os.path.join(OUT, rel.replace("/", "__") + ".json"), "w") as fh:
            json.dump(res, fh)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
