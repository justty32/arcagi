"""Validate the language-independent file protocol and retained artifacts."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from arcagi.eval import evaluate_tasks
from arcagi.solvers import predict, predict_with_trace
from arcagi.solvers.external import (
    ExternalSolverError,
    ExternalSolverTimeoutError,
    make_external_solver,
)
from arcagi.tasks import Example, Task

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "file_identity.py"


@pytest.fixture
def task() -> Task:
    return Task("abc", (Example(((1,),), ((2,),)),), (Example(((3,),), ((9,),)),))


def test_example_protocol_and_artifacts(tmp_path: Path, task: Task) -> None:
    solver = make_external_solver(
        [sys.executable, str(EXAMPLE), "--input", "{input}", "--output", "{output}"],
        run_dir=tmp_path,
        timeout=5,
        seed=42,
        params={"mode": "identity"},
    )
    assert solver.last_run is None
    assert predict(solver, task) == (((3,),),)
    record = solver.last_run
    request = json.loads(Path(record["input_path"]).read_text())
    assert request == {
        "schema_version": "arcagi-solver-input/1",
        "task_id": "abc",
        "task": {
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]]}],
        },
        "seed": 42,
        "params": {"mode": "identity"},
        "trace_path": record["trace_path"],
    }
    assert Path(record["trace_path"]).parent == Path(record["artifact_dir"])
    assert record["error"] is None
    assert record["returncode"] == 0
    assert record["elapsed_seconds"] > 0
    directory = Path(record["artifact_dir"])
    assert {path.name for path in directory.iterdir()} == {
        "request.json",
        "response.json",
        "stdout.log",
        "stderr.log",
        "run.json",
    }
    assert json.loads((directory / "run.json").read_text()) == record
    predict(solver, task)
    assert len(solver.records) == 2
    assert solver.records[0]["artifact_dir"] != solver.records[1]["artifact_dir"]


def test_example_params_change_behavior(tmp_path: Path, task: Task) -> None:
    solver = make_external_solver(
        [sys.executable, str(EXAMPLE), "--input", "{input}", "--output", "{output}"],
        run_dir=tmp_path,
        timeout=5,
        params={"mode": "zero"},
    )
    assert predict(solver, task) == (((0,),),)


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ('{"abc": [[[3]]], "abc": [[[4]]]}', "Duplicate JSON key"),
        ('{"abc": [[[3]]], "other": [[[3]]]}', "exactly task ID"),
        ("{}", "exactly task ID"),
        ("[]", "exactly task ID"),
        ('{"abc": []}', "exactly one prediction"),
        ('{"abc": [[[NaN]]]}', "Invalid JSON number"),
        ("not-json", "Invalid response JSON"),
    ],
)
def test_response_rejects_invalid_data(tmp_path: Path, task: Task, response, error):
    script = (
        "from pathlib import Path; import sys; "
        "Path(sys.argv[1]).write_text(sys.argv[2])"
    )
    solver = make_external_solver(
        [sys.executable, "-c", script, "{output}", response],
        run_dir=tmp_path,
        timeout=5,
    )
    with pytest.raises(ExternalSolverError, match=error):
        predict(solver, task)
    assert solver.last_run["status"] == "error"
    assert error in solver.last_run["error"]


def test_stdout_stderr_and_nonzero_exit_are_retained(
    tmp_path: Path, task: Task
) -> None:
    solver = make_external_solver(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)",
        ],
        run_dir=tmp_path,
        timeout=5,
    )
    with pytest.raises(ExternalSolverError, match="exited with code 7"):
        predict(solver, task)
    assert Path(solver.last_run["stdout_path"]).read_text().strip() == "out"
    assert Path(solver.last_run["stderr_path"]).read_text().strip() == "err"
    assert solver.last_run["returncode"] == 7


def test_timeout_reaps_process(tmp_path: Path, task: Task, monkeypatch) -> None:
    workers = []
    original = subprocess.Popen

    def capture(*args, **kwargs):
        worker = original(*args, **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(subprocess, "Popen", capture)
    solver = make_external_solver(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        run_dir=tmp_path,
        timeout=0.3,
    )
    with pytest.raises(ExternalSolverTimeoutError, match="exceeded 0.3 seconds"):
        predict(solver, task)
    assert workers[0].poll() is not None
    assert solver.last_run["elapsed_seconds"] < 5
    assert solver.last_run["status"] == "error"


def test_no_stale_response_or_stdin_block(tmp_path: Path, task: Task) -> None:
    solver = make_external_solver(
        [sys.executable, "-c", "import sys; assert sys.stdin.read() == ''"],
        run_dir=tmp_path,
        timeout=5,
    )
    (tmp_path / "response.json").write_text('{"abc": [[[3]]]}')
    with pytest.raises(ExternalSolverError, match="Invalid response JSON"):
        predict(solver, task)


def test_path_safe_and_substitutions_are_literal(tmp_path: Path) -> None:
    task = Task("../../{seed}/測試", (), (Example(((3,),)),))
    script = """import json,sys
from pathlib import Path
assert sys.argv[2] == '../../{' + 'seed}/測試'
assert sys.argv[3] == '42'
assert sys.argv[4] == '{unrelated}'
Path(sys.argv[1]).write_text(json.dumps({sys.argv[2]: [[[3]]]}))
"""
    solver = make_external_solver(
        [
            sys.executable,
            "-c",
            script,
            "{output}",
            "{task_id}",
            "{seed}",
            "{unrelated}",
        ],
        run_dir=tmp_path,
        timeout=5,
        seed=42,
    )
    assert predict(solver, task) == (((3,),),)
    assert Path(solver.last_run["artifact_dir"]).parent == tmp_path


def test_full_task_rejected(tmp_path: Path, task: Task) -> None:
    solver = make_external_solver([sys.executable], run_dir=tmp_path, timeout=5)
    with pytest.raises(TypeError, match="label-free"):
        solver(task)


@pytest.mark.parametrize("command", ["echo hello", [], [123], [""]])
def test_command_must_be_argv(tmp_path: Path, command) -> None:
    with pytest.raises(ValueError, match="argv array"):
        make_external_solver(command, run_dir=tmp_path, timeout=5)


def test_command_cwd_and_shell_characters_remain_literal(tmp_path: Path, task: Task):
    script = tmp_path / "solver script.py"
    script.write_text(
        """import json,sys
