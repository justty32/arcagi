"""Check the experiment console entry point against real file-based solvers."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from arcagi.cli import main


@pytest.fixture
def experiment_config(tmp_path: Path) -> Path:
    for name in ("first", "second"):
        (tmp_path / f"{name}.json").write_text(
            json.dumps(
                {
                    "train": [{"input": [[1]], "output": [[1]]}],
                    "test": [{"input": [[2, 3]], "output": [[2, 3]]}],
                }
            )
        )
    (tmp_path / "solver with spaces.py").write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "request = json.loads(Path(sys.argv[1]).read_text())\n"
        "assert request['schema_version'] == 'arcagi-solver-input/1'\n"
        "assert request['seed'] in [3, 7]\n"
        "assert all('output' not in item for item in request['task']['test'])\n"
        "assert request['task']['train'][0]['output'] == [[1]]\n"
        "mode = request['params']['mode']\n"
        "grids = [item['input'] for item in request['task']['test']]\n"
        "if mode == 'zero':\n"
        "    grids = [[[0 for cell in row] for row in grid] for grid in grids]\n"
        "print('solver diagnostic')\n"
        "Path(sys.argv[2]).write_text(json.dumps({request['task_id']: grids}))\n"
    )
    config = {
        "version": 1,
        "tasks": [
            {"path": "first.json", "tags": ["focus", "smoke"]},
            {"path": "second.json", "tags": ["other"]},
        ],
        "solvers": [
            {
                "name": mode,
                "command": [
                    sys.executable,
                    "solver with spaces.py",
                    "{input}",
                    "{output}",
                ],
                "cwd": ".",
                "params": {"mode": mode},
            }
            for mode in ("identity", "zero")
        ],
        "seeds": [3, 7],
        "repeats": 2,
        "timeout_seconds": 5,
    }
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps(config))
    return path


def test_console_experiment_matrix_and_reports(
    experiment_config: Path, tmp_path: Path
) -> None:
    output = tmp_path / "experiment output"
    console = Path(sys.executable).with_name("arcagi")
    completed = subprocess.run(
        [
            str(console),
            "experiment",
            str(experiment_config),
            "--output",
            str(output),
            "--task",
            "first",
            "--tag",
            "focus",
        ],
        cwd=tmp_path.parent,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["runs_total"] == 8
    assert summary["errors"] == 0
    for filename in ("results.json", "results.csv", "summary.csv", "report.html"):
        assert (output / filename).is_file()
        assert (output / filename).stat().st_size > 0
    assert "<svg" in (output / "report.html").read_text()
    report = json.loads((output / "results.json").read_text())
    assert len(report["runs"]) == 8
    assert {run["task_id"] for run in report["runs"]} == {"first"}
    assert report["errors"] == 0


def test_experiment_unknown_tag_rejected(
    experiment_config: Path, tmp_path: Path, capsys
) -> None:
    assert (
        main(
            [
                "experiment",
                str(experiment_config),
                "--output",
                str(tmp_path / "missing-tag"),
                "--tag",
                "not-a-tag",
            ]
        )
        == 2
    )
    assert "error:" in capsys.readouterr().err


def test_experiment_solver_failures_reported(
    experiment_config: Path, tmp_path: Path, capsys
) -> None:
    config = json.loads(experiment_config.read_text())
    config["solvers"] = [
        {
            "name": "broken",
            "command": [
                sys.executable,
                "-c",
                "raise RuntimeError('intentional failure')",
                "{input}",
                "{output}",
            ],
        }
    ]
    config["seeds"] = [3]
    config["repeats"] = 1
    experiment_config.write_text(json.dumps(config))
    output = tmp_path / "failed jobs"
    assert (
        main(
            [
                "experiment",
                str(experiment_config),
                "--output",
                str(output),
                "--task",
                "first",
            ]
        )
        == 1
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["errors"] == 1
    assert json.loads((output / "results.json").read_text())["errors"] == 1
    assert (output / "report.html").is_file()
