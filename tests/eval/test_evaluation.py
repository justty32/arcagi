"""Exact scoring and failure accounting for public and held-out tasks."""

import json

import pytest

from arcagi.eval import evaluate_tasks, score_predictions
from arcagi.solvers import load_solver
from arcagi.tasks import SolverTask, Task, TaskValidationError, task_from_dict


def make_task(task_id: str, outputs: list[int | None]) -> Task:
    return task_from_dict(
        {
            "train": [{"input": [[1]], "output": [[1]]}],
            "test": [
                {"input": [[1]], **({"output": [[out]]} if out is not None else {})}
                for out in outputs
            ],
        },
        task_id=task_id,
    )


def test_task_score_requires_all_tests_and_reports_are_json() -> None:
    report = evaluate_tasks(
        [make_task("partial", [1, 2]), make_task("complete", [1])], load_solver()
    )
    assert report["attempts_per_test"] == 1
    assert report["scoring"] == "top1_exact_match"
    assert report["tasks_total"] == 2
    assert report["tasks_correct"] == 1
    assert report["task_accuracy"] == 0.5
    assert report["tests_total"] == 3
    assert report["tests_correct"] == 2
    assert report["test_accuracy"] == pytest.approx(2 / 3)
    assert report["errors"] == 0
    assert report["tasks"][0]["correct"] is False
    assert report["tasks"][0]["tests"][1] == {
        "index": 1,
        "correct": False,
        "prediction": [[1]],
        "expected": [[2]],
    }
    assert json.loads(json.dumps(report)) == report


def test_wrong_grid_shape_not_counted_as_match() -> None:
    report = evaluate_tasks([make_task("shape", [1])], lambda _: [[[1, 1]]])
    assert report["tasks_correct"] == report["tests_correct"] == 0
    assert report["errors"] == 0


def test_missing_labels_rejected_before_any_solver_execution() -> None:
    calls = []

    def solver(view: SolverTask) -> tuple:
        calls.append(view)
        return view.test

    with pytest.raises(TaskValidationError, match="hidden.test\\[0\\]: missing output"):
        evaluate_tasks([make_task("valid", [1]), make_task("hidden", [None])], solver)
    assert calls == []


def test_errors_count_all_tests_wrong_and_continue_to_next_task() -> None:
    def solver(view: SolverTask) -> tuple:
        if view.task_id == "broken":
            raise RuntimeError("failed to search")
        return view.test

    report = evaluate_tasks(
        [make_task("broken", [1, 1]), make_task("valid", [1])], solver
    )
    assert report["tasks_total"] == 2
    assert report["tests_total"] == 3
    assert report["tasks_correct"] == report["tests_correct"] == 1
    assert report["errors"] == 1
    assert report["tasks"][0]["error"] == "RuntimeError: failed to search"
    assert all(test["prediction"] is None for test in report["tasks"][0]["tests"])


def test_invalid_prediction_discards_partial_task_result() -> None:
    report = evaluate_tasks([make_task("bad", [1, 1])], lambda _: [[[1]], [[True]]])
    assert report["tests_correct"] == 0
    assert report["errors"] == 1


def test_interrupts_are_not_swallowed() -> None:
    def solver(_: SolverTask) -> tuple:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        evaluate_tasks([make_task("interrupt", [1])], solver)


def test_empty_dataset_and_duplicate_ids_rejected() -> None:
    with pytest.raises(TaskValidationError, match="empty"):
        evaluate_tasks([], load_solver())
    with pytest.raises(TaskValidationError, match="unique"):
        evaluate_tasks([make_task("same", [1]), make_task("same", [1])], load_solver())


def test_external_predictions_score_without_importing_a_solver() -> None:
    report = score_predictions(
        [make_task("a", [2, 3]), make_task("b", [4])],
        {"a": [[[2]], [[3]]], "b": [[[0]]]},
    )
    assert report["solver"] == "provided-predictions"
    assert report["tasks_correct"] == 1
    assert report["tests_correct"] == 2


def test_missing_external_predictions_remain_in_denominator() -> None:
    report = score_predictions([make_task("a", [1]), make_task("missing", [1, 1])], {})
    assert report["tasks_total"] == 2
    assert report["tests_total"] == 3
    assert report["tasks_correct"] == report["tests_correct"] == 0
    assert report["errors"] == 2
    assert "Missing predictions" in report["tasks"][0]["error"]


def test_unknown_external_prediction_ids_rejected() -> None:
    with pytest.raises(ValueError, match="unknown task IDs"):
        score_predictions([make_task("a", [1])], {"typo": [[[1]]]})
    with pytest.raises(ValueError, match="mapping"):
        score_predictions([make_task("a", [1])], [])
