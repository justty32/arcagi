"""Run any language's solver using a small, answer-free JSON file protocol."""

import json
import math
import re
import subprocess
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arcagi.tasks import Grid, SolverTask, validate_grid


class ExternalSolverError(RuntimeError):
    """An external command failed or produced an invalid prediction file."""


class ExternalSolverTimeoutError(TimeoutError):
    """The direct external solver process exceeded its deadline."""


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON number: {value}")


class ExternalSolver:
    """A callable adapter retaining each run's files and timing records.

    Commands are argv arrays and are never interpreted by a shell. This is not a
    sandbox. Timeouts kill and reap the direct process; commands are responsible
    for any descendant processes they create.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        run_dir: Path,
        timeout: float,
        seed: int = 0,
        params: dict[str, Any] | None = None,
        cwd: Path | None = None,
    ) -> None:
        if (
            isinstance(command, (str, bytes))
            or not command
            or not all(isinstance(arg, str) for arg in command)
            or not command[0]
        ):
            raise ValueError("External solver command must be a nonempty argv array")
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("External solver timeout must be finite and positive")
        if type(seed) is not int:
            raise ValueError("External solver seed must be an integer")
        if params is not None and not isinstance(params, dict):
            raise ValueError("External solver params must be a JSON object")
        self.command = tuple(command)
        self.run_dir = Path(run_dir).resolve()
        self.timeout = timeout
        self.seed = seed
        self.params = json.loads(json.dumps(params or {}, allow_nan=False))
        self.cwd = Path(cwd).resolve() if cwd is not None else None
        self.records: list[dict[str, Any]] = []

    @property
    def last_run(self) -> dict[str, Any] | None:
        """Return the most recent execution record, or None before the first call."""
        return self.records[-1] if self.records else None

    def __call__(self, task: SolverTask) -> tuple[Grid, ...]:
        if not isinstance(task, SolverTask):
            raise TypeError("External solvers accept only a label-free SolverTask")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", task.task_id)[:80] or "task"
        directory = Path(tempfile.mkdtemp(prefix=f"{safe_id}-", dir=self.run_dir))
        input_path = directory / "request.json"
        output_path = directory / "response.json"
        stdout_path = directory / "stdout.log"
        stderr_path = directory / "stderr.log"
        replacements = {
            "{input}": str(input_path),
            "{output}": str(output_path),
            "{task_id}": task.task_id,
            "{seed}": str(self.seed),
        }
        command = [
            re.sub(
                r"\{(?:input|output|task_id|seed)\}",
                lambda match: replacements[match.group()],
                argument,
            )
            for argument in self.command
        ]
        record: dict[str, Any] = {
            "task_id": task.task_id,
            "seed": self.seed,
            "artifact_dir": str(directory),
            "input_path": str(input_path),
            "output_path": str(output_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "command": command,
            "elapsed_seconds": 0.0,
            "returncode": None,
            "error": None,
            "status": "running",
        }
        self.records.append(record)
        started = time.perf_counter()
        try:
            request = {
                "schema_version": "arcagi-solver-input/1",
                "task_id": task.task_id,
                "task": {
                    "train": [
                        {"input": example.input, "output": example.output}
                        for example in task.train
                    ],
                    "test": [{"input": grid} for grid in task.test],
                },
                "seed": self.seed,
                "params": self.params,
            }
            input_path.write_text(
                json.dumps(request, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                try:
                    completed = subprocess.run(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        timeout=self.timeout,
                        cwd=self.cwd,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise ExternalSolverTimeoutError(
                        f"External solver exceeded {self.timeout:g} seconds "
                        f"for task {task.task_id}"
                    ) from exc
            record["returncode"] = completed.returncode
            if completed.returncode:
                raise ExternalSolverError(
                    f"External solver exited with code {completed.returncode}; "
                    f"see {stderr_path}"
                )
            try:
                response = json.loads(
                    output_path.read_text(encoding="utf-8"),
                    object_pairs_hook=_unique_keys,
                    parse_constant=_reject_constant,
                )
            except (OSError, ValueError) as exc:
                raise ExternalSolverError(f"Invalid response JSON: {exc}") from exc
            if not isinstance(response, dict) or set(response) != {task.task_id}:
                raise ExternalSolverError(
                    f"Response must contain exactly task ID {task.task_id!r}; "
                    "missing or unknown task IDs are not accepted"
                )
            predictions = response[task.task_id]
            if not isinstance(predictions, list) or len(predictions) != len(task.test):
                raise ExternalSolverError(
                    "Response must contain exactly one prediction per test input"
                )
            result = tuple(
                validate_grid(grid, context=f"{task.task_id}.prediction[{index}]")
                for index, grid in enumerate(predictions)
            )
            record["status"] = "ok"
            return result
        except Exception as exc:
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            record["elapsed_seconds"] = time.perf_counter() - started
            (directory / "run.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


def make_external_solver(
    command: Sequence[str],
    *,
    run_dir: Path,
    timeout: float,
    seed: int = 0,
    params: dict[str, Any] | None = None,
    cwd: Path | None = None,
) -> ExternalSolver:
    """Create a file-protocol solver with retained per-call execution artifacts."""
    return ExternalSolver(
        command, run_dir=run_dir, timeout=timeout, seed=seed, params=params, cwd=cwd
    )
