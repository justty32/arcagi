"""GPU fallback stays opt-in and cannot replace a mainline answer."""

import json
import os

import pytest

from arcagi.solvers import gated, search
from arcagi.solvers.trace import SolverResult, validate_trace
from arcagi.tasks import Example, SolverTask, task_from_dict

IDENTITY = json.dumps([])
RECOLOR = json.dumps([["colormap", [[1, 2]]]])
UNSEEN = json.dumps([["colormap", [[1, 2], [3, 9]]]])


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.delenv("ARCAGI_GPU_FALLBACK", raising=False)
    monkeypatch.setattr(gated, "SYNTH_ROOT", tmp_path / "no-synth")


def _task():
    return SolverTask(
        "gpu-test",
        (Example(((1, 0),), ((2, 0),)), Example(((0, 1),), ((0, 2),))),
        (((1, 3),), ((0, 1),)),
    )


def _trace(program=None):
    return {
        "schema_version": "arcagi-trace/1",
        "attempts": (
            [{"id": "p0", "kind": "program", "program": program}]
            if program is not None
            else []
        ),
        "selected": "p0" if program is not None else None,
        "metadata": {"source": "native", "fixed": [1, "trace"]},
    }


def _unexpected(*args, **kwargs):
    raise AssertionError("GPU fallback must not run")


def _gpu_file(path, task_id="gpu-test", program=RECOLOR):
    path.write_text(
        json.dumps({"task": task_id, "best": {"program": json.loads(program)}}) + "\n"
    )
    return path


def test_mainline_answer_returns_same_verdict_without_evaluating(monkeypatch):
    task = _task()
    verdict, _ = gated.gate(task, _trace(RECOLOR))
    assert not verdict.abstained
    monkeypatch.setattr(gated, "evaluate", _unexpected)
    assert gated.gpu_fallback(task, verdict, [UNSEEN]) is verdict
    assert verdict.reason == "kept"


def test_abstained_mainline_accepts_train_passing_gpu_program_without_synth(
    monkeypatch,
):
    task = _task()
    verdict, _ = gated.gate(task, None)
    monkeypatch.setattr(gated, "synth_pairs", _unexpected)
    adopted = gated.gpu_fallback(task, verdict, [IDENTITY, RECOLOR])
    assert not adopted.abstained
    assert adopted.predictions == [[[2, 3]], [[0, 2]]]
    assert adopted.reason == "gpu-fallback: kept"
    assert adopted.chosen.candidate.origin == "gpu"
    assert adopted.chosen.candidate.synth_total == 0
    assert verdict.abstained and verdict.reason == "no candidates"


def test_unseen_gpu_output_keeps_original_abstention_and_echo():
    task = _task()
    verdict, _ = gated.gate(task, None)
    assert len(gated.evaluate(task, [(UNSEEN, "gpu")])) == 1
    rejected = gated.gpu_fallback(task, verdict, [UNSEEN])
    assert rejected is verdict
    assert rejected.abstained
    assert rejected.predictions == [[[1, 3]], [[0, 1]]]
    # Disabling the gates proves the unseen color caused the rejection.
    unguarded = gated.gpu_fallback(task, verdict, [UNSEEN], gates=())
    assert not unguarded.abstained
    assert unguarded.predictions == [[[2, 9]], [[0, 2]]]


@pytest.mark.parametrize("programs", [[IDENTITY], []])
def test_no_train_passing_gpu_program_keeps_original_verdict(programs):
    task = _task()
    verdict, _ = gated.gate(task, None)
    assert gated.gpu_fallback(task, verdict, programs) is verdict
    assert verdict.abstained
    assert verdict.predictions == [[[1, 3]], [[0, 1]]]


def _request(path):
    task = _task()
    raw = {
        "train": [{"input": e.input, "output": e.output} for e in task.train],
        "test": [{"input": g} for g in task.test],
    }
    path.write_text(json.dumps({"task_id": task.task_id, "task": raw}))
    return task_from_dict(raw, task_id=task.task_id).to_solver_task()


def _runner(trace):
    def run(_request_path, output_path, trace_path):
        output_path.write_text(json.dumps({"gpu-test": [[[8]]]}))
        trace_path.write_text(json.dumps(trace))

    return run


@pytest.mark.parametrize("env_value", [None, ""])
@pytest.mark.parametrize("program", [None, RECOLOR])
def test_disabled_main_is_byte_identical_to_old_gate_logic(
    tmp_path, monkeypatch, env_value, program
):
    request = tmp_path / "request.json"
    output, trace_path = tmp_path / "output.json", tmp_path / "trace.json"
    task = _request(request)
    inner = _trace(program)
    verdict, _ = gated.gate(task, inner)
    expected_output = (json.dumps({task.task_id: verdict.predictions}) + "\n").encode()
    expected_trace = (
        json.dumps(validate_trace(gated._annotate(inner, verdict))) + "\n"
    ).encode()
    if env_value is not None:
        monkeypatch.setenv("ARCAGI_GPU_FALLBACK", env_value)
    monkeypatch.setattr(gated, "load_gpu_programs", _unexpected)
    monkeypatch.setattr(gated, "gpu_fallback", _unexpected)
    assert (
        gated.main([str(request), str(output), str(trace_path)], runner=_runner(inner))
        == 0
    )
    assert output.read_bytes() == expected_output
    assert trace_path.read_bytes() == expected_trace


