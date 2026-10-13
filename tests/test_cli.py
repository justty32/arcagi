"""Exercise CLI success and failure behavior through its public entry point."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from arcagi.cli import main


@pytest.fixture
def task_path(tmp_path: Path) -> Path:
    path = tmp_path / "sample.json"
    path.write_text(
        json.dumps(
            {
                "train": [{"input": [[1, 2]], "output": [[1, 2]]}],
                "test": [
                    {"input": [[3]], "output": [[3]]},
                    {"input": [[4, 5]], "output": [[4, 5]]},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arcagi", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "generate" in result.stdout
    assert "score" in result.stdout


def test_validate_and_reject_bad_grid(task_path: Path, capsys) -> None:
    assert main(["validate", str(task_path)]) == 0
    assert json.loads(capsys.readouterr().out)["test_examples"] == 2
    payload = json.loads(task_path.read_text())
    payload["train"][0]["input"] = [[1], [2, 3]]
    task_path.write_text(json.dumps(payload))
    assert main(["validate", str(task_path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_empty_directory_is_error(tmp_path: Path, capsys) -> None:
    assert main(["validate", str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_solve_writes_scoreable_predictions(
    task_path: Path, tmp_path: Path, capsys
) -> None:
    output = tmp_path / "results" / "predictions.json"
    assert main(["solve", str(task_path), "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == {"sample": [[[3]], [[4, 5]]]}
    assert json.loads(capsys.readouterr().out)["output"] == str(output)


def test_eval_custom_directory_and_report(
    task_path: Path, tmp_path: Path, capsys
) -> None:
    output = tmp_path / "reports" / "evaluation.json"
    assert (
        main(["eval", "--tasks-dir", str(task_path.parent), "--output", str(output)])
        == 0
    )
    report = json.loads(output.read_text())
    assert report["tasks_correct"] == 1
    assert report["tests_correct"] == 2
    assert report["attempts_per_test"] == 1
    assert "tasks" not in json.loads(capsys.readouterr().out)


def test_incorrect_prediction_is_normal_score(task_path: Path, capsys) -> None:
    payload = json.loads(task_path.read_text())
    payload["test"][0]["output"] = [[0]]
    task_path.write_text(json.dumps(payload))
    assert main(["eval", "--tasks-dir", str(task_path.parent)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["tasks_correct"] == 0
    assert report["tests_correct"] == 1


def test_invalid_solver_is_configuration_error(task_path: Path, capsys) -> None:
    assert (
        main(["solve", str(task_path), "--solver", "nonexistent_arcagi_plugin:solve"])
        == 2
    )
    assert "error:" in capsys.readouterr().err


def test_solver_exception_writes_report_and_exits_one(
    task_path: Path, capsys, monkeypatch
) -> None:
    import arcagi.solvers

    def failing_solver(task):
        raise RuntimeError("deliberate solver failure")

    monkeypatch.setattr(arcagi.solvers, "load_solver", lambda spec: failing_solver)
    assert main(["eval", "--tasks-dir", str(task_path.parent)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["errors"] == 1
    assert "deliberate solver failure" in report["tasks"][0]["error"]


def test_score_external_predictions(task_path: Path, tmp_path: Path, capsys) -> None:
    predictions = tmp_path / "predictions.data"
    predictions.write_text(json.dumps({"sample": [[[3]], [[4, 5]]]}))
    assert (
        main(
            [
                "score",
                "--tasks-dir",
                str(task_path.parent),
                "--predictions",
                str(predictions),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["tasks_correct"] == 1


def test_missing_labels_fail_eval_but_allow_solve(task_path: Path, capsys) -> None:
    payload = json.loads(task_path.read_text())
    del payload["test"][0]["output"]
    task_path.write_text(json.dumps(payload))
    assert main(["solve", str(task_path)]) == 0
    capsys.readouterr()
    assert main(["eval", "--tasks-dir", str(task_path.parent)]) == 2
    assert "error:" in capsys.readouterr().err


def test_generate_requires_destination(capsys) -> None:
    assert main(["generate"]) == 2
    assert "--output" in capsys.readouterr().err


def test_score_rejects_duplicate_task_keys(
    task_path: Path, tmp_path: Path, capsys
) -> None:
    predictions = tmp_path / "predictions.data"
    predictions.write_text('{"sample": [[[3]], [[4, 5]]], "sample": []}')
    assert (
        main(
            [
                "score",
                "--tasks-dir",
                str(task_path.parent),
                "--predictions",
                str(predictions),
            ]
        )
        == 2
    )
    assert "Duplicate JSON key" in capsys.readouterr().err


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_timeout_rejects_invalid_numbers(task_path: Path, timeout: str) -> None:
    with pytest.raises(SystemExit) as error:
        main(["solve", str(task_path), "--timeout", timeout])
    assert error.value.code == 2


def test_solver_logs_go_to_stderr(task_path: Path, capsys, monkeypatch) -> None:
    import arcagi.solvers

    def noisy_solver(task):
        print("solver debug log")
        return task.test

    monkeypatch.setattr(arcagi.solvers, "load_solver", lambda spec: noisy_solver)
    assert main(["solve", str(task_path)]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == {"sample": [[[3]], [[4, 5]]]}
    assert "solver debug log" in output.err
    assert main(["eval", "--tasks-dir", str(task_path.parent)]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["tasks_correct"] == 1
    assert "solver debug log" in output.err


def test_output_cannot_overwrite_input_task(task_path: Path, capsys) -> None:
    original = task_path.read_text()
    assert main(["solve", str(task_path), "--output", str(task_path)]) == 2
    assert task_path.read_text() == original
    assert "must not overwrite" in capsys.readouterr().err
    assert (
        main(
            [
                "eval",
                "--tasks-dir",
                str(task_path.parent),
                "--output",
                str(task_path),
            ]
        )
        == 2
    )
    assert task_path.read_text() == original


def test_console_entrypoint_loads_cwd_plugin(task_path: Path, tmp_path: Path) -> None:
    (tmp_path / "custom_local_solver.py").write_text(
        'print("import log")\n'
        "def solve(task):\n"
        '    print("prediction log")\n'
        "    return task.test\n"
    )
    console = Path(sys.executable).with_name("arcagi")
    result = subprocess.run(
        [
            str(console),
            "solve",
            str(task_path),
            "--solver",
            "custom_local_solver:solve",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"sample": [[[3]], [[4, 5]]]}
    assert "import log" in result.stderr
    assert "prediction log" in result.stderr
