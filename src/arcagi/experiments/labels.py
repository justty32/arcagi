"""Load arbitrary task_id -> category mappings from CSV or JSON files."""

import csv
import json
from pathlib import Path

UNLABELED = "(unlabeled)"


def _task_key(value: str) -> str:
    value = value.strip()
    return value[: -len(".json")] if value.endswith(".json") else value


def load_labels(
    path: str | Path,
    *,
    column: str | None = None,
    separator: str | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return task ID -> sorted categories; a task may have several categories.

    CSV files need a ``task_id`` column; the category column is ``column`` or the
    first other column. Repeated rows accumulate, and ``separator`` splits one
    cell into several categories. JSON files map task IDs to a string or a list of
    strings. A trailing ``.json`` on task IDs is ignored. Empty cells are skipped.
    """
    path = Path(path)
    labels: dict[str, set[str]] = {}

    def add(task_id: object, value: object) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"{path}: task IDs must be nonempty strings")
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str):
                raise ValueError(f"{path}: categories must be strings ({task_id})")
            parts = item.split(separator) if separator else [item]
            for part in parts:
                if part.strip():
                    labels.setdefault(_task_key(task_id), set()).add(part.strip())

    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected an object of task_id -> category")
        for task_id, category in value.items():
            add(task_id, category)
    else:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            if "task_id" not in fields:
                raise ValueError(f"{path}: CSV needs a 'task_id' column")
            if column is None:
                others = [field for field in fields if field != "task_id"]
                if not others:
                    raise ValueError(f"{path}: CSV needs a category column")
                column = others[0]
            elif column not in fields:
                raise ValueError(f"{path}: no column {column!r}; have {fields}")
            for row in reader:
                if (row["task_id"] or "").strip():
                    add(row["task_id"], row[column] or "")
    return {task_id: tuple(sorted(values)) for task_id, values in labels.items()}


__all__ = ["UNLABELED", "load_labels"]
