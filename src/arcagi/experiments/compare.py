"""Compare solver reports task by task, pairwise, and by task category."""

import csv
import json
from itertools import combinations
from pathlib import Path
from typing import Any

from .labels import UNLABELED

COMPARISON_SCHEMA = "arcagi-comparison/1"

type Outcomes = dict[str, dict[str, int]]


def _parse_spec(spec: str) -> tuple[str | None, Path]:
    name, separator, path = spec.partition("=")
    if separator and name and path and not Path(spec).exists():
        return name, Path(path)
    return None, Path(spec)


def load_report_outcomes(spec: str) -> list[tuple[str, str, Outcomes]]:
    """Load ``[NAME=]PATH`` into ``(method, source, {task_id: {runs, correct}})``.

    Accepts an ``arcagi eval`` report, an experiment ``results.json``, or an
    experiment output directory. Experiment reports yield one method per solver;
    with NAME and several solvers, methods are named ``NAME/solver``.
    """
    label, path = _parse_spec(spec)
    if path.is_dir():
        path = path / "results.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError(f"{path}: not a report object")
    if report.get("schema_version") == "arcagi-evaluation/1":
        outcomes = {
            task["task_id"]: {"runs": 1, "correct": int(bool(task["correct"]))}
            for task in report["tasks"]
        }
        return [(label or str(report["solver"]), str(path), outcomes)]
    if report.get("schema") == "arcagi-experiment/1":
        by_solver: dict[str, Outcomes] = {}
        for run in report["runs"]:
            entry = by_solver.setdefault(run["solver"], {}).setdefault(
                run["task_id"], {"runs": 0, "correct": 0}
            )
            entry["runs"] += 1
            entry["correct"] += int(bool(run["correct"]))
        methods = []
        for solver, outcomes in by_solver.items():
            if label is None:
                name = solver
            else:
                name = label if len(by_solver) == 1 else f"{label}/{solver}"
            methods.append((name, str(path), outcomes))
        return methods
    raise ValueError(f"{path}: not an arcagi eval or experiment report")


def _solved(outcome: dict[str, int] | None) -> bool | None:
    """A task counts as solved only when every run of it was correct."""
    if outcome is None:
        return None
    return outcome["runs"] > 0 and outcome["correct"] == outcome["runs"]


def _summary(names: list[str], methods: dict[str, Outcomes], ids: list[str]) -> dict:
    result = {}
    for name in names:
        present = [task_id for task_id in ids if task_id in methods[name]]
        solved = sum(bool(_solved(methods[name][task_id])) for task_id in present)
        result[name] = {
            "tasks_total": len(present),
            "tasks_solved": solved,
            "accuracy": solved / len(present) if present else 0.0,
        }
    return result


def compare_reports(
    specs: list[str], labels: dict[str, tuple[str, ...]] | None = None
) -> dict[str, Any]:
    """Build a comparison; the first method is the baseline for changes.

    Pairwise counts use only tasks present in both methods. Category accuracy
    uses each method's own tasks; a task may belong to several categories, so
    category totals overlap. Tasks absent from ``labels`` are ``(unlabeled)``.
    """
    names: list[str] = []
    sources: dict[str, str] = {}
    methods: dict[str, Outcomes] = {}
    for spec in specs:
        for name, source, outcomes in load_report_outcomes(spec):
            if name in methods:
                raise ValueError(
                    f"Duplicate method name {name!r}; prefix reports as NAME=PATH"
                )
            names.append(name)
            sources[name] = source
            methods[name] = outcomes
    if not names:
        raise ValueError("No methods to compare")
    task_ids = sorted(
        {task_id for outcomes in methods.values() for task_id in outcomes}
    )

    def categories(task_id: str) -> list[str]:
        if labels is None:
            return []
        return list(labels.get(task_id, (UNLABELED,)))

    tasks = []
    for task_id in task_ids:
        results = {}
        for name in names:
            outcome = methods[name].get(task_id)
            results[name] = (
                None if outcome is None else {**outcome, "solved": _solved(outcome)}
            )
        tasks.append(
            {"task_id": task_id, "categories": categories(task_id), "results": results}
        )

    pairs = []
    for first, second in combinations(names, 2):
        common = [i for i in task_ids if i in methods[first] and i in methods[second]]
        a = {i for i in common if _solved(methods[first][i])}
        b = {i for i in common if _solved(methods[second][i])}
        pairs.append(
            {
                "a": first,
                "b": second,
                "common_tasks": len(common),
                "both_solved": len(a & b),
                "neither_solved": len(common) - len(a | b),
                "only_a_solved": sorted(a - b),
                "only_b_solved": sorted(b - a),
            }
        )
    baseline = names[0]
    changes = [
        {
            "method": pair["b"],
            "baseline": baseline,
            "newly_solved": pair["only_b_solved"],
            "regressed": pair["only_a_solved"],
        }
        for pair in pairs
        if pair["a"] == baseline
    ]
    summary = _summary(names, methods, task_ids)
    by_category = []
    if labels is not None:
        groups: dict[str, list[str]] = {}
        for task in tasks:
            for category in task["categories"]:
                groups.setdefault(category, []).append(task["task_id"])
        for category in sorted(groups):
            by_category.append(
                {
                    "category": category,
                    "tasks_total": len(groups[category]),
                    "methods": _summary(names, methods, groups[category]),
                }
            )
    return {
        "schema": COMPARISON_SCHEMA,
        "solved_rule": "all_runs_correct",
        "baseline": baseline,
        "methods": [
            {"name": name, "source": sources[name], **summary[name]} for name in names
        ],
        "tasks": tasks,
        "pairs": pairs,
        "changes": changes,
        "categories": by_category,
    }


