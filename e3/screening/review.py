"""E3 manual review helper (protocol §2.6-§2.7): rules M1-M8 (M2' for X6-only), in seeded order.

For each static pass (and each repository excluded only by X6) it shows what the rules need:
the repository at its pinned commit, entry-point candidates, README and requirements excerpts, the
exact lines that match the hidden-state channels (for M6) or network access (for M2'), and possible
duplicates of repositories already accepted (for M8). You decide; it records the decision.

Nothing is executed. The repository's code is only read, from the copy kept by screen.py.

Usage (from the repository root):
    python e3/screening/review.py --status                 # counts only
    python e3/screening/review.py --population P4          # review in seeded order; q to stop, resumes later

Decisions are written to e3/screening/<P>/manual_review.jsonl (commit it). Review follows the
seeded order with no skipping, refuses to start before the protocol is registered
(e3/E3-PROTOCOL.md committed), and stops when 24 repositories are eligible across P4 and P5.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screen as SC  # noqa: E402

ROOT = SC.ROOT
OUT = SC.OUT
TARGET = 24
RULES = ["M1", "M2", "M2'", "M3", "M4", "M5", "M6", "M7", "M8"]
RULE_TEXT = {
    "M1": "batch experiment / training-evaluation script (not server, GUI, bot, notebook-only, interactive)",
    "M2": "all inputs available offline (committed, generated, or a non-medical bundled dataset)",
    "M2'": "(X6-only) every input fetchable at the networked build stage from a public, stable source",
    "M3": "statically plausible on CPU within 10 minutes",
    "M4": "produces numerical results (printed metrics or written arrays/tables/models)",
    "M5": "not high-stakes or sensitive, judged beyond keywords",
    "M6": "at least one hidden-state channel is real (on the computation path)",
    "M7": "no licence restriction on local execution or storing derived outputs",
    "M8": "not a duplicate of a repository already accepted earlier in seeded order",
}
NEAR_DUPLICATE = 0.90


# ----------------------------------------------------------------------------- data
def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def candidates(pop: str) -> list[dict]:
    """Static passes and X6-only repositories, in seeded order."""
    recs = load_jsonl(OUT / pop / "screening.jsonl")
    return sorted((r for r in recs if r.get("static_pass") or r.get("reasons") == SC.X6_ONLY), key=lambda r: r["order"])


def decisions(pop: str) -> list[dict]:
    return load_jsonl(OUT / pop / "manual_review.jsonl")


def n_eligible() -> int:
    return sum(1 for pop in ("P4", "P5") for d in decisions(pop) if d["decision"] == "eligible")


def source_dir(pop: str, repo: str) -> Path | None:
    base = SC.WORK / pop / "src" / repo.replace("/", "__")
    tops = [p for p in base.iterdir() if p.is_dir()] if base.exists() else []
    return tops[0] if len(tops) == 1 else (base if base.exists() else None)


# ----------------------------------------------------------------------------- M8 support
def normalise_code(text: str) -> str:
    """Drop comments, blank lines and spacing, so cosmetic edits do not hide a copy."""
    lines = (re.sub(r"\s+", " ", re.sub(r"#.*", "", l)).strip() for l in text.splitlines())
    return "\n".join(l for l in lines if l)


def entry_fingerprints(src: Path | None, entries: list[str]) -> dict[str, dict]:
    fp = {}
    for rel in entries:
        p = (src / rel) if src else None
        if p and p.is_file() and not p.is_symlink():
            text = p.read_text(errors="ignore")
            fp[rel] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "normalised": normalise_code(text)}
    return fp


def duplicate_flags(fp: dict[str, dict], accepted: list[dict]) -> list[str]:
    flags = []
    for acc in accepted:
        for rel_a, a in (acc.get("entry_fingerprints") or {}).items():
            for rel_b, b in fp.items():
                if a["sha256"] == b["sha256"]:
                    flags.append(f"byte-identical: {rel_b} = {acc['repo']}:{rel_a}")
                    continue
                ratio = difflib.SequenceMatcher(None, a["normalised"], b["normalised"]).ratio()
                if ratio >= NEAR_DUPLICATE:
                    flags.append(f"near-identical ({ratio:.2f}): {rel_b} ~ {acc['repo']}:{rel_a}")
    return flags


# ----------------------------------------------------------------------------- display
def matching_lines(src: Path | None, rx: re.Pattern, limit: int = 12) -> list[str]:
    if not src:
        return []
    hits = []
    for p in sorted(src.rglob("*.py")):
        if not p.is_file() or p.is_symlink() or p.stat().st_size >= 300_000:
            continue
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p.relative_to(src)}:{i}: {line.strip()[:110]}")
                if len(hits) >= limit:
                    return hits
    return hits


def excerpt(src: Path | None, pattern: str, n: int) -> list[str]:
    if not src:
        return []
    files = sorted(p for p in src.rglob("*") if p.is_file() and re.search(pattern, p.name, re.I))
    return [f"[{files[0].relative_to(src)}]", *files[0].read_text(errors="ignore").splitlines()[:n]] if files else []


def describe(rec: dict, pop: str, meta: dict, ps, accepted: list[dict]) -> tuple[str, dict]:
    src = source_dir(pop, rec["repo"])
    x6_only = rec.get("reasons") == SC.X6_ONLY
    fp = entry_fingerprints(src, rec.get("entry_candidates") or [])
    dups = duplicate_flags(fp, accepted)
    lines = [
        "=" * 100,
        f"#{rec['order']}  {rec['repo']}   stars {rec.get('stars')}   licence {rec.get('license')}",
        f"https://github.com/{rec['repo']}/tree/{rec.get('commit')}",
        f"Description: {(meta.get('description') or '')[:200]}",
        f"Local copy: {src}" if src else "Local copy: MISSING (re-run screen.py or fetch the pinned commit)",
        f"Static result: {'X6-only, so M2' + chr(8242) + ' applies instead of M2' if x6_only else 'PASS'};  "
        f"{rec.get('n_py')} .py, {rec.get('n_ipynb')} notebooks;  scikit-learn pinned: {rec.get('sklearn_pinned')}",
        f"Entry candidates: {', '.join(rec.get('entry_candidates') or []) or '-'}",
        f"Channels detected: {rec.get('channels')}",
    ]
    for title, rx in (("Environment reads (M6)", ps.ENV), ("Cache artifacts (M6)", ps.CACHE),
                      ("Relative paths (M6)", ps.RELPATH)):
        hits = matching_lines(src, rx)
        if hits:
            lines += [f"-- {title}:", *("   " + h for h in hits)]
    if x6_only:
        lines += ["-- Network access (M2'):", *("   " + h for h in matching_lines(src, ps.NETWORK))]
    for title, pat, n in (("README", r"^readme", 25), ("Requirements", r"requirements.*\.txt$|pyproject\.toml$", 15)):
        ex = excerpt(src, pat, n)
        if ex:
            lines += [f"-- {title} {ex[0]}", *("   " + l[:110] for l in ex[1:])]
    lines.append("-- M8 duplicates: " + ("; ".join(dups) if dups else "none found among accepted repositories"))
    return "\n".join(lines), {"entry_fingerprints": fp, "duplicate_flags": dups}


# ----------------------------------------------------------------------------- loop
def ask(prompt: str, valid: Callable[[str], bool], read: Callable[[str], str]) -> str:
    while True:
        a = read(prompt).strip()
        if valid(a):
            return a


def review(pop: str, read: Callable[[str], str] = input, write: Callable[[str], None] = print) -> int:
    ps = SC.load_e2_rules()
    metas = {r["fullName"]: r for r in json.loads((OUT / pop / "order.json").read_text())["repositories"]}
    done = {d["repo"] for d in decisions(pop)}
    accepted = [d for p in ("P4", "P5") for d in decisions(p) if d["decision"] == "eligible"]
    out = OUT / pop / "manual_review.jsonl"
    for rec in candidates(pop):
        if rec["repo"] in done:
            continue
        if n_eligible() >= TARGET:
            write(f"Target reached: {TARGET} eligible. Review stops here (protocol §2.7).")
            return 0
        text, extra = describe(rec, pop, metas.get(rec["repo"], {}), ps, accepted)
        write(text)
        write(f"Eligible so far: {n_eligible()} of {TARGET}.  Rules: " + ", ".join(RULES))
        a = ask("[e]ligible, e[x]clude, [r]ules, [q]uit: ", lambda s: s in {"e", "x", "r", "q"}, read)
        while a == "r":
            write("\n".join(f"  {k}: {v}" for k, v in RULE_TEXT.items()))
            a = ask("[e]ligible, e[x]clude, [q]uit: ", lambda s: s in {"e", "x", "q"}, read)
        if a == "q":
            write("Stopped. Run again to continue from this repository.")
            return 0
        d = {"repo": rec["repo"], "population": pop, "order": rec["order"], "commit": rec.get("commit"),
             "static_result": "X6-only" if rec.get("reasons") == SC.X6_ONLY else "pass"}
        if a == "x":
            allowed = [r for r in RULES if r != ("M2" if d["static_result"] == "X6-only" else "M2'")]
            d["decision"] = "exclude"
            d["rule"] = ask(f"Rule ({'/'.join(allowed)}): ", lambda s: s in allowed, read)
            d["reason"] = ask("Reason (one line): ", lambda s: bool(s), read)
        else:
            d["decision"] = "eligible"
            d["rule"] = ""
            d["entry_point"] = ask("Entry point command (e.g. python train.py): ", lambda s: bool(s), read)
            d["cwd"] = read("Working directory relative to the repository root (blank = root): ").strip()
            d["reason"] = ask("Why it is eligible (channels that are real, data, runtime): ", lambda s: bool(s), read)
            d["entry_fingerprints"] = extra["entry_fingerprints"]
        d["duplicate_flags"] = extra["duplicate_flags"]
        d["reviewed_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with out.open("a") as fh:
            fh.write(json.dumps(d) + "\n")
        if d["decision"] == "eligible":
            accepted.append(d)
        write(f"Recorded: {d['decision']} {d['rule']}".rstrip())
    write(f"{pop} candidates exhausted with {n_eligible()} eligible."
          + (" P5 is next (protocol §2.7)." if pop == "P4" and n_eligible() < TARGET else ""))
    return 0


def status() -> str:
    lines = []
    for pop in ("P4", "P5"):
        c, d = candidates(pop), decisions(pop)
        rules = {}
        for x in d:
            if x["decision"] == "exclude":
                rules[x["rule"]] = rules.get(x["rule"], 0) + 1
        lines.append(f"{pop}: {len(load_jsonl(OUT / pop / 'screening.jsonl'))} screened, {len(c)} candidates, "
                     f"{len(d)} reviewed, {sum(1 for x in d if x['decision'] == 'eligible')} eligible, excluded by rule {rules}")
    lines.append(f"Eligible in total: {n_eligible()} of {TARGET}")
    return "\n".join(lines)


def main(argv: list[str] | None = None, read: Callable[[str], str] = input, write: Callable[[str], None] = print) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--population", choices=["P4", "P5"], default="P4")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)
    if args.status:
        write(status()); return 0
    registered = ROOT / "e3" / "E3-PROTOCOL.md"
    if not (registered.exists() and SC.committed_and_clean(registered)):
        write("NOT READY: register the protocol first (commit e3/E3-PROTOCOL.md); manual review comes after registration.")
        return 2
    if not (OUT / args.population / "screening.jsonl").exists():
        write(f"NOT READY: no screening results for {args.population}; run screen.py first."); return 2
    if args.population == "P5" and any(c["repo"] not in {d["repo"] for d in decisions("P4")} for c in candidates("P4")):
        write("NOT READY: P5 is reviewed only after P4's candidates are exhausted (protocol §2.7)."); return 2
    return review(args.population, read, write)


if __name__ == "__main__":
    sys.exit(main())
