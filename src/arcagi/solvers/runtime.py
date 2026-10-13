"""Optional per-task subprocess deadlines for trusted local solver plugins.

This is process isolation for time limits, not a security sandbox. The deadline
covers plugin import and execution. Only the direct worker is terminated; plugins
must manage any additional processes they create themselves.
"""

import contextlib
import json
import math
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arcagi.solvers import Solver, load_solver
from arcagi.tasks import Example, SolverTask


class SolverTimeoutError(TimeoutError):
    """A solver worker exceeded its per-task deadline."""


class SolverExecutionError(RuntimeError):
    """A solver worker failed or returned an invalid response."""


def load_timed_solver(spec: str, timeout: float) -> Solver:
    """Return a solver that imports and runs ``spec`` in a fresh Python process.

    ``timeout`` must be finite and positive, in seconds. Each invocation gets the
    same budget, including interpreter startup and plugin import. Plugin state is
    not shared between tasks. Use ``load_solver`` for execution without a deadline.
    """
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Solver timeout must be a finite positive number of seconds")
    if spec != "identity":
        module, separator, function = spec.partition(":")
        if not separator or not module or not function or ":" in function:
            raise ValueError("Solver must be 'identity' or 'module:function'")

    def solve(task: SolverTask) -> Sequence[object]:
        if not isinstance(task, SolverTask):
            raise TypeError("Timed solvers accept only a label-free SolverTask")
        payload = {
            "solver": spec,
            "task": {
                "task_id": task.task_id,
                "train": [
                    {"input": example.input, "output": example.output}
                    for example in task.train
                ],
                "test": task.test,
            },
        }
        # Preserve the caller's import paths, including plugins beside a CLI call.
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            str(Path(entry or os.curdir).resolve()) for entry in sys.path
        )
        with tempfile.TemporaryDirectory(prefix="arcagi-solver-") as directory:
            result_path = Path(directory) / "result.json"
            with tempfile.TemporaryFile() as request, tempfile.TemporaryFile() as log:
                request.write(json.dumps(payload, allow_nan=False).encode("utf-8"))
                request.seek(0)
                try:
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "arcagi.solvers.runtime",
                            "--worker",
                            str(result_path),
                        ],
                        stdin=request,
                        stdout=log,
                        stderr=log,
                        env=environment,
                        timeout=timeout,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    # subprocess.run kills and waits for the worker before raising.
                    raise SolverTimeoutError(
                        f"Solver {spec!r} exceeded {timeout:g} seconds "
                        f"for task {task.task_id}"
                    ) from exc
                if completed.returncode:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(0, log.tell() - 4096))
                    detail = log.read().decode("utf-8", errors="replace").strip()
                    raise SolverExecutionError(
                        f"Solver worker exited with code {completed.returncode}"
                        + (f": {detail}" if detail else "")
                    )
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise SolverExecutionError(
                    "Solver worker did not return a valid JSON response"
                ) from exc
        if not isinstance(result, dict):
            raise SolverExecutionError("Solver worker returned an invalid response")
        if result.get("status") == "error":
            raise SolverExecutionError(str(result.get("error", "Unknown solver error")))
        predictions = result.get("predictions")
        if result.get("status") != "ok" or not isinstance(predictions, list):
            raise SolverExecutionError(
                "Solver must return a sequence of prediction grids"
            )
        return predictions

    return solve


def _worker(result_path: Path) -> None:
    """Read a label-free request and write one JSON response, separate from logs."""
    result: dict[str, Any]
    try:
        request = json.load(sys.stdin)
        raw = request["task"]
        task = SolverTask(
            raw["task_id"],
            tuple(
                Example(
                    tuple(tuple(row) for row in example["input"]),
                    tuple(tuple(row) for row in example["output"])
                    if example["output"] is not None
                    else None,
                )
                for example in raw["train"]
            ),
            tuple(tuple(tuple(row) for row in grid) for grid in raw["test"]),
        )
        with contextlib.redirect_stdout(sys.stderr):
            predictions = load_solver(request["solver"])(task)
        if not isinstance(predictions, Sequence) or isinstance(
            predictions, (str, bytes)
        ):
            raise ValueError("Solver must return a sequence of prediction grids")
        result = {"status": "ok", "predictions": list(predictions)}
        # Check serializability here so failures become ordinary per-task errors.
        encoded = json.dumps(result, allow_nan=False)
    except Exception as exc:
        encoded = json.dumps(
            {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        )
    result_path.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--worker":
        raise SystemExit("This module is an internal solver worker")
    _worker(Path(sys.argv[2]))
