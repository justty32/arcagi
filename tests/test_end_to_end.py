"""Check real plugin processes and external prediction scoring as one pipeline."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arcagi", *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _task(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "train": [{"input": [[0]], "output": [[1]]}],
                "test": [
                    {"input": [[2]], "output": [[3]]},
                    {"input": [[4, 5]], "output": [[5, 6]]},
                ],
            }
        ),
        encoding="utf-8",
    )


def _plugin(path: Path) -> None:
    path.write_text(
        "from arcagi.tasks import SolverTask\n"
        "def solve(task):\n"
        "    assert isinstance(task, SolverTask)\n"
        "    assert not hasattr(task.test[0], 'output')\n"
        "    assert task.train[0].output == ((1,),)\n"
        "    if task.task_id == 'broken':\n"
        "        raise RuntimeError('intentional failure')\n"
        "    return [tuple(tuple(c + 1 for c in row) for row in grid)\n"
        "            for grid in task.test]\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("timeout_args", [(), ("--timeout", "5")])
def test_plugin_solve_then_external_score(
    tmp_path: Path, timeout_args: tuple[str, ...]
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _task(tasks / "sample.json")
    _plugin(tmp_path / "candidate.py")
    predictions = tmp_path / "predictions.json"
    solved = _run(
        tmp_path,
        "solve",
        str(tasks / "sample.json"),
        "--solver",
        "candidate:solve",
        "--output",
        str(predictions),
        *timeout_args,
    )
    assert solved.returncode == 0, solved.stderr
    assert json.loads(predictions.read_text()) == {"sample": [[[3]], [[5, 6]]]}
    scored = _run(
        tmp_path,
        "score",
        "--tasks-dir",
        str(tasks),
        "--predictions",
        str(predictions),
    )
    assert scored.returncode == 0, scored.stderr
    report = json.loads(scored.stdout)
    assert report["tasks_correct"] == report["tasks_total"] == 1
    assert report["tests_correct"] == report["tests_total"] == 2

    # Prove scoring can go red while valid partial predictions remain measurable.
    predictions.write_text(json.dumps({"sample": [[[3]], [[6, 5]]]}))
    scored = _run(
        tmp_path,
        "score",
        "--tasks-dir",
        str(tasks),
        "--predictions",
        str(predictions),
    )
    assert scored.returncode == 0, scored.stderr
    report = json.loads(scored.stdout)
    assert report["tasks_correct"] == 0
    assert report["tests_correct"] == 1
    assert report["tests_total"] == 2
    assert report["errors"] == 0


@pytest.mark.parametrize("timeout_args", [(), ("--timeout", "5")])
def test_plugin_failure_and_missing_predictions_keep_denominators(
    tmp_path: Path, timeout_args: tuple[str, ...]
) -> None:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for name in ("broken", "working"):
        _task(tasks / f"{name}.json")
    _plugin(tmp_path / "candidate.py")
    evaluated = _run(
        tmp_path,
        "eval",
        "--tasks-dir",
        str(tasks),
        "--solver",
        "candidate:solve",
        *timeout_args,
    )
    assert evaluated.returncode == 1, evaluated.stderr
    report = json.loads(evaluated.stdout)
    assert report["tasks_total"] == 2
    assert report["tests_total"] == 4
    assert report["tasks_correct"] == 1
    assert report["tests_correct"] == 2
    assert report["errors"] == 1

    predictions = tmp_path / "predictions.json"
    predictions.write_text(json.dumps({"working": [[[3]], [[5, 6]]]}))
    scored = _run(
        tmp_path,
        "score",
        "--tasks-dir",
        str(tasks),
        "--predictions",
        str(predictions),
    )
    assert scored.returncode == 1, scored.stderr
    scored_report = json.loads(scored.stdout)
    for field in (
        "tasks_total",
        "tests_total",
        "tasks_correct",
        "tests_correct",
        "errors",
    ):
        assert scored_report[field] == report[field]
