"""Validate experiment plans before starting any solver processes."""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arcagi.tasks import Task, load_task


@dataclass(frozen=True)
class TaskSpec:
    task: Task
    path: Path
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SolverSpec:
    name: str
    command: tuple[str, ...]
    params: dict[str, Any]
    cwd: Path


@dataclass(frozen=True)
class ExperimentConfig:
    path: Path
    tasks: tuple[TaskSpec, ...]
    solvers: tuple[SolverSpec, ...]
    seeds: tuple[int, ...]
    repeats: int
    timeout_seconds: float
    source_config: dict[str, Any]


def _object(
    value: object, required: set[str], optional: set[str], context: str
) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{context}: expected an object")
    if required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"{context}: missing required or unknown fields")
    return value


def _strings(value: object, context: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{context}: expected a {'nonempty ' if nonempty else ''}list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{context}: expected nonempty strings")
    return tuple(value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate experiment JSON key: {key}")
        result[key] = value
    return result


def load_config(path: str | Path) -> ExperimentConfig:
    """Resolve all task paths and solver working directories relative to the config."""
    path = Path(path).resolve()
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
    )
    _object(
        value,
        {"version", "tasks", "solvers"},
        {"seeds", "repeats", "timeout_seconds"},
        "experiment",
    )
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Experiment version must be 1")
    for key in ("tasks", "solvers"):
        if not isinstance(value[key], list) or not value[key]:
            raise ValueError(f"{key}: expected a nonempty list")
    tasks = []
    for entry in value["tasks"]:
        _object(entry, {"path"}, {"tags"}, "task")
        if not isinstance(entry["path"], str) or not entry["path"].strip():
            raise ValueError("Task path must be a nonempty string")
        task_path = (path.parent / entry["path"]).resolve()
        tasks.append(
            TaskSpec(
                load_task(task_path, require_test_outputs=True),
                task_path,
                _strings(entry.get("tags", []), "task.tags"),
            )
        )
    ids = [item.task.task_id for item in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Experiment task IDs (filename stems) must be unique")
    solvers = []
    for entry in value["solvers"]:
        _object(entry, {"name", "command"}, {"params", "cwd"}, "solver")
        name = entry["name"]
        if not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*", name
        ):
            raise ValueError(
                "Solver name must be a safe name starting with a letter/digit"
            )
        params = entry.get("params", {})
        if not isinstance(params, dict):
            raise ValueError(f"{name}.params must be an object")
        try:
            json.dumps(params, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{name}.params must contain finite JSON values") from exc
        cwd = entry.get("cwd", ".")
        if not isinstance(cwd, str) or not cwd:
            raise ValueError(f"{name}.cwd must be a nonempty string")
        cwd = (path.parent / cwd).resolve()
        if not cwd.is_dir():
            raise ValueError(f"Solver working directory does not exist: {cwd}")
        command = entry["command"]
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(arg, str) for arg in command)
            or not command[0]
        ):
            raise ValueError(f"{name}.command must be an argv list with an executable")
        solvers.append(SolverSpec(name, tuple(command), params, cwd))
    names = [solver.name for solver in solvers]
    if len(names) != len(set(names)):
        raise ValueError(
            "Solver names must be unique; name parameter variants separately"
        )
    seeds = value.get("seeds", [0])
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(type(seed) is not int for seed in seeds)
    ):
        raise ValueError("seeds must be a nonempty list of integers")
    if len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be unique; use repeats to repeat the same seed")
    repeats = value.get("repeats", 1)
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    timeout = value.get("timeout_seconds", 10)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be a positive finite number")
    return ExperimentConfig(
        path, tuple(tasks), tuple(solvers), tuple(seeds), repeats, float(timeout), value
    )


def select_tasks(
    config: ExperimentConfig,
    task_ids: list[str] | None = None,
    tags: list[str] | None = None,
) -> tuple[TaskSpec, ...]:
    """OR values within one filter, AND the task and tag filters together."""
    ids = set(task_ids or [])
    requested_tags = set(tags or [])
    unknown_ids = ids - {entry.task.task_id for entry in config.tasks}
    unknown_tags = requested_tags - {
        tag for entry in config.tasks for tag in entry.tags
    }
    if unknown_ids or unknown_tags:
        raise ValueError(
            f"Unknown task IDs: {sorted(unknown_ids)}; "
            f"unknown tags: {sorted(unknown_tags)}"
        )
    selected = tuple(
        entry
        for entry in config.tasks
        if (not ids or entry.task.task_id in ids)
        and (not requested_tags or requested_tags.intersection(entry.tags))
    )
    if not selected:
        raise ValueError("Task selection is empty")
    return selected