def test_enabled_main_without_task_programs_keeps_predictions(tmp_path, monkeypatch):
    request = tmp_path / "request.json"
    output, trace_path = tmp_path / "output.json", tmp_path / "trace.json"
    task = _request(request)
    inner = _trace()
    verdict, _ = gated.gate(task, inner)
    gpu_file = _gpu_file(tmp_path / "gpu.jsonl", task_id="other-task")
    monkeypatch.setenv("ARCAGI_GPU_FALLBACK", str(gpu_file))
    gated.main([str(request), str(output), str(trace_path)], runner=_runner(inner))
    assert (
        output.read_bytes()
        == (json.dumps({task.task_id: verdict.predictions}) + "\n").encode()
    )
    annotated = json.loads(trace_path.read_text())
    assert annotated["metadata"]["guard"].pop("gpu_fallback") == {
        "used": False,
        "n_programs": 0,
        "reason": "no candidates",
    }
    assert annotated == validate_trace(gated._annotate(inner, verdict))


@pytest.mark.parametrize("program", [None, RECOLOR])
def test_enabled_main_records_whether_gpu_was_used(tmp_path, monkeypatch, program):
    request = tmp_path / "request.json"
    output, trace_path = tmp_path / "output.json", tmp_path / "trace.json"
    _request(request)
    first = _gpu_file(tmp_path / "first.jsonl", task_id="other-task")
    second = _gpu_file(tmp_path / "second.jsonl")
    monkeypatch.setenv(
        "ARCAGI_GPU_FALLBACK", os.pathsep.join(map(str, (first, second)))
    )
    gated.main(
        [str(request), str(output), str(trace_path)], runner=_runner(_trace(program))
    )
    assert json.loads(output.read_text()) == {"gpu-test": [[[2, 3]], [[0, 2]]]}
    metadata = json.loads(trace_path.read_text())["metadata"]["guard"]
    assert metadata["gpu_fallback"] == {
        "used": program is None,
        "n_programs": 1,
        "reason": "gpu-fallback: kept" if program is None else "kept",
    }


@pytest.mark.parametrize(
    ("enabled", "program", "has_trace"),
    [
        (False, None, True),
        (False, RECOLOR, True),
        (True, None, True),
        (True, RECOLOR, True),
        (True, None, False),
    ],
)
def test_plugin_uses_same_opt_in_and_metadata(
    tmp_path, monkeypatch, enabled, program, has_trace
):
    task = _task()
    inner = _trace(program) if has_trace else None
    monkeypatch.setattr(search, "solve", lambda _task: SolverResult([], inner))
    if enabled:
        monkeypatch.setenv(
            "ARCAGI_GPU_FALLBACK", str(_gpu_file(tmp_path / "gpu.jsonl"))
        )
    else:
        monkeypatch.setattr(gated, "gpu_fallback", _unexpected)
    original, _ = gated.gate(task, inner)
    result = gated.solve(task)
    if enabled:
        assert result.predictions == [[[2, 3]], [[0, 2]]]
    else:
        assert result.predictions == original.predictions
        assert result.trace == gated._annotate(inner, original)
    if has_trace:
        assert "guard" not in inner["metadata"]
        metadata = result.trace["metadata"]["guard"]
        if enabled:
            assert metadata["gpu_fallback"]["used"] is (program is None)
            assert metadata["gpu_fallback"]["n_programs"] == 1
        else:
            assert "gpu_fallback" not in metadata
    else:
        assert result.trace is None


def test_load_gpu_programs_merges_best_then_samples_and_caches_paths(tmp_path):
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    identity, recolor, unseen = map(json.loads, (IDENTITY, RECOLOR, UNSEEN))
    records = [
        {
            "task": "t",
            "best": {"program": recolor},
            "samples": [identity, recolor, unseen, identity],
        },
        {"task": "other", "samples": [identity]},
        {"task": "empty", "samples": []},
        {"task": "t", "best": {}, "samples": [unseen]},
    ]
    first.write_text("".join(json.dumps(r) + "\n" for r in records))
    extra = [["flip_lr"]]
    second.write_text(
        json.dumps(
            {"task": "t", "best": {"program": identity}, "samples": [extra, unseen]}
        )
        + "\n"
    )
    paths = (str(first), str(second))
    programs = gated.load_gpu_programs(paths)
    assert programs == {
        "t": [RECOLOR, IDENTITY, UNSEEN, json.dumps(extra)],
        "other": [IDENTITY],
    }
    assert gated.load_gpu_programs(paths) is programs
    assert gated.load_gpu_programs(tuple(reversed(paths)))["t"] == [
        IDENTITY,
        json.dumps(extra),
        UNSEEN,
        RECOLOR,
    ]
