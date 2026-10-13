"""Run a fixed task × method × seed × repeat matrix with preserved artifacts."""

import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from arcagi.eval import evaluate_tasks
from arcagi.solvers.external import make_external_solver

from .config import load_config, select_tasks


def run_experiment(
    config_path: str | Path,
    output_dir: str | Path,
    task_ids: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Run every selected job once; repeated runs never become answer attempts.

    Each method receives identical selected tasks, seeds, and repeat counts.
    Test labels stay in the parent evaluator. Every failure remains in the score
    denominator. Output directories must be new to preserve previous evidence.
    """
    config = load_config(config_path)
    tasks = select_tasks(config, task_ids, tags)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "config.json").write_text(
        json.dumps(config.source_config, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    runs = []
    for method in config.solvers:
        for seed in config.seeds:
            for repeat in range(config.repeats):
                for entry in tasks:
                    solver = make_external_solver(
                        method.command,
                        run_dir=output_dir / "artifacts" / method.name,
                        timeout=config.timeout_seconds,
                        seed=seed,
                        params=method.params,
                        cwd=method.cwd,
                    )
                    started = perf_counter()
                    result = evaluate_tasks(
                        [entry.task], solver, solver_name=method.name
                    )
                    duration = perf_counter() - started
                    record = solver.records[-1] if solver.records else {}
                    task_result = result["tasks"][0]
                    row = {
                        "solver": method.name,
                        "task_id": entry.task.task_id,
                        "tags": list(entry.tags),
                        "seed": seed,
                        "repeat": repeat,
                        "params": method.params,
                        "correct": task_result["correct"],
                        "tests_total": result["tests_total"],
                        "tests_correct": result["tests_correct"],
                        "elapsed_seconds": record.get("elapsed_seconds", duration),
                        "error": task_result["error"],
                        "artifact_dir": record.get("artifact_dir"),
                        "returncode": record.get("returncode"),
                        "predictions": [
                            test["prediction"] for test in task_result["tests"]
                        ],
                    }
                    runs.append(row)
                    with (output_dir / "runs.jsonl").open(
                        "a", encoding="utf-8"
                    ) as stream:
                        stream.write(
                            json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                        )
    aggregates = []
    for method in config.solvers:
        rows = [row for row in runs if row["solver"] == method.name]
        correct = sum(row["correct"] for row in rows)
        tests_total = sum(row["tests_total"] for row in rows)
        tests_correct = sum(row["tests_correct"] for row in rows)
        aggregates.append(
            {
                "solver": method.name,
                "runs_total": len(rows),
                "runs_correct": correct,
                "run_accuracy": correct / len(rows),
                "tests_total": tests_total,
                "tests_correct": tests_correct,
                "test_accuracy": tests_correct / tests_total,
                "errors": sum(row["error"] is not None for row in rows),
                "elapsed_seconds": sum(row["elapsed_seconds"] for row in rows),
            }
        )
    return {
        "schema": "arcagi-experiment/1",
        "scoring": "top1_exact_match_per_run",
        "attempts_per_test": 1,
        "config_path": str(config.path),
        "seeds": list(config.seeds),
        "repeats": config.repeats,
        "timeout_seconds": config.timeout_seconds,
        "source_config": config.source_config,
        "solvers": [
            {
                "name": solver.name,
                "command": list(solver.command),
                "params": solver.params,
                "cwd": str(solver.cwd),
            }
            for solver in config.solvers
        ],
        "tasks": [
            {
                "task_id": entry.task.task_id,
                "path": str(entry.path),
                "tags": list(entry.tags),
                "task_content_sha256": hashlib.sha256(
                    json.dumps(entry.task.to_dict(), sort_keys=True).encode("utf-8")
                ).hexdigest(),
            }
            for entry in tasks
        ],
        "runs": runs,
        "aggregates": aggregates,
        "errors": sum(row["error"] is not None for row in runs),
    }
