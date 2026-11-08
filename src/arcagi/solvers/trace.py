"""Optional per-task attempt traces that solvers may return for later distillation.

A trace never affects scoring. Solvers that return plain prediction sequences keep
working; solvers that want to record what they tried return ``SolverResult``
(Python) or write ``trace.json`` (external file protocol). Invalid traces are
reported as ``trace_error`` while the predictions are still scored.
"""

import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from arcagi.tasks import Example, Grid

TRACE_SCHEMA = "arcagi-trace/1"
MAX_TRACE_BYTES = 10 * 1024 * 1024

_TOP_LEVEL = {
    "schema_version": str,
    "solver": str,
    "selected": (str, type(None)),
    "reasoning": str,
    "elapsed_seconds": (int, float),
    "metadata": dict,
}
_ATTEMPT = {
    "id": str,
    "kind": str,
    "description": str,
    "program": str,
    "train_results": list,
    "train_correct": int,
    "train_total": int,
    "selected": bool,
    "elapsed_seconds": (int, float),
    "reasoning": str,
    "error": (str, type(None)),
    "data": dict,
}


class TraceValidationError(ValueError):
    """A solver-supplied trace does not follow the ``arcagi-trace/1`` shape."""


@dataclass(frozen=True)
class SolverResult:
    """Predictions plus an optional trace; ``predict`` scores only predictions."""

    predictions: Sequence[object]
    trace: dict[str, Any] | None = None
    trace_error: str | None = None


def _check_fields(value: dict, spec: dict, context: str) -> None:
    for key, expected in spec.items():
        if key not in value:
            continue
        item = value[key]
        if isinstance(item, bool) and expected is not bool:
            raise TraceValidationError(f"{context}.{key}: booleans are not allowed")
        if not isinstance(item, expected):
            raise TraceValidationError(f"{context}.{key}: wrong type")
        if isinstance(item, float) and (not math.isfinite(item) or item < 0):
            raise TraceValidationError(f"{context}.{key}: must be finite and >= 0")
        if isinstance(item, int) and not isinstance(item, bool) and item < 0:
            raise TraceValidationError(f"{context}.{key}: must be >= 0")


def validate_trace(value: object) -> dict[str, Any]:
    """Check known fields' types and return a JSON round-tripped copy.

    Unknown keys are preserved so solvers can attach extra data, but known keys
    must have the documented types. ``schema_version`` defaults to the current one.
    """
    if not isinstance(value, dict):
        raise TraceValidationError("trace: expected a JSON object")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TraceValidationError(f"trace: not JSON serializable: {exc}") from exc
    if len(encoded.encode("utf-8")) > MAX_TRACE_BYTES:
        raise TraceValidationError(f"trace: larger than {MAX_TRACE_BYTES} bytes")
    trace = json.loads(encoded)
    trace.setdefault("schema_version", TRACE_SCHEMA)
    _check_fields(trace, _TOP_LEVEL, "trace")
    if trace["schema_version"] != TRACE_SCHEMA:
        raise TraceValidationError(
            f"trace.schema_version: expected {TRACE_SCHEMA!r}, "
            f"got {trace['schema_version']!r}"
        )
    attempts = trace.setdefault("attempts", [])
    if not isinstance(attempts, list):
        raise TraceValidationError("trace.attempts: expected a list")
    ids = []
    for index, attempt in enumerate(attempts):
        context = f"trace.attempts[{index}]"
        if not isinstance(attempt, dict):
            raise TraceValidationError(f"{context}: expected an object")
        _check_fields(attempt, _ATTEMPT, context)
        results = attempt.get("train_results", [])
        if any(not isinstance(item, bool) for item in results):
            raise TraceValidationError(f"{context}.train_results: expected booleans")
        if "id" in attempt:
            ids.append(attempt["id"])
    if len(ids) != len(set(ids)):
        raise TraceValidationError("trace.attempts: ids must be unique")
    selected = trace.get("selected")
    if selected is not None and selected not in ids:
        raise TraceValidationError("trace.selected: must name an attempt id")
    return trace


def split_solver_output(
    output: object,
) -> tuple[object, dict[str, Any] | None, str | None]:
    """Return ``(predictions, trace, trace_error)`` for any solver return value."""
    if not isinstance(output, SolverResult):
        return output, None, None
    if output.trace is None:
        return output.predictions, None, output.trace_error
    try:
        return output.predictions, validate_trace(output.trace), output.trace_error
    except TraceValidationError as exc:
        return output.predictions, None, str(exc)


def check_on_train(
    transform: Callable[[Grid], object], train: Sequence[Example]
) -> list[bool]:
    """Apply ``transform`` to each train input; True where it reproduces the output.

    Exceptions count as a failed example so hypothesis checks never abort a solve.
    """
    results = []
    for example in train:
        try:
            produced = transform(example.input)
            normalized = tuple(tuple(row) for row in produced)  # type: ignore[union-attr]
        except Exception:
            results.append(False)
            continue
        results.append(normalized == example.output)
    return results


class TraceRecorder:
    """Small helper for building an ``arcagi-trace/1`` dict inside a solver."""

    def __init__(self, solver: str | None = None) -> None:
        self._started = time.perf_counter()
        self.attempts: list[dict[str, Any]] = []
        self.selected: str | None = None
        self.reasoning = ""
        self.metadata: dict[str, Any] = {}
        self.solver = solver

    def attempt(
        self,
        description: str,
        *,
        kind: str = "hypothesis",
        program: str | None = None,
        train_results: Sequence[bool] | None = None,
        elapsed_seconds: float | None = None,
        reasoning: str | None = None,
        error: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Record one tried hypothesis/program and return its generated id."""
        attempt_id = f"a{len(self.attempts)}"
        record: dict[str, Any] = {
            "id": attempt_id,
            "kind": kind,
            "description": description,
        }
        if program is not None:
            record["program"] = program
        if train_results is not None:
            results = [bool(item) for item in train_results]
            record["train_results"] = results
            record["train_correct"] = sum(results)
            record["train_total"] = len(results)
        if elapsed_seconds is not None:
            record["elapsed_seconds"] = elapsed_seconds
        if reasoning:
            record["reasoning"] = reasoning
        if error is not None:
            record["error"] = error
        if data:
            record["data"] = data
        self.attempts.append(record)
        return attempt_id

    def select(self, attempt_id: str | None) -> None:
        """Mark the attempt whose output became the submitted prediction."""
        self.selected = attempt_id
        for record in self.attempts:
            record["selected"] = record["id"] == attempt_id

    def to_dict(self) -> dict[str, Any]:
        trace: dict[str, Any] = {
            "schema_version": TRACE_SCHEMA,
            "attempts": self.attempts,
            "selected": self.selected,
            "elapsed_seconds": time.perf_counter() - self._started,
        }
        if self.solver:
            trace["solver"] = self.solver
        if self.reasoning:
            trace["reasoning"] = self.reasoning
        if self.metadata:
            trace["metadata"] = self.metadata
        return validate_trace(trace)

    def result(self, predictions: Sequence[object]) -> SolverResult:
        """Bundle predictions with this trace for return from ``solve``."""
        return SolverResult(list(predictions), self.to_dict())


__all__ = [
    "MAX_TRACE_BYTES",
    "TRACE_SCHEMA",
    "SolverResult",
    "TraceRecorder",
    "TraceValidationError",
    "check_on_train",
    "split_solver_output",
    "validate_trace",
]
