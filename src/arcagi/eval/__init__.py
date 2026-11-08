"""Exact-match top-1 evaluation with explicit failures and label validation."""

from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any

from arcagi.solvers import Solver, validate_predictions
from arcagi.solvers.trace import split_solver_output
from arcagi.tasks import SolverTask, Task, TaskValidationError


def evaluate_tasks(
    tasks: Iterable[Task],
    solver: Solver,
    *,
    solver_name: str = "identity",
    workers: int = 1,
) -> dict[str, Any]:
    """Evaluate every test; a task succeeds only when all its tests succeed.

    All labels are checked before calling the solver. Solver exceptions and invalid
    predictions mark the entire task incorrect and are retained in the report.
    This passes no test answers through the plugin interface; it is not a sandbox.
    Each task also records ``elapsed_seconds`` and an optional solver ``trace``
    (``arcagi-trace/1``) or ``trace_error``; traces never affect scoring.
    ``workers`` > 1 calls the solver from that many threads at once; use it only
    with solvers that do their work in subprocesses (timed or external solvers).
    The report is identical in order and content to a sequential run.
    """
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")
    tasks = list(tasks)
    if not tasks:
        raise TaskValidationError("Cannot evaluate an empty task collection")
    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise TaskValidationError("Evaluation task IDs must be unique")
    for task in tasks:
        if not task.test:
            raise TaskValidationError(f"{task.task_id}: no test examples")
        for index, example in enumerate(task.test):
            if example.output is None:
                raise TaskValidationError(
                    f"{task.task_id}.test[{index}]: missing output"
                )

    if workers == 1:
        results = [_evaluate_one(task, solver) for task in tasks]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # map keeps input order, so the report matches a sequential run.
            results = list(pool.map(lambda task: _evaluate_one(task, solver), tasks))
    tasks_correct = sum(result["correct"] for result in results)
    tests_total = sum(len(result["tests"]) for result in results)
    tests_correct = sum(
        test["correct"] for result in results for test in result["tests"]
    )
    return {
        "schema_version": "arcagi-evaluation/1",
        "solver": solver_name,
        "scoring": "top1_exact_match",
        "attempts_per_test": 1,
        "tasks_total": len(tasks),
        "tasks_correct": tasks_correct,
        "task_accuracy": tasks_correct / len(tasks),
        "tests_total": tests_total,
        "tests_correct": tests_correct,
        "test_accuracy": tests_correct / tests_total,
        "errors": sum(result["error"] is not None for result in results),
        "traces": sum(result["trace"] is not None for result in results),
        "tasks": results,
    }


def _evaluate_one(task: Task, solver: Solver) -> dict[str, Any]:
    """Run one task and build its report entry; failures become errors."""
    error = None
    predictions = ()
    trace = trace_error = None
    started = perf_counter()
    try:
        raw, trace, trace_error = split_solver_output(solver(task.to_solver_task()))
        predictions = validate_predictions(task, raw)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        trace = trace or getattr(exc, "arcagi_trace", None)
        trace_error = trace_error or getattr(exc, "arcagi_trace_error", None)
    elapsed = perf_counter() - started
    tests = []
    for index, example in enumerate(task.test):
        prediction = predictions[index] if error is None else None
        tests.append(
            {
                "index": index,
                "correct": prediction == example.output if error is None else False,
                "prediction": [list(row) for row in prediction]
                if prediction is not None
                else None,
                "expected": [list(row) for row in example.output],
            }
        )
    return {
        "task_id": task.task_id,
        "correct": all(test["correct"] for test in tests),
        "error": error,
        "elapsed_seconds": elapsed,
        "tests": tests,
        "trace": trace,
        "trace_error": trace_error,
    }


def score_predictions(
    tasks: Iterable[Task], predictions: Mapping[str, object]
) -> dict[str, Any]:
    """Score externally produced top-1 predictions keyed by task ID.

    Unknown task IDs are rejected to expose selection/filename mistakes. Missing
    entries and invalid predictions become per-task errors, retaining every task
    in the denominator. No solver code is imported or executed.
    """
    tasks = list(tasks)
    if not isinstance(predictions, Mapping):
        raise ValueError("Predictions must be an object mapping task IDs to grid lists")
    unknown = set(predictions) - {task.task_id for task in tasks}
    if unknown:
        raise ValueError(
            f"Predictions contain unknown task IDs: {sorted(unknown, key=str)}"
        )

    def supplied(task: SolverTask) -> Any:
        if task.task_id not in predictions:
            raise ValueError(f"Missing predictions for task {task.task_id}")
        return predictions[task.task_id]

    return evaluate_tasks(tasks, supplied, solver_name="provided-predictions")


__all__ = ["evaluate_tasks", "score_predictions"]
