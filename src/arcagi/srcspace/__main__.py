"""CLI: ``python -m arcagi.srcspace {emit,parse,roundtrip,mine}``."""

import argparse
import json
import sys
from pathlib import Path

from arcagi.blocks import default_blocks_root

from . import janet_bridge
from .emit import to_janet
from .parse import from_janet
from .roundtrip import block_objects, roundtrip, trace_programs

DEFAULT_TRACES = Path("artifacts/r04/dsl-training-traces.jsonl")


def _read(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def cmd_emit(args) -> int:
    base = None if args.path == "-" else Path(args.path).resolve().parent
    sys.stdout.write(to_janet(json.loads(_read(args.path)), base=base))
    return 0


def cmd_parse(args) -> int:
    print(json.dumps(from_janet(_read(args.path)), ensure_ascii=False))
    return 0


def cmd_roundtrip(args) -> int:
    objects = list(block_objects(args.root)) + list(trace_programs(args.traces))
    report = roundtrip(objects)
    print(f"roundtrip {report.passed}/{report.checked}")
    for failure in report.failures[:20]:
        print("  FAIL", failure)
    if args.janet:
        results = janet_bridge.check_all(report.texts)
        if results and results[0] is None:
            print("janet: not available (skipped)")
        else:
            print(f"janet parse {sum(1 for r in results if r)}/{len(results)}")
    return 0 if not report.failures else 1


def cmd_mine(args) -> int:
    from .mine import mine

    for line in mine(args.traces, args.root, args.min_tasks, write=args.write):
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m arcagi.srcspace")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("emit", cmd_emit), ("parse", cmd_parse)):
        p = sub.add_parser(name)
        p.add_argument("path", help="file or - for stdin")
        p.set_defaults(fn=fn)
    p = sub.add_parser("roundtrip")
    p.add_argument("--root", type=Path, default=default_blocks_root())
    p.add_argument("--traces", type=Path, nargs="*", default=[DEFAULT_TRACES])
    p.add_argument("--janet", action="store_true", help="also janet-parse the text")
    p.set_defaults(fn=cmd_roundtrip)
    p = sub.add_parser("mine")
    p.add_argument("--root", type=Path, default=default_blocks_root())
    p.add_argument("--traces", type=Path, nargs="+", default=[DEFAULT_TRACES])
    p.add_argument("--min-tasks", type=int, default=3)
    p.add_argument("--write", action="store_true")
    p.set_defaults(fn=cmd_mine)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
