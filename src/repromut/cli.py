"""Command-line interface: ``repromut <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .auditors import audit_combined, audit_dynamic, audit_seed_only, audit_static, make_record
from .benchmark import run_benchmark
from .experiments import build_catalog
from .mutations import BY_ID, CATALOG
from .runner import execute, write_package


def _cmd_list(args) -> int:
    for m in CATALOG:
        print(f"{m.id:28s} {m.kind:8s} {m.family:16s} {m.expected_stage or '-':10s} {m.description}")
    return 0


def _cmd_export(args) -> int:
    """Write a baseline package (optionally mutated) plus its reported record."""
    specs = {s.config["name"]: s for s in build_catalog()}
    if args.experiment not in specs:
        print(f"unknown experiment; choose from: {', '.join(specs)}", file=sys.stderr)
        return 2
    spec = specs[args.experiment]
    record = make_record(spec.config, execute(spec))
    if args.mutation:
        if args.mutation not in BY_ID:
            print(f"unknown mutation: {args.mutation}", file=sys.stderr)
            return 2
        spec = BY_ID[args.mutation].apply(spec)
    out = Path(args.out)
    write_package(spec, out / "package")
    (out / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"wrote {out / 'package'} and {out / 'record.json'}")
    return 0


def _cmd_audit(args) -> int:
    record = json.loads(Path(args.record).read_text())
    pkg = Path(args.package)
    st = audit_static(pkg, record)
    dy = audit_dynamic(pkg, record, repeats=args.repeats)
    verdicts = [audit_seed_only(pkg, record), st, dy,
                audit_combined(pkg, record, static=st, dynamic=dy)]
    for v in verdicts:
        print(f"{v.method:16s} flagged={str(v.flagged):5s} stage={v.stage or '-':10s} {v.reason}")
    return 1 if dy.flagged else 0


def _cmd_bench(args) -> int:
    summary = run_benchmark(Path(args.out), smoke=args.smoke,
                            dynamic_repeats=args.repeats, oracle_repeats=args.oracle_repeats,
                            progress=(lambda n: print(f"\r{n} cases", end="", file=sys.stderr)))
    print(file=sys.stderr)
    print((Path(args.out) / "summary.md").read_text())
    agree = summary["oracle_agreement"]
    return 0 if agree["agree"] == agree["total"] else 3


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="repromut", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-mutations").set_defaults(func=_cmd_list)
    e = sub.add_parser("export", help="write a (mutated) package and its reported record")
    e.add_argument("experiment")
    e.add_argument("--mutation")
    e.add_argument("--out", required=True)
    e.set_defaults(func=_cmd_export)
    a = sub.add_parser("audit", help="audit a package against a reported record")
    a.add_argument("package")
    a.add_argument("--record", required=True)
    a.add_argument("--repeats", type=int, default=2)
    a.set_defaults(func=_cmd_audit)
    b = sub.add_parser("bench", help="run the benchmark")
    b.add_argument("--out", required=True)
    b.add_argument("--smoke", action="store_true")
    b.add_argument("--repeats", type=int, default=2)
    b.add_argument("--oracle-repeats", type=int, default=3)
    b.set_defaults(func=_cmd_bench)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
