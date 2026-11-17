"""E3 population snapshot and order (E3 protocol draft §2.1-§2.5).

Takes the GitHub search snapshot of P4 (primary) and P5 (fallback) once, verifies it, saves it,
and builds each population's seeded review order. It reads only GitHub search metadata; it does
not download or run any repository.

Usage (from the repository root, after the protocol draft is committed):
    python e3/screening/snapshot.py --dry-run       # print the queries and checks; no network
    python e3/screening/snapshot.py                 # take the snapshot, then build the order
    python e3/screening/snapshot.py --order-only    # rebuild the order from the saved snapshot

Authentication: none by default (about 10 search requests a minute; expect roughly 20-30 minutes).
To go faster, export REPROMUT_GITHUB_TOKEN with a token from the personal GitHub account only
(INDEPENDENCE.md); never a work account. The token is only sent to api.github.com and is never
written to disk; the manifest records only whether one was used.

Outputs (commit all of them, with this script):
    e3/screening/snapshot/MANIFEST.json            when, from which commit, which queries, counts
    e3/screening/snapshot/<P4|P5>/<slice>.json     each slice's query, counts and repositories
    e3/screening/<P4|P5>/order.json                the seeded review order (protocol §2.3-§2.4)

A snapshot is taken once. The script refuses to overwrite an existing one; retaking it is a
deviation that must be recorded in e3/DEVIATIONS.md before deleting the old snapshot.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "e3" / "screening"
SNAP = OUT / "snapshot"
PROTOCOL = ROOT / "e3" / "E3-PROTOCOL-DRAFT.md"
E2_MANIFEST = ROOT / "e2" / "REPOSITORY-MANIFEST.json"

LICENCES = "license:mit license:apache-2.0 license:bsd-3-clause license:bsd-2-clause"
P4_BASE = f"topic:scikit-learn language:Python stars:<10 fork:false size:<=20000 {LICENCES}"
P5_BASE = f"language:Python fork:false size:<=20000 {LICENCES} -topic:scikit-learn -topic:sklearn -topic:mlops"
WINDOW = ("2018-01-01", "2026-06-30")

# (population, slice name, query without the created: range, created range) - protocol §2.1 and §2.2
SLICES: list[tuple[str, str, str, tuple[str, str]]] = [
    ("P4", "P4-a", P4_BASE, ("2018-01-01", "2022-12-31")),
    ("P4", "P4-b", P4_BASE, ("2023-01-01", "2023-12-31")),
    ("P4", "P4-c", P4_BASE, ("2024-01-01", "2024-12-31")),
    ("P4", "P4-d", P4_BASE, ("2025-01-01", "2025-06-30")),
    ("P4", "P4-e", P4_BASE, ("2025-07-01", "2025-12-31")),
    ("P4", "P4-f", P4_BASE, ("2026-01-01", "2026-03-31")),
    ("P4", "P4-g", P4_BASE, ("2026-04-01", "2026-06-30")),
    ("P5", "P5-random-forest", f"topic:random-forest {P5_BASE}", WINDOW),
    ("P5", "P5-xgboost", f"topic:xgboost {P5_BASE}", WINDOW),
    ("P5", "P5-regression", f"topic:regression {P5_BASE}", WINDOW),
    ("P5", "P5-logistic-regression", f"topic:logistic-regression {P5_BASE}", WINDOW),
    ("P5", "P5-feature-engineering", f"topic:feature-engineering {P5_BASE}", WINDOW),
    ("P5", "P5-supervised-learning", f"topic:supervised-learning {P5_BASE}", WINDOW),
    ("P5", "P5-classification-a", f"topic:classification {P5_BASE}", ("2018-01-01", "2022-12-31")),
    ("P5", "P5-classification-b", f"topic:classification {P5_BASE}", ("2023-01-01", "2026-06-30")),
]
SEED_TEXT = {"P4": "ReproMut-E3|10.5281/zenodo.24090849|P4", "P5": "ReproMut-E3|10.5281/zenodo.24090849|P5"}
CAP = 1000          # GitHub search returns at most 1,000 results per query
PER_PAGE = 100      # each query is narrowed until its results fit on one page
ATTEMPTS = 3        # re-fetch a query whose results do not add up to its total_count

Getter = Callable[[str, int], dict]


def seed_of(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16) % 2**32


def query(base: str, created: tuple[str, str]) -> str:
    return f"{base} created:{created[0]}..{created[1]}"


def halve(created: tuple[str, str]) -> list[tuple[str, str]]:
    """Protocol §2.1: a slice at the cap is split into two halves by date (inclusive ranges)."""
    a, b = (dt.date.fromisoformat(x) for x in created)
    if a >= b:
        raise ValueError(f"cannot split a one-day range {created}")
    mid = a + (b - a) // 2
    return [(a.isoformat(), mid.isoformat()), ((mid + dt.timedelta(days=1)).isoformat(), b.isoformat())]


def normalise(item: dict) -> dict:
    """Keep E2's raw-snapshot fields (so E2's screening code reads them unchanged), plus id and topics."""
    lic = item.get("license") or None
    return {
        "id": item["id"], "fullName": item["full_name"], "url": item["html_url"],
        "description": item.get("description"), "createdAt": item.get("created_at"),
        "pushedAt": item.get("pushed_at"), "defaultBranch": item.get("default_branch"),
        "isArchived": item.get("archived"), "isFork": item.get("fork"), "language": item.get("language"),
        "license": ({"key": lic.get("key"), "name": lic.get("name"), "spdx_id": lic.get("spdx_id")} if lic else None),
        "size": item.get("size"), "stargazersCount": item.get("stargazers_count"), "topics": item.get("topics") or [],
    }


# ----------------------------------------------------------------------------- network
def github_getter(token: str | None, min_interval: float) -> Getter:
    last = [0.0]

    def get(q: str, page: int) -> dict:
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": q, "per_page": PER_PAGE, "page": page})
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "repromut-e3-snapshot",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        for attempt in range(8):
            wait = min_interval - (time.monotonic() - last[0])
            if wait > 0:
                time.sleep(wait)
            last[0] = time.monotonic()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    reset = e.headers.get("Retry-After") or ""
                    if not reset and e.headers.get("X-RateLimit-Reset"):
                        reset = str(max(0, int(e.headers["X-RateLimit-Reset"]) - int(time.time())))
                    delay = min(int(reset) + 2 if reset.isdigit() else 60, 900)
                    print(f"    rate limited; waiting {delay}s", flush=True)
                    time.sleep(delay)
                    continue
                if e.code >= 500:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise
            except urllib.error.URLError:
                time.sleep(10 * (attempt + 1))
        raise RuntimeError(f"GitHub search failed repeatedly for page {page} of: {q}")
    return get


def fetch_query(q: str, get: Getter, paginate: bool = False) -> dict:
    """Fetch one query. Normally the query fits on one page (at most 100 results), which avoids
    GitHub's search pagination: with its default ordering, later pages can repeat or skip results
    (seen on 2026-11-16: 166 of 170 after three attempts). Pagination is used only for a single-day
    range that still has more than 100 results. Verified when the unique repositories returned equal
    total_count and GitHub did not flag incomplete results; retried up to ATTEMPTS times otherwise."""
    rec: dict = {}
    for attempt in range(1, ATTEMPTS + 1):
        items: dict[str, dict] = {}
        total, incomplete = None, False
        for page in range(1, (CAP // PER_PAGE if paginate else 1) + 1):
            d = get(q, page)
            total = d["total_count"]
            incomplete = incomplete or bool(d.get("incomplete_results"))
            if total > PER_PAGE and not paginate:
                return {"total_count": total, "fits_one_page": False}
            for it in d["items"]:
                items.setdefault(it["full_name"].lower(), normalise(it))
            if len(d["items"]) < PER_PAGE or page * PER_PAGE >= total:
                break
        rec = {"total_count": total, "fits_one_page": total <= PER_PAGE, "n_items": len(items),
               "incomplete_results": incomplete, "attempts": attempt,
               "verified": (not incomplete) and len(items) == total, "items": items}
        if rec["verified"]:
            break
    return rec


def fetch_parts(base: str, created: tuple[str, str], get: Getter) -> list[dict]:
    """Halve the created range until each part fits on one page; returns the parts in date order."""
    q = query(base, created)
    r = fetch_query(q, get)
    if not r["fits_one_page"]:
        if created[0] == created[1]:
            r = fetch_query(q, get, paginate=True)          # cannot split a single day any further
        else:
            return [p for half in halve(created) for p in fetch_parts(base, half, get)]
    return [{"query": q, "created": list(created), **r}]


def fetch_slice(pop: str, name: str, base: str, created: tuple[str, str], get: Getter,
                log: Callable[[str], None] = print) -> dict:
    """One protocol slice. Its own total_count is checked against the union of its parts, which
    partition the slice's date range, so the population is exactly the slice query's results."""
    q = query(base, created)
    head = get(q, 1)
    parts = fetch_parts(base, created, get)
    items: dict[str, dict] = {}
    for p in parts:
        for k, v in p.pop("items").items():
            items.setdefault(k, v)
    total = head["total_count"]
    verified = all(p["verified"] for p in parts) and sum(p["total_count"] for p in parts) == total == len(items)
    log(f"  {name}: total_count {total}, {len(parts)} part(s), {len(items)} unique, verified {verified}")
    return {"population": pop, "slice": name, "query": q, "created": list(created),
            "fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_count": total, "reached_search_cap": total >= CAP, "n_items": len(items),
            "verified": verified, "parts": parts,
            "items": sorted(items.values(), key=lambda r: r["fullName"].lower())}


# ----------------------------------------------------------------------------- order (§2.3-§2.4)
def build_order(pop: str, slices: list[dict], e2_names: set[str], p4_order: list[dict] | None) -> dict:
    merged: dict[str, dict] = {}
    for s in slices:
        for it in s["items"]:
            merged.setdefault(it["fullName"].lower(), it)
    removed_e2 = sorted(n for n in merged if n in e2_names)
    removed_p4: list[str] = []
    if p4_order is not None:
        p4_names = {r["fullName"].lower() for r in p4_order}
        p4_ids = {r["id"] for r in p4_order}
        removed_p4 = sorted(n for n, it in merged.items() if n in p4_names or it["id"] in p4_ids)
    drop = set(removed_e2) | set(removed_p4)
    names = sorted(n for n in merged if n not in drop)
    seed = seed_of(SEED_TEXT[pop])
    random.Random(seed).shuffle(names)
    return {"population": pop, "seed_text": SEED_TEXT[pop], "seed": seed,
            "n_in_snapshot": len(merged), "removed_already_screened_in_e2": removed_e2,
            "removed_in_p4": removed_p4, "n_ordered": len(names),
            "repositories": [dict(merged[n], order=i) for i, n in enumerate(names)]}


def e2_screened_names() -> set[str]:
    m = json.loads(E2_MANIFEST.read_text())
    return {r["repo"].lower() for r in m["repositories"]}


def write_orders() -> dict:
    out = {}
    e2 = e2_screened_names()
    for pop in ("P4", "P5"):
        slices = [json.loads(f.read_text()) for f in sorted((SNAP / pop).glob("*.json"))]
        p4 = out["P4"]["repositories"] if pop == "P5" else None
        out[pop] = build_order(pop, slices, e2, p4)
        (OUT / pop).mkdir(parents=True, exist_ok=True)
        (OUT / pop / "order.json").write_text(json.dumps(out[pop], indent=1))
        print(f"{pop}: {out[pop]['n_in_snapshot']} in snapshot, {len(out[pop]['removed_already_screened_in_e2'])} "
              f"already screened in E2, {len(out[pop]['removed_in_p4'])} also in P4, {out[pop]['n_ordered']} ordered")
    return out


# ----------------------------------------------------------------------------- integrity
def protocol_state() -> dict:
    """The protocol draft must be committed and unchanged before the snapshot (§2.5)."""
    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    tracked = git("ls-files", "--error-unmatch", str(PROTOCOL.relative_to(ROOT))).returncode == 0
    dirty = git("status", "--porcelain", "--", str(PROTOCOL.relative_to(ROOT))).stdout.strip()
    head = git("rev-parse", "HEAD").stdout.strip()
    return {"git_head": head, "protocol_tracked": tracked, "protocol_clean": tracked and not dirty}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv: list[str] | None = None, get: Getter | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print queries and checks; no network")
    ap.add_argument("--order-only", action="store_true", help="rebuild order.json from the saved snapshot")
    args = ap.parse_args(argv)
    if args.order_only:
        if not (SNAP / "MANIFEST.json").exists():
            print("NOT READY: no saved snapshot"); return 2
        write_orders(); return 0
    print("Queries (protocol §2.1-§2.2):")
    for pop, name, base, created in SLICES:
        print(f"  {name}: {query(base, created)}")
    print("Seeds:", {p: seed_of(t) for p, t in SEED_TEXT.items()})
    state = protocol_state()
    token = os.environ.get("REPROMUT_GITHUB_TOKEN") or None
    print(f"Protocol committed and unchanged: {state['protocol_clean']} (HEAD {state['git_head'][:7] or '?'}); "
          f"authenticated: {bool(token)}")
    problems = []
    if not state["protocol_clean"]:
        problems.append("e3/E3-PROTOCOL-DRAFT.md must be committed with no local changes (§2.5)")
    if (SNAP / "MANIFEST.json").exists():
        problems.append("a snapshot already exists; retaking it is a deviation (see the docstring)")
    if problems:
        print("NOT READY:\n  " + "\n  ".join(problems)); return 2
    if args.dry_run:
        print("Ready. Nothing was fetched."); return 0
    get = get or github_getter(token, 2.2 if token else 6.5)
    started = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    saved = []
    for pop, name, base, created in SLICES:
        s = fetch_slice(pop, name, base, created, get)
        (SNAP / pop).mkdir(parents=True, exist_ok=True)
        (SNAP / pop / f"{name}.json").write_text(json.dumps(s, indent=1))
        saved.append({k: v for k, v in s.items() if k not in ("items", "parts")} | {"n_parts": len(s["parts"])})
    manifest = {
        "snapshot_started_utc": started,
        "snapshot_finished_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **state, "protocol_sha256": sha256_file(PROTOCOL), "script_sha256": sha256_file(Path(__file__)),
        "python": platform.python_version(), "authenticated": bool(token),
        "endpoint": "https://api.github.com/search/repositories", "per_page": PER_PAGE,
        "all_slices_verified": all(s["verified"] for s in saved), "slices": saved,
    }
    (SNAP / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print(f"Snapshot saved: {len(saved)} slices, all verified: {manifest['all_slices_verified']}")
    if not manifest["all_slices_verified"]:
        print("WARNING: at least one slice's parts did not add up to its total_count after "
              f"{ATTEMPTS} attempts; record it in e3/DEVIATIONS.md before screening.")
    write_orders()
    return 0


if __name__ == "__main__":
    sys.exit(main())
