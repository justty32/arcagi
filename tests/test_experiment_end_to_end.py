"""Exercise the language-neutral experiment protocol with an actual Node solver."""

import csv
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is optional for this test")


def _run(config: Path, output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "arcagi",
            "experiment",
            str(config),
            "--output",
            str(output),
            *extra,
        ],
        cwd=config.parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _workspace(tmp_path: Path) -> tuple[Path, dict]:
    directory = tmp_path / "config with spaces"
    directory.mkdir()
    for name in ("first task", "second task"):
        (directory / f"{name}.json").write_text(
            json.dumps(
                {
                    "train": [{"input": [[0]], "output": [[1]]}],
                    "test": [
                        {"input": [[2]], "output": [[3]]},
                        {"input": [[4, 5]], "output": [[5, 6]]},
                    ],
                }
            )
        )
    (directory / "node solver.cjs").write_text(
        "const fs = require('fs');\n"
        "const request = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));\n"
        "if (request.task.test.some(pair => 'output' in pair)) process.exit(90);\n"
        "if (request.params.fail_on === request.task_id) process.exit(17);\n"
        "const predictions = request.task.test.map(pair => pair.input.map(\n"
        "  row => row.map(cell => cell + request.params.increment)));\n"
        "const finish = () => fs.writeFileSync(process.argv[3],\n"
        "  JSON.stringify({[request.task_id]: predictions}));\n"
        "if (request.params.sleep_on === request.task_id) setTimeout(finish, 5000);\n"
        "else finish();\n",
        encoding="utf-8",
    )
    command = [NODE, "node solver.cjs", "{input}", "{output}"]
    config = {
        "version": 1,
        "tasks": [
            {
                "path": "first task.json",
                "tags": ["<easy>", "<img src=x onerror=alert(1)>"],
            },
            {"path": "second task.json", "tags": ["hard"]},
        ],
        "solvers": [
            {
                "name": "method-good",
                "command": command,
                "cwd": ".",
                "params": {"increment": 1},
            },
            {
                "name": "sometimes-fails",
                "command": command,
                "cwd": ".",
                "params": {"increment": 1, "fail_on": "second task"},
            },
        ],
        "seeds": [13, 29],
        "repeats": 2,
        "timeout_seconds": 2,
    }
    return directory / "experiment config.json", config


def test_node_methods_repeats_artifacts_and_reports(tmp_path: Path) -> None:
    config_path, config = _workspace(tmp_path)
    config_path.write_text(json.dumps(config))
    output = tmp_path / "results with spaces"
    process = _run(config_path, output)
    assert process.returncode == 1, process.stderr
    report = json.loads((output / "results.json").read_text())
    runs = report["runs"]
    assert len(runs) == 16
    assert report["errors"] == 4
    assert sum(run["correct"] for run in runs) == 12
    assert sum(run["tests_total"] for run in runs) == 32
    assert sum(run["tests_correct"] for run in runs) == 24

    matching_inputs = defaultdict(list)
    for run in runs:
        artifact = Path(run["artifact_dir"])
        request = json.loads((artifact / "request.json").read_text())
        assert request["seed"] == run["seed"]
        assert request["params"] == run["params"]
        assert all(set(pair) == {"input"} for pair in request["task"]["test"])
        assert request["task"]["train"][0]["output"] == [[1]]
        for filename in ("stdout.log", "stderr.log", "run.json"):
            assert (artifact / filename).is_file()
        if run["error"] is None:
            assert (artifact / "response.json").is_file()
        matching_inputs[(run["task_id"], run["seed"], run["repeat"])].append(
            request["task"]
        )
    assert len(matching_inputs) == 8
    assert all(
        len(pair) == 2 and pair[0] == pair[1] for pair in matching_inputs.values()
    )

    with (output / "results.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 16
    assert {int(row["seed"]) for row in rows} == {13, 29}
    with (output / "summary.csv").open(newline="") as stream:
        summaries = list(csv.DictReader(stream))
    failed_method = next(
        row
        for row in summaries
        if row["scope"] == "solver" and row["solver"] == "sometimes-fails"
    )
    assert int(failed_method["runs_total"]) == 8
    assert int(failed_method["runs_correct"]) == 4
    assert float(failed_method["run_accuracy"]) == 0.5
    html = (output / "report.html").read_text()
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&lt;easy&gt;" in html


def test_node_timeout_continues_and_task_tag_selection(tmp_path: Path) -> None:
    config_path, config = _workspace(tmp_path)
    config["seeds"] = [13]
    config["repeats"] = 1
    config["timeout_seconds"] = 0.8
    config["solvers"] = [config["solvers"][0]]
    config["solvers"][0]["params"]["sleep_on"] = "first task"
    config_path.write_text(json.dumps(config))
    output = tmp_path / "timeout results"
    process = _run(config_path, output)
    assert process.returncode == 1, process.stderr
    runs = json.loads((output / "results.json").read_text())["runs"]
    assert len(runs) == 2
    assert sum(run["correct"] for run in runs) == 1
    assert sum(run["tests_total"] for run in runs) == 4
    failed = next(run for run in runs if run["task_id"] == "first task")
    assert "Timeout" in failed["error"]

    output = tmp_path / "selected results"
    process = _run(config_path, output, "--task", "second task", "--tag", "hard")
    assert process.returncode == 0, process.stderr
    runs = json.loads((output / "results.json").read_text())["runs"]
    assert len(runs) == 1
    assert runs[0]["task_id"] == "second task"
