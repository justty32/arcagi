"""Command dispatch, solver wiring, and exit status handling for the CLI."""

import argparse
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING

from arcagi.cli_args import build_parser as build_parser
from arcagi.cli_io import _emit, _load_selected, _protect_output, _unique_object

if TYPE_CHECKING:
    from arcagi.solvers import Solver


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


def _run(args: argparse.Namespace) -> int:
    _protect_output(args)
    if args.command == "experiment":
        from arcagi.cli_experiment import run_experiment_command

        return run_experiment_command(args)
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
