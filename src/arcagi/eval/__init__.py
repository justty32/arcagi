"""Exact-match top-1 evaluation with explicit failures and label validation."""

from collections.abc import Iterable, Mapping
from typing import Any

from arcagi.solvers import Solver, predict
from arcagi.tasks import SolverTask, Task, TaskValidationError


def evaluate_tasks(
    tasks: Iterable[Task], solver: Solver, *, solver_name: str = "identity"
) -> dict[str, Any]:
    """Evaluate every test; a task succeeds only when all its tests succeed.

    All labels are checked before calling the solver. Solver exceptions and invalid
    predictions mark the entire task incorrect and are retained in the report.
    This passes no test answers through the plugin interface; it is not a sandbox.
    """
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

    results = []
    for task in tasks:
        error = None
        predictions = ()
        try:
            predictions = predict(solver, task)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
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
        results.append(
            {
                "task_id": task.task_id,
                "correct": all(test["correct"] for test in tests),
                "error": error,
                "tests": tests,
            }
        )
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
        "tasks": results,
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
