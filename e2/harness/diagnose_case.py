"""Pilot diagnostic: run one case once and report which declared artifacts differ from baseline run #1.

Usage: python e2/harness/diagnose_case.py e2/plans/<slug>.json <results.jsonl> <case_id>
Diagnostics are not outcome records; they are used only to review pilot adapter behaviour.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from run_plan import WORK, tracked_files  # noqa: E402

from repromut.e2 import outputs as O  # noqa: E402
from repromut.e2.cases import CaseSpec  # noqa: E402
from repromut.e2.study import RepoPlan, _execute_once  # noqa: E402
from repromut.e2 import container as C  # noqa: E402


def main(plan_path, results, case_id):
    plan = json.loads(Path(plan_path).read_text())
    tree = Path(plan["source_tree"]).expanduser()
    slug = plan["repo"].replace("/", "__")
    rp = RepoPlan(plan["repo"], tree, plan["argv"], O.AdapterSpec.from_dict(plan["adapter"]), tracked_files(tree),
                  plan["images"], {k: Path(v).expanduser().read_text() for k, v in plan["packages"].items()},
                  [CaseSpec.from_dict(c) for c in plan["cases"]], WORK / "artifacts" / slug,
                  plan.get("cwd_rel", ""), plan.get("timeout_s", 600))
    base = next(json.loads(l) for l in open(results) if json.loads(l)["case_id"] == "baseline")
    b0 = O.from_jsonable(base["outputs"][0])
    case = next(c for c in rp.cases if c.case_id == case_id)
    run = _execute_once(rp, case, WORK / "runs" / f"diag-{slug}-{case_id}", C.run)
    print("status", run.obs.status)
    if run.obs.outputs is None:
        print(run.raw.stderr[-1500:])
        return
    for k in b0:
        a, b = b0[k], run.obs.outputs.get(k)
        same = b is not None and a.shape == b.shape and np.allclose(a, b, rtol=O.RTOL, atol=O.ATOL, equal_nan=True)
        print(f"{k}: {'same' if same else 'DIFFERS'} len {len(a)} vs {None if b is None else len(b)}")
        if not same and b is not None and a.shape == b.shape:
            idx = np.where(~np.isclose(a, b, rtol=O.RTOL, atol=O.ATOL, equal_nan=True))[0]
            print("   n_diff", len(idx), "first", [(int(i), a[i], b[i]) for i in idx[:5]])
    print(run.raw.stdout[-1200:])


if __name__ == "__main__":
    main(*sys.argv[1:4])
