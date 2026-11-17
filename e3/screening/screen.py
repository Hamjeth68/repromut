"""E3 static screening (protocol §2.6): E2's automated rules X1-X12, applied in seeded order.

The rules are E2's, unchanged: this script loads e2/screening/prescreen.py and calls its screen()
function, so the keyword lists, entry-point and hidden-state checks, and archive handling are
exactly E2's (including refinements S2-S4). Only the transport differs: E2 called GitHub through
the `gh` command-line tool; E3 calls the GitHub REST API directly with a personal token, so no
other login on the machine is ever used. Repositories are read as text only; nothing is executed.

Usage (from the repository root, after the snapshot and order are committed):
    python e3/screening/screen.py --population P4 --dry-run
    read -s REPROMUT_GITHUB_TOKEN && export REPROMUT_GITHUB_TOKEN    # personal account, read-only
    caffeinate -i python e3/screening/screen.py --population P4
    unset REPROMUT_GITHUB_TOKEN

It resumes where it stopped, so it can be interrupted and run again.

Outputs:
    e3/screening/<P>/screening.jsonl    one record per repository, in seeded order (commit it)
    ~/repromut-e3-work/screening/<P>/src/<owner__repo>    extracted sources, kept only for static
        passes and for repositories excluded only by X6 (which manual rule M2' reviews); every other
        repository's source is deleted once its record is written, as E2 did (S12).

The token is read from the environment, sent only to api.github.com (never forwarded on redirects),
and never written to disk or printed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "e3" / "screening"
WORK = Path.home() / "repromut-e3-work" / "screening"
E2_PRESCREEN = ROOT / "e2" / "screening" / "prescreen.py"
X6_ONLY = ["X6 network/data download in code"]
MIN_FREE_BYTES = 8 * 1024**3
RETRY_WAIT_S = 30
HAS_DATA_FILTER = hasattr(tarfile, "data_filter")   # E2 extraction needs it (Python 3.12+, 3.10.12+, 3.11.4+)


def load_e2_rules():
    """Import E2's prescreen.py as a module without running its main(). It reads sys.argv at import
    time to locate its own folders; it is given none, and its folder is replaced afterwards."""
    spec = importlib.util.spec_from_file_location("e2_prescreen", E2_PRESCREEN)
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = [saved[0]]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


class GitHub:
    """Drop-in replacement for E2's gh(path, raw=False), using the REST API and a personal token."""

    def __init__(self, token: str, urlopen=urllib.request.urlopen, sleep: Callable[[float], None] = time.sleep):
        self._token, self._urlopen, self._sleep = token, urlopen, sleep

    def __call__(self, path: str, raw: bool = False):
        url = "https://api.github.com/" + path.lstrip("/")
        for attempt in range(6):
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "repromut-e3-screen",
                                                       "X-GitHub-Api-Version": "2022-11-28"})
            req.add_unredirected_header("Authorization", f"Bearer {self._token}")  # not sent to codeload
            try:
                with self._urlopen(req, timeout=180) as r:
                    body = r.read()
                    if r.headers.get("X-RateLimit-Remaining") == "0":
                        self._wait_for_reset(r.headers)
                    return body if raw else json.loads(body)
            except urllib.error.HTTPError as e:
                if e.code in (403, 429) and (e.headers.get("X-RateLimit-Remaining") == "0" or e.headers.get("Retry-After")):
                    self._wait_for_reset(e.headers)
                    continue
                if e.code >= 500:
                    self._sleep(15 * (attempt + 1))
                    continue
                raise RuntimeError(f"HTTP {e.code} for {path}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                self._sleep(15 * (attempt + 1))
        raise RuntimeError(f"GitHub API failed repeatedly for {path}")

    def _wait_for_reset(self, headers) -> None:
        if headers.get("Retry-After", "").isdigit():
            delay = int(headers["Retry-After"]) + 1
        else:
            delay = max(0, int(headers.get("X-RateLimit-Reset", time.time() + 60)) - int(time.time())) + 2
        print(f"    rate limit reached; waiting {delay}s", flush=True)
        self._sleep(min(delay, 3700))


def keep_source(rec: dict) -> bool:
    return bool(rec.get("static_pass")) or rec.get("reasons") == X6_ONLY


def screen_one(ps, meta: dict, sleep: Callable[[float], None] = time.sleep) -> dict:
    """E2's screen(), with one retry after an infrastructure error (E2 S12 retried failures once).
    A partly extracted source is removed before the retry so it is never screened half-complete."""
    dest = ps.HERE / "src" / meta["fullName"].replace("/", "__")
    try:
        return ps.screen(meta)
    except Exception as e1:  # noqa: BLE001 - recorded, never hidden
        first = str(e1)[:200]
    shutil.rmtree(dest, ignore_errors=True)
    sleep(RETRY_WAIT_S)
    try:
        rec = ps.screen(meta)
    except Exception as e2:  # noqa: BLE001
        shutil.rmtree(dest, ignore_errors=True)
        rec = {"repo": meta["fullName"], "url": meta["url"], "reasons": [f"INFRA {str(e2)[:200]}"],
               "static_pass": False}
    rec["first_attempt_error"] = first
    return rec


def committed_and_clean(path: Path) -> bool:
    rel = str(path.relative_to(ROOT))
    git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    return git("ls-files", "--error-unmatch", rel).returncode == 0 and not git("status", "--porcelain", "--", rel).stdout.strip()


def summarise(records: list[dict]) -> dict:
    first = Counter((r["reasons"][0].split(" ")[0] if r["reasons"] else "PASS") for r in records)
    return {"screened": len(records), "static_pass": sum(1 for r in records if r.get("static_pass")),
            "x6_only": sum(1 for r in records if r.get("reasons") == X6_ONLY),
            "infra": sum(1 for r in records if r["reasons"] and r["reasons"][0].startswith("INFRA")),
            "first_reason": dict(sorted(first.items()))}


def main(argv: list[str] | None = None, gh=None, sleep: Callable[[float], None] = time.sleep) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--population", choices=["P4", "P5"], default="P4")
    ap.add_argument("--dry-run", action="store_true", help="check readiness; contact nothing")
    ap.add_argument("--limit", type=int, default=None, help="screen at most this many new repositories")
    args = ap.parse_args(argv)
    pop = args.population
    order_file = OUT / pop / "order.json"
    out = OUT / pop / "screening.jsonl"
    order = json.loads(order_file.read_text())["repositories"]
    done = {json.loads(l)["repo"] for l in out.read_text().splitlines()} if out.exists() else set()
    token = os.environ.get("REPROMUT_GITHUB_TOKEN") or None
    WORK.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(WORK).free
    print(f"{pop}: {len(order)} in seeded order, {len(done)} already screened, {len(order) - len(done)} to go")
    print(f"Token present: {bool(token)}; free disk: {free / 1024**3:.1f} GiB; sources in {WORK / pop / 'src'}")
    problems = []
    if not HAS_DATA_FILTER:
        problems.append("this Python has no tarfile 'data' filter; use Python 3.12+ (or 3.10.12+/3.11.4+)")
    if not committed_and_clean(order_file):
        shown = order_file.relative_to(ROOT) if order_file.is_relative_to(ROOT) else order_file
        problems.append(f"{shown} must be committed with no local changes")
    if free < MIN_FREE_BYTES:
        problems.append("less than 8 GiB free disk")
    if not token and not args.dry_run and gh is None:
        problems.append("set REPROMUT_GITHUB_TOKEN (personal account, read-only); without it GitHub "
                        "allows 60 API calls an hour, which would take days")
    if problems:
        print("NOT READY:\n  " + "\n  ".join(problems)); return 2
    if args.dry_run:
        print("Ready. Nothing was contacted."); return 0
    ps = load_e2_rules()
    ps.HERE = WORK / pop
    ps.gh = gh or GitHub(token, sleep=sleep)
    n_new = 0
    with out.open("a") as fh:
        for meta in order:
            if meta["fullName"] in done:
                continue
            if args.limit is not None and n_new >= args.limit:
                break
            if shutil.disk_usage(WORK).free < MIN_FREE_BYTES:
                print("Stopping: less than 8 GiB free disk. Free some space and run again to resume."); return 3
            rec = screen_one(ps, meta, sleep)
            rec["order"] = meta["order"]
            rec["screened_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if not keep_source(rec):
                shutil.rmtree(ps.HERE / "src" / meta["fullName"].replace("/", "__"), ignore_errors=True)
            n_new += 1
            print(meta["order"], rec["repo"], "PASS" if rec.get("static_pass") else rec["reasons"][:2], flush=True)
    records = [json.loads(l) for l in out.read_text().splitlines()]
    print(json.dumps(summarise(records)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
