"""Dataset selection, JSON output, and input-file protection for the CLI."""

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from arcagi.tasks import Task


def _dataset_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "path", None) or getattr(args, "tasks_dir", None)
    if explicit is not None:
        return explicit
    nested = args.data_root / "data" / args.split
    if nested.is_dir():
        return nested
    return args.data_root / args.split


def _load_selected(
    args: argparse.Namespace, *, require_outputs: bool = False
) -> list["Task"]:
    from arcagi.tasks import load_task, load_tasks

    path = _dataset_path(args)
    if path.is_file():
        tasks = [load_task(path, require_test_outputs=require_outputs)]
    else:
        tasks = load_tasks(path, require_test_outputs=require_outputs)
    if not tasks:
        raise ValueError(f"No task JSON files found in {path}")
    return tasks[: args.limit] if args.limit is not None else tasks


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _emit(payload: Any, output: Path | None = None) -> None:
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if output is None:
        print(encoded, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")


def _protect_output(args: argparse.Namespace) -> None:
    output = getattr(args, "output", None)
    if output is None or args.command == "generate":
        return
    candidates = [getattr(args, "task", None), getattr(args, "predictions", None)]
    if args.command in ("eval", "score", "visualize"):
        selected = _dataset_path(args)
        if selected.is_dir():
            candidates.extend(selected.glob("*.json"))
        else:
            candidates.append(selected)
    if any(path and output.resolve() == path.resolve() for path in candidates):
        raise ValueError("Output must not overwrite an input task or predictions file")
