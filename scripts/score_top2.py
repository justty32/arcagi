"""Offline top-2 scoring of an ``arcagi eval`` report.

The solver stores its second candidate per test in ``trace.metadata.second`` (a
list with one grid or null per test). A task counts as correct under top-2 when
every test matches its expected grid with either the top-1 prediction or the
second candidate. Tasks without ``second`` score the same as top-1.

Usage: uv run python scripts/score_top2.py REPORT.json [--format json|markdown]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _second(task: dict[str, Any]) -> list[Any]:
    trace = task.get("trace") or {}
    metadata = trace.get("metadata") or {}
    second = metadata.get("second")
    return second if isinstance(second, list) else []


def _task_top2(task: dict[str, Any]) -> bool:
    if task.get("correct"):
        return True
    second = _second(task)
    tests = task.get("tests") or []
    if not tests:
        return False
    for test in tests:
        index = test.get("index", 0)
        alt = second[index] if index < len(second) else None
        hit = test.get("correct") or (alt is not None and alt == test.get("expected"))
        if not hit:
            return False
    return True


def score_top2(report: dict[str, Any]) -> dict[str, Any]:
    """Top-1 and top-2 task counts plus the task ids only top-2 solves."""
    tasks = report.get("tasks") or []
    top1 = [t["task_id"] for t in tasks if t.get("correct")]
    top2 = [t["task_id"] for t in tasks if _task_top2(t)]
    solved = set(top1)
    return {
        "tasks_total": len(tasks),
        "tasks_correct_top1": len(top1),
        "tasks_correct_top2": len(top2),
        "newly_correct": [task_id for task_id in top2 if task_id not in solved],
    }


def to_markdown(score: dict[str, Any]) -> str:
    newly = ", ".join(score["newly_correct"]) or "-"
    return "\n".join(
        [
            "| metric | value |",
            "|---|---|",
            f"| tasks | {score['tasks_total']} |",
            f"| top-1 correct | {score['tasks_correct_top1']} |",
            f"| top-2 correct | {score['tasks_correct_top2']} |",
            f"| newly correct | {newly} |",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    score = score_top2(json.loads(args.report.read_text(encoding="utf-8")))
    if args.format == "markdown":
        print(to_markdown(score))
    else:
        json.dump(score, sys.stdout, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
