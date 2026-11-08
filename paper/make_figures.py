"""Generate paper figures and the LaTeX results macros from a benchmark run.

Usage: python paper/make_figures.py results/dev-2026-11-08 paper/figures
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

LABELS = {"no_audit": "No audit", "seed_only": "Seed-only", "static_manifest": "Static manifest",
          "dynamic": "Dynamic", "combined": "Combined"}


def main(run_dir: str, out_dir: str) -> None:
    run, out = Path(run_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    s = json.loads((run / "summary.json").read_text())
    methods = list(LABELS)
    plt.rcParams.update({"font.size": 8, "font.family": "serif"})

    # Figure 1: recall by mutation family (heatmap)
    fams = sorted(s["methods"]["dynamic"]["recall_by_family"])
    M = np.array([[s["methods"][m]["recall_by_family"][f]["detected"] /
                   s["methods"][m]["recall_by_family"][f]["total"] for m in methods] for f in fams])
    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    im = ax.imshow(M, cmap="Greys", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(methods)), [LABELS[m] for m in methods], rotation=25, ha="right")
    totals = [s["methods"]["dynamic"]["recall_by_family"][f]["total"] for f in fams]
    ax.set_yticks(range(len(fams)), [f"{f} (n={n})" for f, n in zip(fams, totals)])
    for i in range(len(fams)):
        for j in range(len(methods)):
            ax.text(j, i, f"{M[i, j]:.0%}", ha="center", va="center",
                    color="white" if M[i, j] > 0.5 else "black", fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, label="Recall")
    fig.tight_layout()
    fig.savefig(out / "recall_by_family.pdf")
    plt.close(fig)

    # Figure 2: recall and false-positive rate with Wilson 95% CIs
    fig, ax = plt.subplots(figsize=(4.6, 2.3))
    x = np.arange(len(methods))
    for off, key, ci, lab, hatch in ((-0.18, "recall", "recall_ci95", "Recall (positives)", None),
                                     (0.18, "fpr", "fpr_ci95", "False-positive rate (controls)", "///")):
        vals = np.array([s["methods"][m][key] for m in methods])
        lo = np.array([s["methods"][m][ci][0] for m in methods])
        hi = np.array([s["methods"][m][ci][1] for m in methods])
        ax.bar(x + off, vals, 0.34, yerr=[vals - lo, hi - vals], capsize=2, label=lab,
               color="0.35" if hatch is None else "white", edgecolor="black", hatch=hatch, linewidth=0.6)
    ax.set_xticks(x, [LABELS[m] for m in methods])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Proportion")
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "recall_fpr.pdf")
    plt.close(fig)
    print("figures written to", out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
