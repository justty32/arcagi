"""Deterministic loading of official ARC task files."""

import json
from pathlib import Path

from .models import Task
from .validation import TaskValidationError, task_from_dict


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise TaskValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_task(path: str | Path, *, require_test_outputs: bool = False) -> Task:
    """Read one task; identify it by filename stem and include paths in errors."""
    path = Path(path)
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
        )
        return task_from_dict(
            data, task_id=path.stem, require_test_outputs=require_test_outputs
        )
    except (ValueError, UnicodeError) as exc:
        raise TaskValidationError(f"{path}: {exc}") from exc


def load_tasks(
    directory: str | Path, *, require_test_outputs: bool = False
) -> list[Task]:
    """Load immediate *.json files in filename order; reject empty datasets."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Task directory does not exist: {directory}")
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise TaskValidationError(f"No task JSON files found in {directory}")
    return [
        load_task(path, require_test_outputs=require_test_outputs) for path in paths
    ]
