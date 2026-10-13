"""Small command-line adapters around the public task and evaluation APIs."""

import argparse
import json
import math
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arcagi.solvers import Solver
    from arcagi.tasks import Task


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


def _solver(args: argparse.Namespace) -> "Solver":
    from arcagi.solvers import load_solver

    # Console entry points omit cwd, unlike python -m; local plugins need it.
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    if args.timeout is None:
        return load_solver(args.solver)
    from arcagi.solvers.runtime import load_timed_solver

    return load_timed_solver(args.solver, args.timeout)


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
    solve.add_argument(
        "--timeout", type=_positive_seconds, help="Per-task timeout in seconds"
    )
    solve.add_argument(
        "--solver", default="identity", help="identity or module:function"
    )
    solve.add_argument(
        "--output", type=Path, help="Write predictions JSON to this file"
    )
    evaluate = commands.add_parser("eval", help="Measure exact-match top-1 accuracy")
    _add_dataset_args(evaluate, positional=False)
    evaluate.add_argument(
        "--timeout", type=_positive_seconds, help="Per-task timeout in seconds"
    )
    evaluate.add_argument(
        "--solver", default="identity", help="identity or module:function"
    )
    evaluate.add_argument("--output", type=Path, help="Write the complete JSON report")
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
    return parser


def _dataset_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "path", None) or getattr(args, "tasks_dir", None)
    if explicit is not None:
        return explicit
    nested = args.data_root / "data" / args.split
    if nested.is_dir():
        return nested
    return args.data_root / args.split


def _load_selected(
    args: argparse.Namespace, *, require_outputs: bool = False
) -> list["Task"]:
    from arcagi.tasks import load_task, load_tasks

    path = _dataset_path(args)
    if path.is_file():
        tasks = [load_task(path, require_test_outputs=require_outputs)]
    else:
        tasks = load_tasks(path, require_test_outputs=require_outputs)
    if not tasks:
        raise ValueError(f"No task JSON files found in {path}")
    return tasks[: args.limit] if args.limit is not None else tasks


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _emit(payload: Any, output: Path | None = None) -> None:
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output is None:
        print(encoded, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")


def _protect_output(args: argparse.Namespace) -> None:
    output = getattr(args, "output", None)
    if output is None or args.command == "generate":
        return
    candidates = [getattr(args, "task", None), getattr(args, "predictions", None)]
    if args.command in ("eval", "score", "visualize"):
        selected = _dataset_path(args)
        if selected.is_dir():
            candidates.extend(selected.glob("*.json"))
        else:
            candidates.append(selected)
    if any(path and output.resolve() == path.resolve() for path in candidates):
        raise ValueError("Output must not overwrite an input task or predictions file")


def _run(args: argparse.Namespace) -> int:
    _protect_output(args)
    if args.command == "validate":
        tasks = _load_selected(args, require_outputs=args.require_test_outputs)
        _emit(
            {
                "valid": True,
                "tasks_total": len(tasks),
                "train_examples": sum(len(task.train) for task in tasks),
                "test_examples": sum(len(task.test) for task in tasks),
            }
        )
    elif args.command == "solve":
        from arcagi.solvers import predict
        from arcagi.tasks import load_task

        task = load_task(args.task)
        with redirect_stdout(sys.stderr):
            predictions = predict(_solver(args), task)
        result = {task.task_id: predictions}
        _emit(result, args.output)
        if args.output:
            _emit({"output": str(args.output), "task_id": task.task_id})
    elif args.command in ("eval", "score"):
        from arcagi.eval import evaluate_tasks, score_predictions

        tasks = _load_selected(args, require_outputs=True)
        if args.command == "score":
            predictions = json.loads(
                args.predictions.read_text(encoding="utf-8"),
                object_pairs_hook=_unique_object,
            )
            report = score_predictions(tasks, predictions)
        else:
            with redirect_stdout(sys.stderr):
                report = evaluate_tasks(tasks, _solver(args), solver_name=args.solver)
        _emit(report, args.output)
        if args.output:
            summary = {key: value for key, value in report.items() if key != "tasks"}
            summary["output"] = str(args.output)
            _emit(summary)
        return 1 if report["errors"] else 0
    elif args.command == "generate":
        from arcagi.generation import generate_dataset, list_generators

        if args.list:
            _emit(list_generators())
            return 0
        if args.output is None:
            raise ValueError("generate requires --output DIR (or use --list)")
        task_ids = None if args.all else (args.task_ids or ["007bbfb7"])
        result = generate_dataset(
            args.output,
            task_ids=task_ids,
            seed=args.seed,
            count=args.count,
            train_examples=args.train_examples,
            test_examples=args.test_examples,
            difficulty_lower=args.difficulty_lower,
            difficulty_upper=args.difficulty_upper,
            timeout=args.timeout,
        )
        _emit(result)
    elif args.command == "visualize":
        from arcagi.visualization import write_html

        tasks = _load_selected(args)
        output = write_html(tasks, args.output, title=args.title)
        _emit({"output": str(output), "tasks_total": len(tasks)})
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI: 0 success, 1 solver failures, 2 invalid input, 130 interrupted."""
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