from pathlib import Path
assert Path.cwd() == Path(sys.argv[3])
assert sys.argv[2] == '$HOME; echo unexpected & {other}'
Path(sys.argv[1]).write_text(json.dumps({'abc': [[[3]]]}))
""",
        encoding="utf-8",
    )
    solver = make_external_solver(
        [
            sys.executable,
            script.name,
            "{output}",
            "$HOME; echo unexpected & {other}",
            str(tmp_path),
        ],
        run_dir=tmp_path / "runs",
        cwd=tmp_path,
        timeout=5,
    )
    assert predict(solver, task) == (((3,),),)


def test_invalid_grid_is_recorded_as_error(tmp_path: Path, task: Task) -> None:
    script = (
        "from pathlib import Path; import sys; "
        "Path(sys.argv[1]).write_text('{\"abc\": [[[true]]]}')"
    )
    solver = make_external_solver(
        [sys.executable, "-c", script, "{output}"],
        run_dir=tmp_path,
        timeout=5,
    )
    with pytest.raises(ValueError, match="not bool"):
        predict(solver, task)
    assert solver.last_run["status"] == "error"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_timeout_validation(tmp_path: Path, timeout: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        make_external_solver([sys.executable], run_dir=tmp_path, timeout=timeout)


EXAMPLES = EXAMPLE.parent
TWO_TESTS = Task(
    "two",
    (Example(((1,),), ((1,),)),),
    (Example(((3, 4), (5, 6)), ((3, 4), (5, 6))), Example(((7,),), ((0,),))),
)


def _write_files(response: str, trace: str | None) -> str:
    lines = [
        "from pathlib import Path; import sys",
        f"Path(sys.argv[1]).write_text({response!r})",
    ]
    if trace is not None:
        lines.append(f"Path(sys.argv[2]).write_text({trace!r})")
    return "\n".join(lines)


def test_trace_file_is_returned_and_scored_separately(tmp_path: Path, task: Task):
    trace = json.dumps({"attempts": [{"id": "x", "train_results": [True]}]})
    solver = make_external_solver(
        [sys.executable, "-c", _write_files('{"abc": [[[9]]]}', trace)]
        + ["{output}", "{trace}"],
        run_dir=tmp_path,
        timeout=5,
    )
    grids, parsed, error = predict_with_trace(solver, task)
    assert grids == (((9,),),)
    assert parsed["attempts"][0]["id"] == "x" and error is None
    report = evaluate_tasks([task], solver)
    assert report["tasks_correct"] == 1
    assert report["tasks"][0]["trace"]["schema_version"] == "arcagi-trace/1"


@pytest.mark.parametrize("trace", ["not json", '{"attempts": 3}', "[]"])
def test_invalid_trace_file_is_a_note_not_a_failure(tmp_path, task, trace):
    solver = make_external_solver(
        [sys.executable, "-c", _write_files('{"abc": [[[9]]]}', trace)]
        + ["{output}", "{trace}"],
        run_dir=tmp_path,
        timeout=5,
    )
    report = evaluate_tasks([task], solver)
    assert report["tasks_correct"] == 1 and report["errors"] == 0
    assert report["tasks"][0]["trace"] is None
    assert "Invalid trace file" in report["tasks"][0]["trace_error"]
    assert solver.last_run["trace_error"] == report["tasks"][0]["trace_error"]


def test_trace_survives_failed_run(tmp_path: Path, task: Task) -> None:
    solver = make_external_solver(
        [sys.executable, "-c", _write_files("{}", '{"reasoning": "stuck"}')]
        + ["{output}", "{trace}"],
        run_dir=tmp_path,
        timeout=5,
    )
    report = evaluate_tasks([task], solver)
    assert report["errors"] == 1
    assert report["tasks"][0]["trace"]["reasoning"] == "stuck"


def test_sh_example_works_through_protocol(tmp_path: Path) -> None:
    solver = make_external_solver(
        ["sh", str(EXAMPLES / "sh_identity.sh"), "{input}", "{output}", "{trace}"],
        run_dir=tmp_path,
        timeout=10,
        params={"note": '}, "seed": [1]'},
    )
    report = evaluate_tasks([TWO_TESTS], solver)
    assert report["errors"] == 0 and report["tests_correct"] == 1
    assert report["tasks"][0]["trace"]["selected"] == "copy"


@pytest.mark.skipif(shutil.which("cc") is None, reason="no C compiler")
def test_c_example_compiles_and_works(tmp_path: Path) -> None:
    binary = tmp_path / "solver"
    subprocess.run(
        ["cc", "-std=c99", "-O2", "-o", str(binary)]
        + [str(EXAMPLES / "c_identity" / "solver.c")],
        check=True,
    )
    solver = make_external_solver(
        [str(binary), "{input}", "{output}", "{trace}"],
        run_dir=tmp_path / "runs",
        timeout=10,
    )
    report = evaluate_tasks([TWO_TESTS], solver)
    assert report["errors"] == 0 and report["tests_correct"] == 1
    assert report["tasks"][0]["trace"]["solver"] == "c_identity"
