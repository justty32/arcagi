"""Offline top-2 scoring from eval reports with ``trace.metadata.second``."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "score_top2.py"
_spec = importlib.util.spec_from_file_location("score_top2", SCRIPT)
assert _spec and _spec.loader
score_top2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_top2)

A, B = [[1, 2]], [[3, 4]]


def _task(task_id, tests, second=None):
    trace = None if second is None else {"metadata": {"second": second}}
    return {
        "task_id": task_id,
        "correct": all(t["correct"] for t in tests),
        "tests": [
            {
                "index": i,
                "correct": t["correct"],
                "prediction": t["pred"],
                "expected": t["exp"],
            }
            for i, t in enumerate(tests)
        ],
        "trace": trace,
    }


def _t(pred, exp):
    return {"pred": pred, "exp": exp, "correct": pred == exp}


REPORT = {
    "tasks": [
        _task("solved", [_t(A, A)], second=[B]),
        _task("second_hits", [_t(B, A)], second=[A]),
        _task("mixed", [_t(A, A), _t(A, B)], second=[None, B]),
        _task("partial", [_t(B, A), _t(A, B)], second=[A, None]),
        _task("no_second", [_t(B, A)]),
        _task("bad_meta", [_t(B, A)], second="oops"),
    ]
}


def test_score_counts_second_attempts_per_test() -> None:
    score = score_top2.score_top2(REPORT)
    assert score["tasks_correct_top1"] == 1
    assert score["tasks_correct_top2"] == 3
    assert score["newly_correct"] == ["second_hits", "mixed"]


def test_missing_second_equals_top1() -> None:
    report = {"tasks": [_task("x", [_t(B, A)]), _task("y", [_t(A, A)])]}
    score = score_top2.score_top2(report)
    assert score["tasks_correct_top1"] == score["tasks_correct_top2"] == 1
    assert score["newly_correct"] == []


def test_cli_json_and_markdown(tmp_path, capsys) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(REPORT), encoding="utf-8")
    assert score_top2.main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["tasks_correct_top2"] == 3
    assert score_top2.main([str(path), "--format", "markdown"]) == 0
    assert "| top-2 correct | 3 |" in capsys.readouterr().out
