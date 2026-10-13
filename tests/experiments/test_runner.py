"""Experiment matrix consistency and strict configuration failure checks."""

import json
import sys
from pathlib import Path

import pytest

from arcagi.experiments import load_config, run_experiment, select_tasks


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    for name, expected in (("a", 1), ("b", 2)):
        (tmp_path / f"{name}.json").write_text(
            json.dumps(
                {
                    "train": [{"input": [[1]], "output": [[1]]}],
                    "test": [{"input": [[1]], "output": [[expected]]}],
                }
            )
        )
    (tmp_path / "solver.py").write_text(
        "import json, pathlib, sys\n"
        "req = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert all('output' not in pair for pair in req['task']['test'])\n"
        "result = [pair['input'] for pair in req['task']['test']]\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({req['task_id']: result}))\n"
    )
    path = tmp_path / "experiment.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [
                    {"path": "a.json", "tags": ["easy", "one"]},
                    {"path": "b.json", "tags": ["hard", "one"]},
                ],
                "solvers": [
                    {
                        "name": "identity",
                        "command": [sys.executable, "solver.py", "{input}", "{output}"],
                        "params": {"limit": 5},
                    }
                ],
                "seeds": [0, 42],
                "repeats": 2,
                "timeout_seconds": 2,
            }
        )
    )
    return path


def test_fixed_matrix_keeps_repeats_separate_and_artifacts(config_file: Path) -> None:
    output = config_file.parent / "results"
    report = run_experiment(config_file, output)
    assert report["errors"] == 0
    assert report["attempts_per_test"] == 1
    assert len(report["runs"]) == 8
    aggregate = report["aggregates"][0]
    assert aggregate["runs_total"] == 8
    assert aggregate["runs_correct"] == 4
    assert aggregate["run_accuracy"] == 0.5
    assert {row["seed"] for row in report["runs"]} == {0, 42}
    assert {row["repeat"] for row in report["runs"]} == {0, 1}
    assert len({row["artifact_dir"] for row in report["runs"]}) == 8
    for row in report["runs"]:
        request = json.loads((Path(row["artifact_dir"]) / "request.json").read_text())
        assert request["seed"] == row["seed"]
        assert request["params"] == {"limit": 5}
        assert row["elapsed_seconds"] >= 0
    assert len((output / "runs.jsonl").read_text().splitlines()) == 8
    assert json.loads((output / "config.json").read_text()) == report["source_config"]
    assert all(len(task["task_content_sha256"]) == 64 for task in report["tasks"])
    with pytest.raises(FileExistsError):
        run_experiment(config_file, output)


def test_relative_paths_and_filter_semantics(config_file: Path) -> None:
    config = load_config(config_file)
    assert config.tasks[0].path == config_file.parent / "a.json"
    assert config.solvers[0].cwd == config_file.parent
    assert len(select_tasks(config, tags=["easy", "hard"])) == 2
    assert [
        item.task.task_id for item in select_tasks(config, ["a", "b"], ["easy"])
    ] == ["a"]
    with pytest.raises(ValueError, match="empty"):
        select_tasks(config, ["a"], ["hard"])
    with pytest.raises(ValueError, match="Unknown"):
        select_tasks(config, ["typo"])
    with pytest.raises(ValueError, match="unknown tags"):
        select_tasks(config, tags=["typo"])


def test_failed_jobs_remain_in_matrix(config_file: Path) -> None:
    data = json.loads(config_file.read_text())
    data["solvers"].append({"name": "broken", "command": ["/missing/executable"]})
    config_file.write_text(json.dumps(data))
    report = run_experiment(config_file, config_file.parent / "failed-results")
    assert len(report["runs"]) == 16
    assert report["errors"] == 8
    broken = report["aggregates"][1]
    assert broken["runs_total"] == broken["tests_total"] == broken["errors"] == 8
    assert broken["runs_correct"] == 0
    assert all(row["artifact_dir"] for row in report["runs"])
    matrices = {
        method: {
            (row["task_id"], row["seed"], row["repeat"])
            for row in report["runs"]
            if row["solver"] == method
        }
        for method in ("identity", "broken")
    }
    assert matrices["identity"] == matrices["broken"]


def test_empty_argument_is_preserved_as_literal_argv(config_file: Path) -> None:
    data = json.loads(config_file.read_text())
    data["solvers"][0]["command"].append("")
    config_file.write_text(json.dumps(data))
    assert load_config(config_file).solvers[0].command[-1] == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("version", 2),
        ("repeats", 0),
        ("repeats", True),
        ("seeds", []),
        ("seeds", [0, 0]),
        ("seeds", [False]),
        ("timeout_seconds", 0),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", True),
        ("tasks", []),
        ("solvers", []),
        ("unknown", 1),
    ],
)
def test_invalid_top_level_rejected_before_output(
    config_file: Path, field: str, value: object
) -> None:
    data = json.loads(config_file.read_text())
    data[field] = value
    config_file.write_text(json.dumps(data))
    output = config_file.parent / "not-created"
    with pytest.raises(ValueError):
        run_experiment(config_file, output)
    assert not output.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "../escape"),
        ("command", "echo hello"),
        ("command", []),
        ("params", []),
        ("params", {"bad": float("nan")}),
        ("cwd", "absent"),
    ],
)
def test_invalid_solver_config(config_file: Path, field: str, value: object) -> None:
    data = json.loads(config_file.read_text())
    data["solvers"][0][field] = value
    config_file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_config(config_file)


def test_duplicate_task_and_solver_identity_rejected(config_file: Path) -> None:
    data = json.loads(config_file.read_text())
    data["tasks"].append(data["tasks"][0])
    config_file.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="task IDs"):
        load_config(config_file)
    data["tasks"].pop()
    data["solvers"].append(data["solvers"][0])
    config_file.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Solver names"):
        load_config(config_file)


def test_unlabelled_task_is_rejected_before_any_execution(config_file: Path) -> None:
    task_path = config_file.parent / "b.json"
    task = json.loads(task_path.read_text())
    del task["test"][0]["output"]
    task_path.write_text(json.dumps(task))
    with pytest.raises(ValueError, match="missing output"):
        run_experiment(config_file, config_file.parent / "never-created")
    assert not (config_file.parent / "never-created").exists()
