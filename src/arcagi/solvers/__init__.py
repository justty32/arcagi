"""A small plugin contract independent of any learning framework."""

from collections.abc import Sequence
from importlib import import_module
from typing import Protocol

from arcagi.tasks import Grid, SolverTask, Task, validate_grid

from .trace import SolverResult, split_solver_output


class Solver(Protocol):
    """Return exactly one predicted grid per test input in its original order.

    A solver may instead return ``SolverResult(predictions, trace)`` to attach an
    optional ``arcagi-trace/1`` attempt trace; scoring ignores the trace.
    """

    def __call__(self, task: SolverTask) -> Sequence[object] | SolverResult: ...


def load_solver(spec: str = "identity") -> Solver:
    """Load a trusted local Python callable from module:function."""
    if spec == "identity":
        from .identity import solve

        return solve
    module_name, separator, function_name = spec.partition(":")
    if not separator or not module_name or not function_name or ":" in function_name:
        raise ValueError("Solver must be 'identity' or 'module:function'")
    solver = getattr(import_module(module_name), function_name)
    if not callable(solver):
        raise TypeError(f"Solver {spec!r} is not callable")
    return solver


def predict(solver: Solver, task: Task) -> tuple[Grid, ...]:
    """Hide test labels and validate the solver's complete top-1 prediction."""
    return predict_with_trace(solver, task)[0]


def predict_with_trace(
    solver: Solver, task: Task
) -> tuple[tuple[Grid, ...], dict | None, str | None]:
    """Like ``predict`` but also return ``(trace, trace_error)`` when supplied."""
    predictions, trace, trace_error = split_solver_output(solver(task.to_solver_task()))
    return validate_predictions(task, predictions), trace, trace_error


def validate_predictions(task: Task, predictions: object) -> tuple[Grid, ...]:
    """Require exactly one valid grid per test input, in order."""
    if not isinstance(predictions, Sequence) or isinstance(predictions, (str, bytes)):
        raise ValueError("Solver must return a sequence with one grid per test input")
    if len(predictions) != len(task.test):
        raise ValueError(
            f"Solver returned {len(predictions)} predictions for {len(task.test)} tests"
        )
    return tuple(
        validate_grid(grid, context=f"{task.task_id}.prediction[{index}]")
        for index, grid in enumerate(predictions)
    )


__all__ = [
    "Solver",
    "SolverResult",
    "load_solver",
    "predict",
    "predict_with_trace",
    "validate_predictions",
]
