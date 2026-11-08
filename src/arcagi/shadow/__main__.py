"""CLI: ``python -m arcagi.shadow <block folder | _rule.json | folder of blocks ...>``.

Prints a markdown table and a JSON summary; ``--out`` writes every verdict as
JSON. Never writes ``aos/blocks``. ``--status`` filters loaded blocks.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from arcagi.blocks import REPO_ROOT

from . import CHUNK, gate
from .blocks import load_paths
from .reference import confusion, labels
from .support import views


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow-gate candidate blocks.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--synth", type=Path, default=REPO_ROOT / "data_synth")
    parser.add_argument("--blocks-root", type=Path, default=None)
    parser.add_argument("--kind", nargs="+", default=None)
    parser.add_argument("--status", nargs="+", default=None)
    parser.add_argument("--chunk", type=int, default=CHUNK)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true", help="summary only")
    parser.add_argument(
        "--reference", type=Path, default=None, help="S5 overfit.json to compare"
    )
    args = parser.parse_args(argv)
    t0 = time.perf_counter()
    blocks, bad = load_paths(args.paths)
    if args.kind:
        blocks = [b for b in blocks if b["kind"] in args.kind]
    if args.status:
        blocks = [b for b in blocks if b["status"] in args.status]
    orig, chunks = views(args.synth, args.chunk)
    results = gate.run(blocks, orig, chunks, args.blocks_root)
    report = {
        "schema": "arcagi-shadow/1",
        "summary": gate.summary(results),
        "unreadable": bad,
        "seconds": round(time.perf_counter() - t0, 1),
        "results": results,
    }
    if args.reference:
        report["reference"] = confusion(results, labels(args.reference))
        print(json.dumps(report["reference"]))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n")
    if not args.quiet:
        print(gate.table(results))
    print(
        json.dumps(report["summary"] | {"seconds": report["seconds"]}), file=sys.stdout
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
