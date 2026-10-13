"""Group experiment runs and compute failure-inclusive accuracy and timing."""

from collections import defaultdict
from collections.abc import Iterable
from statistics import mean, median
from typing import Any


def _stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep failed and timed-out runs in every accuracy denominator."""
    count = len(runs)
    correct = sum(bool(run["correct"]) for run in runs)
    tests = sum(run["tests_total"] for run in runs)
    passed = sum(run["tests_correct"] for run in runs)
    elapsed = [float(run["elapsed_seconds"]) for run in runs]
    return {
        "runs_total": count,
        "runs_correct": correct,
        "run_accuracy": correct / count if count else 0.0,
        "tests_total": tests,
        "tests_correct": passed,
        "test_accuracy": passed / tests if tests else 0.0,
        "errors": sum(run.get("error") is not None for run in runs),
        "elapsed_mean_seconds": mean(elapsed) if elapsed else 0.0,
        "elapsed_median_seconds": median(elapsed) if elapsed else 0.0,
    }


def summarize_runs(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize each solver, task/solver, and overlapping tag/solver group."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        solver = run["solver"]
        groups[("solver", "all", solver)].append(run)
        groups[("task", run["task_id"], solver)].append(run)
        for tag in set(run.get("tags", [])):
            groups[("tag", tag, solver)].append(run)
    return [
        {"scope": scope, "group": group, "solver": solver, **_stats(members)}
        for (scope, group, solver), members in sorted(groups.items())
    ]
