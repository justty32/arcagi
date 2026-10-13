"""Timeouts must fail explicitly and leave the direct worker reaped."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from arcagi.solvers import predict
from arcagi.solvers.runtime import (
    SolverExecutionError,
    SolverTimeoutError,
    load_timed_solver,
)
from arcagi.tasks import Example, SolverTask, Task


@pytest.fixture
def task() -> Task:
    return Task(
        "deadline-test",
        (Example(((1,),), ((2,),)),),
        (Example(((3,),), ((9,),)),),
    )


@pytest.fixture
def plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    (tmp_path / "deadline_plugin.py").write_text(
        """import os
from pathlib import Path
import sys
import time


def identity(task):
    assert isinstance(task.test[0], tuple)
    assert task.test[0] == ((3,),)
    assert not hasattr(task.test[0], 'output')
    assert task.train[0].output == ((2,),)
    print('Plugin logging does not corrupt the result JSON')
    return task.test


def explode(task):
    raise RuntimeError('deliberate worker failure')


def slow(task):
    time.sleep(30)
    return task.test


def unserializable(task):
    return [object()]


def exit_error(task):
    os._exit(7)


def missing_response(task):
    os._exit(0)


def corrupt_response(task):
    Path(sys.argv[2]).write_text('{invalid-json')
    os._exit(0)
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    return "deadline_plugin"


def test_timed_solver_receives_only_solver_view(task: Task, plugin: str) -> None:
    assert predict(load_timed_solver(f"{plugin}:identity", 5), task) == (((3,),),)


def test_worker_exception_is_reported(task: Task, plugin: str) -> None:
    with pytest.raises(SolverExecutionError, match="RuntimeError: deliberate"):
        predict(load_timed_solver(f"{plugin}:explode", 5), task)


def test_timeout_reaps_worker(
    task: Task, plugin: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    workers = []
    original_popen = subprocess.Popen

    def record_worker(*args, **kwargs):
        worker = original_popen(*args, **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(subprocess, "Popen", record_worker)
    started = time.monotonic()
    with pytest.raises(SolverTimeoutError, match="exceeded 0.5 seconds"):
        predict(load_timed_solver(f"{plugin}:slow", 0.5), task)
    assert time.monotonic() - started < 5
    assert len(workers) == 1
    assert workers[0].poll() is not None
    assert predict(load_timed_solver("identity", 5), task) == (((3,),),)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_timeout_must_be_positive_and_finite(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite positive"):
        load_timed_solver("identity", timeout)


def test_full_task_is_rejected(task: Task) -> None:
    with pytest.raises(TypeError, match="label-free SolverTask"):
        load_timed_solver("identity", 5)(task)


@pytest.mark.parametrize(
    ("function", "message"),
    [
        ("unserializable", "not JSON serializable"),
        ("exit_error", "exited with code 7"),
        ("missing_response", "valid JSON response"),
        ("corrupt_response", "valid JSON response"),
    ],
)
def test_worker_protocol_failures(task: Task, plugin: str, function, message) -> None:
    with pytest.raises(SolverExecutionError, match=message):
        predict(load_timed_solver(f"{plugin}:{function}", 5), task)


def test_large_payload_does_not_block_on_pipe_capacity() -> None:
    grid = tuple((1,) * 30 for _ in range(30))
    task = SolverTask("large", (), (grid,) * 1000)
    predictions = load_timed_solver("identity", 10)(task)
    assert len(predictions) == 1000
    assert predictions[-1] == [list(row) for row in grid]


def test_plugin_importable_from_calling_directory(tmp_path: Path, plugin: str) -> None:
    source = str(Path(__file__).resolve().parents[2] / "src")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = source
    script = """import json
from arcagi.solvers.runtime import load_timed_solver
from arcagi.tasks import Example, SolverTask
task = SolverTask('cwd', (Example(((1,),), ((2,),)),), (((3,),),))
print(json.dumps(load_timed_solver('deadline_plugin:identity', 5)(task)))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert json.loads(completed.stdout) == [[[3]]]


def test_timeout_includes_plugin_import(
    task: Task, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "slow_import_plugin.py").write_text(
        "import time\ntime.sleep(30)\ndef solve(task): return task.test\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    started = time.monotonic()
    solver = load_timed_solver("slow_import_plugin:solve", 0.5)
    with pytest.raises(SolverTimeoutError):
        predict(solver, task)
    assert time.monotonic() - started < 5