def _cell(result: dict | None) -> str:
    if result is None:
        return ""
    if result["runs"] == 1:
        return "1" if result["solved"] else "0"
    return f"{result['correct']}/{result['runs']}"


def write_matrix_csv(comparison: dict[str, Any], path: str | Path) -> None:
    """Write task x method cells: 1/0 for single runs, k/n for repeated runs."""
    names = [method["name"] for method in comparison["methods"]]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["task_id", "categories", *names])
        for task in comparison["tasks"]:
            writer.writerow(
                [
                    task["task_id"],
                    ";".join(task["categories"]),
                    *(_cell(task["results"][name]) for name in names),
                ]
            )


def render_markdown(comparison: dict[str, Any]) -> str:
    """Render a human-readable summary of the comparison."""
    names = [method["name"] for method in comparison["methods"]]
    lines = ["| method | solved | total | accuracy |", "|---|---|---|---|"]
    for method in comparison["methods"]:
        lines.append(
            f"| {method['name']} | {method['tasks_solved']} | "
            f"{method['tasks_total']} | {method['accuracy']:.1%} |"
        )
    for change in comparison["changes"]:
        lines += [
            "",
            f"## {change['method']} vs {change['baseline']}",
            f"- newly solved ({len(change['newly_solved'])}): "
            + (", ".join(change["newly_solved"]) or "-"),
            f"- regressed ({len(change['regressed'])}): "
            + (", ".join(change["regressed"]) or "-"),
        ]
    if comparison["categories"]:
        lines += ["", "## by category", ""]
        lines.append("| category | tasks | " + " | ".join(names) + " |")
        lines.append("|---|---|" + "---|" * len(names))
        for group in comparison["categories"]:
            cells = []
            for name in names:
                stats = group["methods"][name]
                cells.append(f"{stats['tasks_solved']}/{stats['tasks_total']}")
            lines.append(
                f"| {group['category']} | {group['tasks_total']} | "
                + " | ".join(cells)
                + " |"
            )
    disagreements = [
        task
        for task in comparison["tasks"]
        if len({_cell(task["results"][name]) for name in names}) > 1
    ]
    if len(names) > 1:
        lines += ["", f"## tasks where methods differ ({len(disagreements)})", ""]
        lines.append("| task | " + " | ".join(names) + " |")
        lines.append("|---|" + "---|" * len(names))
        for task in disagreements:
            lines.append(
                f"| {task['task_id']} | "
                + " | ".join(_cell(task["results"][name]) or "-" for name in names)
                + " |"
            )
    return "\n".join(lines) + "\n"


__all__ = [
    "COMPARISON_SCHEMA",
    "compare_reports",
    "load_report_outcomes",
    "render_markdown",
    "write_matrix_csv",
]
