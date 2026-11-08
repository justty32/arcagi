"""Copyable solver skeleton showing the plugin contract and attempt tracing.

Run: uv run arcagi eval --split training --solver arcagi.solvers.template:solve \\
         --output artifacts/template.json --traces artifacts/template-traces.jsonl

It is not a real solver. It only tries a few whole-grid symmetries, checks each
on the training pairs, submits the first that reproduces every pair (else the
test inputs unchanged), and records every attempt in an ``arcagi-trace/1`` trace.
Replace ``CANDIDATES`` / ``solve`` with your own hypothesis search.
"""

import time
from collections.abc import Callable

from arcagi.tasks import Grid, SolverTask

from .trace import SolverResult, TraceRecorder, check_on_train

type Transform = Callable[[Grid], Grid]

CANDIDATES: dict[str, Transform] = {
    "identity": lambda grid: grid,
    "flip_horizontal": lambda grid: tuple(tuple(reversed(row)) for row in grid),
    "flip_vertical": lambda grid: tuple(reversed(grid)),
    "transpose": lambda grid: tuple(zip(*grid, strict=True)),
    "rotate_180": lambda grid: tuple(tuple(reversed(row)) for row in reversed(grid)),
}


def solve(task: SolverTask) -> SolverResult:
    """Return one prediction per test input plus the trace of what was tried."""
    recorder = TraceRecorder(solver="template")
    chosen: tuple[str, str] | None = None
    for name, transform in CANDIDATES.items():
        started = time.perf_counter()
        results = check_on_train(transform, task.train)
        attempt_id = recorder.attempt(
            f"apply {name} to the whole grid",
            kind="program",
            program=name,
            train_results=results,
            elapsed_seconds=time.perf_counter() - started,
        )
        if chosen is None and results and all(results):
            chosen = (attempt_id, name)
    if chosen is None:
        recorder.reasoning = "No candidate fits every training pair; echo inputs."
        recorder.select(None)
        return recorder.result(list(task.test))
    attempt_id, name = chosen
    recorder.reasoning = f"{name} reproduces every training pair."
    recorder.select(attempt_id)
    return recorder.result([CANDIDATES[name](grid) for grid in task.test])
