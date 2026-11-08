"""Optional attempt traces: validation, Python plugins, timed workers, template."""

import json

import pytest

from arcagi.eval import evaluate_tasks
from arcagi.solvers import SolverResult, predict, predict_with_trace
from arcagi.solvers.runtime import load_timed_solver
from arcagi.solvers.template import solve as template_solve
from arcagi.solvers.trace import (
    TRACE_SCHEMA,
    TraceRecorder,
    TraceValidationError,
    check_on_train,
    validate_trace,
)
from arcagi.tasks import Example, Task

TRANSPOSE_TASK = Task(
    "transpose",
    (
        Example(((1, 2), (3, 4)), ((1, 3), (2, 4))),
        Example(((5, 6, 7),), ((5,), (6,), (7,))),
    ),
    (Example(((1, 0), (0, 2)), ((1, 0), (0, 2))), Example(((8, 9),), ((8,), (9,)))),
)


def test_minimal_trace_gets_defaults() -> None:
    assert validate_trace({}) == {"schema_version": TRACE_SCHEMA, "attempts": []}


def test_full_trace_round_trips_and_keeps_extra_keys() -> None:
    trace = {
        "schema_version": TRACE_SCHEMA,
        "solver": "aos",
        "attempts": [
            {
                "id": "h1",
                "kind": "hypothesis",
                "description": "recolor",
                "program": "(recolor 1 2)",
                "train_results": [True, False],
                "train_correct": 1,
                "train_total": 2,
                "selected": True,
                "elapsed_seconds": 0.5,
                "reasoning": "colors map one to one",
                "error": None,
                "data": {"llm_tokens": 12},
            }
        ],
        "selected": "h1",
        "reasoning": "free text",
        "elapsed_seconds": 1,
        "metadata": {"model": "x"},
        "custom": [1, 2],
    }
    assert validate_trace(trace) == trace


@pytest.mark.parametrize(
    ("trace", "message"),
    [
        ([], "expected a JSON object"),
        ({"schema_version": "other/1"}, "schema_version"),
        ({"attempts": {}}, "attempts: expected a list"),
        ({"attempts": [1]}, "expected an object"),
        ({"attempts": [{"train_results": [1]}]}, "expected booleans"),
        ({"attempts": [{"train_correct": True}]}, "booleans are not allowed"),
        ({"attempts": [{"train_total": -1}]}, ">= 0"),
        ({"attempts": [{"id": "a"}, {"id": "a"}]}, "unique"),
        ({"attempts": [{"id": "a"}], "selected": "b"}, "must name an attempt"),
        ({"reasoning": 3}, "wrong type"),
        ({"elapsed_seconds": float("nan")}, "not JSON serializable"),
        ({"metadata": {"x": object()}}, "not JSON serializable"),
    ],
)
def test_invalid_traces_are_rejected(trace, message) -> None:
    with pytest.raises(TraceValidationError, match=message):
        validate_trace(trace)


def test_check_on_train_counts_exceptions_as_failures() -> None:
    train = TRANSPOSE_TASK.train
    assert check_on_train(lambda grid: tuple(zip(*grid, strict=True)), train) == [
        True,
        True,
    ]
    assert check_on_train(lambda grid: grid, train) == [False, False]
    assert check_on_train(lambda grid: 1 / 0, train) == [False, False]


def test_recorder_builds_valid_trace() -> None:
    recorder = TraceRecorder(solver="demo")
    first = recorder.attempt("a", train_results=[True, False])
    second = recorder.attempt("b", kind="program", program="p", error="boom")
    recorder.select(second)
    recorder.reasoning = "why"
    recorder.metadata["k"] = 1
    trace = recorder.to_dict()
    assert trace["selected"] == second
    assert [a["selected"] for a in trace["attempts"]] == [False, True]
    assert trace["attempts"][0]["id"] == first
    assert trace["attempts"][0]["train_correct"] == 1
    assert trace["attempts"][1]["error"] == "boom"
    assert trace["solver"] == "demo" and trace["reasoning"] == "why"
    assert trace["metadata"] == {"k": 1}


def test_plain_solvers_still_work_without_trace() -> None:
    grids, trace, error = predict_with_trace(
        lambda task: list(task.test), TRANSPOSE_TASK
    )
    assert grids == TRANSPOSE_TASK.to_solver_task().test
    assert trace is None and error is None


def test_invalid_trace_does_not_fail_prediction() -> None:
    def solver(task):
        return SolverResult(list(task.test), {"attempts": "bad"})

    grids, trace, error = predict_with_trace(solver, TRANSPOSE_TASK)
    assert predict(solver, TRANSPOSE_TASK) == grids
    assert trace is None and "attempts" in error


def test_eval_report_keeps_traces_even_for_wrong_counts() -> None:
    def solver(task):
        return SolverResult([], {"reasoning": "gave up"})

    report = evaluate_tasks([TRANSPOSE_TASK], solver)
    task = report["tasks"][0]
    assert task["error"] and task["trace"]["reasoning"] == "gave up"
    assert task["elapsed_seconds"] >= 0
    assert report["traces"] == 1
    assert json.loads(json.dumps(report)) == report


def test_template_solves_symmetry_task_and_explains_choice() -> None:
    report = evaluate_tasks([TRANSPOSE_TASK], template_solve, solver_name="template")
    task = report["tasks"][0]
    assert task["correct"] is True
    trace = task["trace"]
    selected = [a for a in trace["attempts"] if a["selected"]]
    assert [a["program"] for a in selected] == ["transpose"]
    assert trace["selected"] == selected[0]["id"]
    assert len(trace["attempts"]) >= 4


def test_template_falls_back_to_inputs_without_selection() -> None:
    task = Task("x", (Example(((1,),), ((2,),)),), (Example(((3,),), ((3,),)),))
    result = template_solve(task.to_solver_task())
    assert result.predictions == [((3,),)]
    assert result.trace["selected"] is None


def test_timed_worker_passes_trace_through() -> None:
    solver = load_timed_solver("arcagi.solvers.template:solve", 20)
    report = evaluate_tasks([TRANSPOSE_TASK], solver)
    assert report["tasks"][0]["correct"] is True
    assert report["tasks"][0]["trace"]["schema_version"] == TRACE_SCHEMA
