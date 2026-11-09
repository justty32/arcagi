"""Additive think-4 CLI wiring; the legacy quick commands are unchanged."""

import argparse
import json
from pathlib import Path

from arcagi.hammer.formats import read_json, write_json

from . import dumb, meter, meter_suite

COMMANDS = ("meter-calibrate", "meter", "dumb", "meter-batch", "meter-accept")


def add_commands(commands: argparse._SubParsersAction) -> None:
    """Register the five block-A commands with explicit resource limits."""
    for name in ("meter-calibrate", "meter", "meter-batch"):
        parser = commands.add_parser(name)
        parser.add_argument("tree_json", type=Path)
        parser.add_argument("--L", type=int, default=50_000)
        parser.add_argument("--epochs", "--E", type=int, default=4)
        parser.add_argument("--strip", choices=("all", "targeted"), default="all")
        parser.add_argument("--base-dir", type=Path, default=meter.RUN_BASE)
        if name == "meter-batch":
            parser.add_argument("--jobs", type=int, choices=range(1, 5), default=4)
            parser.add_argument("--out", type=Path, required=True)
        else:
            parser.add_argument("--threads", type=int, choices=range(1, 5), default=1)
            parser.add_argument("--run-dir", type=Path)
            parser.add_argument("--label", default=name)
        if name == "meter-calibrate":
            parser.add_argument("--taskset-out", type=Path, required=True)
        else:
            parser.add_argument("--taskset", type=Path, required=True)
    parser = commands.add_parser("dumb")
    parser.add_argument("tree_json", type=Path)
    parser.add_argument("--recipe", choices=dumb.RECIPES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser = commands.add_parser("meter-accept")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fake", action="store_true")
    parser.add_argument("--fake-dir", type=Path)


def dispatch(args: argparse.Namespace) -> int:
    """Execute a meter command and return a meaningful acceptance exit code."""
    if args.command == "dumb":
        doc = dumb.make(args.tree_json, args.recipe, args.out)
        result = {
            "genome_sha": doc["genome_sha"],
            "out": str(args.out),
            "dumb": doc["dumb"],
        }
    elif args.command == "meter-batch":
        result = meter_suite.batch(
            args.tree_json,
            args.taskset,
            args.out,
            jobs=args.jobs,
            base_dir=args.base_dir,
            L=args.L,
            epochs=args.epochs,
            strip=args.strip,
        )
    elif args.command == "meter-accept":
        result = meter_suite.accept(
            args.manifest, args.out, fake=args.fake, fake_dir=args.fake_dir
        )
    else:
        if args.command == "meter-calibrate":
            ids = meter.source_tasks(args.tree_json)
        else:
            selected = read_json(args.taskset)
            ids = selected if isinstance(selected, list) else selected["task_ids"]
        sha = read_json(args.tree_json)["genome_sha"]
        directory = args.run_dir or meter.fresh_run(args.label, sha, args.base_dir)
        meter.prepare_meter(
            args.tree_json,
            directory,
            ids,
            args.strip,
            L=args.L,
            epochs=args.epochs,
            threads=args.threads,
        )
        report = meter.run(directory)
        verification = meter.verify(directory)
        result = {
            "run_dir": str(directory),
            "scores": report["scores"],
            "verify": verification,
            "pass": verification["pass"],
        }
        if args.command == "meter-calibrate":
            selection = meter.select_taskset(report)
            write_json(args.taskset_out, selection)
            result["selection"] = {
                k: selection[k]
                for k in (
                    "learning_tasks",
                    "needs_targeted",
                    "within_target",
                    "diagnosis",
                )
            }
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return int(not result.get("pass", True))
