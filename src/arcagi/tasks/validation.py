"""Strict ARC-AGI-1 schema validation without runtime dependencies."""

from collections.abc import Mapping

from .models import Example, Grid, Task


class TaskValidationError(ValueError):
    """Raised when a grid or task violates the ARC-AGI-1 data contract."""


def validate_grid(value: object, *, context: str = "grid") -> Grid:
    """Validate a rectangular 1–30 by 1–30 grid and freeze its cells."""
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 30:
        raise TaskValidationError(f"{context}: expected 1–30 rows")
    width: int | None = None
    rows = []
    for row_index, row in enumerate(value):
        if not isinstance(row, (list, tuple)) or not 1 <= len(row) <= 30:
            raise TaskValidationError(f"{context}[{row_index}]: expected 1–30 cells")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise TaskValidationError(f"{context}: grid must be rectangular")
        for column_index, cell in enumerate(row):
            if type(cell) is not int or not 0 <= cell <= 9:
                raise TaskValidationError(
                    f"{context}[{row_index}][{column_index}]: "
                    "expected an integer color 0–9 (not bool)"
                )
        rows.append(tuple(row))
    return tuple(rows)


def task_from_dict(
    value: object, *, task_id: str, require_test_outputs: bool = False
) -> Task:
    """Validate official task JSON, optionally requiring evaluation labels."""
    if (
        not isinstance(value, Mapping)
        or not {"train", "test"}.issubset(value)
        or set(value) - {"train", "test", "name"}
    ):
        raise TaskValidationError(
            f"{task_id}: expected train, test, and optional name keys"
        )
    if "name" in value and not isinstance(value["name"], str):
        raise TaskValidationError(f"{task_id}.name: expected a string")
    sections = {}
    for name in ("train", "test"):
        examples = value[name]
        if not isinstance(examples, list) or not examples:
            raise TaskValidationError(f"{task_id}.{name}: expected a nonempty list")
        parsed = []
        for index, example in enumerate(examples):
            context = f"{task_id}.{name}[{index}]"
            if not isinstance(example, Mapping):
                raise TaskValidationError(f"{context}: expected an input/output object")
            if "input" not in example or set(example) - {"input", "output"}:
                raise TaskValidationError(
                    f"{context}: expected input and optional output"
                )
            require_output = name == "train" or require_test_outputs
            if require_output and "output" not in example:
                raise TaskValidationError(f"{context}: missing output")
            parsed.append(
                Example(
                    validate_grid(example["input"], context=f"{context}.input"),
                    validate_grid(example["output"], context=f"{context}.output")
                    if "output" in example
                    else None,
                )
            )
        sections[name] = tuple(parsed)
    return Task(task_id, sections["train"], sections["test"])
