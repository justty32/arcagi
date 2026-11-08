"""Argument definitions and validation for every command-line subcommand."""

import argparse
import math
from pathlib import Path


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number of seconds")
    return number


def _add_dataset_args(parser: argparse.ArgumentParser, *, positional: bool) -> None:
    if positional:
        parser.add_argument("path", nargs="?", type=Path, help="Task JSON or directory")
    else:
        parser.add_argument("--tasks-dir", type=Path, help="Custom task JSON directory")
    parser.add_argument("--data-root", type=Path, default=Path("data/ARC-AGI"))
    parser.add_argument(
        "--split", choices=("training", "evaluation"), default="training"
    )
    parser.add_argument("--limit", type=_positive_int, help="Use first N sorted tasks")


def _add_solver_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout", type=_positive_seconds, help="Per-task timeout in seconds"
    )
    parser.add_argument(
        "--solver", default="identity", help="identity or module:function"
    )
    parser.add_argument(
        "--external",
        metavar="ARGV",
        help="External solver command (split like a shell, never run by one), "
        "e.g. 'sh solver.sh {input} {output} {trace}'; overrides --solver",
    )
    parser.add_argument("--name", help="Solver name recorded in the report")
    parser.add_argument(
        "--params", default="{}", help="JSON object passed to --external solvers"
    )
    parser.add_argument("--seed", type=int, default=0, help="Seed for --external")
    parser.add_argument("--cwd", type=Path, help="Working directory for --external")
    parser.add_argument(
        "--artifacts",
        type=Path,
        help="Directory for --external request/response/log files",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser without importing optional command modules."""
    parser = argparse.ArgumentParser(
        prog="arcagi",
        description="ARC-AGI-1 testing tools; no model training required.",
    )
    from arcagi import __version__

    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser(
        "validate", help="Validate task JSON grids and schema"
    )
    _add_dataset_args(validate, positional=True)
    validate.add_argument("--require-test-outputs", action="store_true")
    solve = commands.add_parser(
        "solve", help="Run a solver on one task (labels hidden)"
    )
    solve.add_argument("task", type=Path)
    _add_solver_args(solve)
    solve.add_argument(
        "--output", type=Path, help="Write predictions JSON to this file"
    )
    evaluate = commands.add_parser("eval", help="Measure exact-match top-1 accuracy")
    _add_dataset_args(evaluate, positional=False)
    _add_solver_args(evaluate)
    evaluate.add_argument("--output", type=Path, help="Write the complete JSON report")
    evaluate.add_argument(
        "--traces", type=Path, help="Write one JSONL line per task with its trace"
    )
    evaluate.add_argument(
        "--workers",
        type=_positive_int,
        default=1,
        help="Tasks run at once (needs --timeout or --external); report order kept",
    )
    score = commands.add_parser(
        "score", help="Score externally produced predictions JSON"
    )
    _add_dataset_args(score, positional=False)
    score.add_argument("--predictions", type=Path, required=True)
    score.add_argument("--output", type=Path, help="Write the complete JSON report")
    generate = commands.add_parser(
        "generate", help="Generate seeded RE-ARC practice tasks"
    )
    generate.add_argument("--output", type=Path, help="Destination for generated tasks")
    selection = generate.add_mutually_exclusive_group()
    selection.add_argument(
        "--task", action="append", dest="task_ids", help="Rule ID; repeatable"
    )
    selection.add_argument(
        "--all", action="store_true", help="Generate all 400 rule families"
    )
    generate.add_argument("--list", action="store_true", help="List available rule IDs")
    generate.add_argument("--seed", type=int, default=0)
    generate.add_argument(
        "--count", type=_positive_int, default=1, help="Tasks per rule"
    )
    generate.add_argument("--train-examples", type=_positive_int, default=3)
    generate.add_argument("--test-examples", type=_positive_int, default=1)
    generate.add_argument("--difficulty-lower", type=float, default=0.0)
    generate.add_argument("--difficulty-upper", type=float, default=1.0)
    generate.add_argument(
        "--timeout",
        type=_positive_seconds,
        default=60.0,
        help="Generation timeout in seconds",
    )
    visualize = commands.add_parser("visualize", help="Render tasks as standalone HTML")
    _add_dataset_args(visualize, positional=True)
    visualize.add_argument("--output", type=Path, required=True)
    visualize.add_argument("--title", default="ARC-AGI-1")
    experiment = commands.add_parser(
        "experiment", help="Run a file-based experiment matrix"
    )
    experiment.add_argument("config", type=Path)
    experiment.add_argument("--output", type=Path, required=True)
    experiment.add_argument("--task", action="append", dest="task_ids")
    experiment.add_argument("--tag", action="append", dest="tags")
    compare = commands.add_parser(
        "compare", help="Compare eval/experiment reports task by task"
    )
    compare.add_argument(
        "reports",
        nargs="+",
        metavar="[NAME=]REPORT",
        help="eval JSON or experiment results.json; the first is the baseline",
    )
    compare.add_argument(
        "--labels", type=Path, help="CSV/JSON mapping task_id to category"
    )
    compare.add_argument("--label-column", help="CSV category column name")
    compare.add_argument(
        "--label-sep", help="Split one CSV cell into several categories"
    )
    compare.add_argument("--output", type=Path, help="Write the full JSON comparison")
    compare.add_argument("--matrix-csv", type=Path, help="Write task x method CSV")
    compare.add_argument(
        "--format", choices=("json", "markdown"), default="json", help="Stdout format"
    )
    return parser
