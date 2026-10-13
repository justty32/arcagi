"""Report semantics preserve failures, repeated trials, and raw provenance."""

import csv
import json

import pytest

from arcagi.experiments.report import summarize_runs, write_report


def _run(**changes):
    result = {
        "solver": "method",
        "task_id": "task-a",
        "tags": ["copy", "small"],
        "seed": 7,
        "repeat": 0,
        "params": {"budget": 20},
        "correct": True,
        "tests_total": 2,
        "tests_correct": 2,
        "elapsed_seconds": 1.0,
        "error": None,
        "artifact_dir": "runs/0000",
        "returncode": 0,
        "predictions": [[[1]], [[2]]],
    }
    result.update(changes)
    return result


def test_repeated_runs_and_timeouts_remain_in_denominator() -> None:
    runs = [
        _run(),
        _run(repeat=1, correct=False, tests_correct=1, elapsed_seconds=3.0),
        _run(
            repeat=2,
            correct=False,
            tests_correct=0,
            elapsed_seconds=10.0,
            error="timeout",
            returncode=None,
            predictions=None,
        ),
    ]
    summary = summarize_runs(runs)
    solver = next(row for row in summary if row["scope"] == "solver")
    assert solver["runs_total"] == 3
    assert solver["runs_correct"] == 1
    assert solver["run_accuracy"] == pytest.approx(1 / 3)
    assert solver["test_accuracy"] == 0.5
    assert solver["errors"] == 1
    assert solver["elapsed_mean_seconds"] == pytest.approx(14 / 3)
    assert solver["elapsed_median_seconds"] == 3.0
    task = next(row for row in summary if row["scope"] == "task")
    assert task["run_accuracy"] == pytest.approx(1 / 3)


def test_overlapping_tags_are_separate_groups_not_added_to_overall_count() -> None:
    rows = summarize_runs([_run(tags=["copy", "copy", "small"])])
    overall = next(row for row in rows if row["scope"] == "solver")
    assert overall["runs_total"] == 1
    tags = [row for row in rows if row["scope"] == "tag"]
    assert [(row["group"], row["runs_total"]) for row in tags] == [
        ("copy", 1),
        ("small", 1),
    ]


def test_reports_preserve_json_escape_html_and_protect_csv(tmp_path) -> None:
    name = '=HYPERLINK("https://example.invalid")<script>x</script>'
    report = {
        "schema": "arcagi-experiment/1",
        "config_path": "<img src=x>",
        "runs": [
            _run(
                solver=name,
                task_id="@task",
                error="+error",
                correct=False,
                tests_correct=0,
                tags=["<b>tag</b>"],
            )
        ],
        "aggregates": [],
    }
    paths = write_report(report, tmp_path)
    assert set(paths) == {"results.json", "results.csv", "summary.csv", "report.html"}
    assert json.loads((tmp_path / "results.json").read_text()) == report
    with (tmp_path / "results.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["solver"] == "'" + name
    assert row["task_id"] == "'@task"
    assert row["error"] == "'+error"
    assert json.loads(row["params"]) == {"budget": 20}
    html = (tmp_path / "report.html").read_text()
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;tag&lt;/b&gt;" in html
    assert "<svg " in html
    assert 'width="0.00"' in html
    assert "0.0%" in html
    assert "1/1" not in html
    assert "不可把組別題數加總" in html


def test_two_solvers_have_separate_task_matrix_and_summary(tmp_path) -> None:
    report = {
        "runs": [_run(solver="A"), _run(solver="B", correct=False, tests_correct=0)]
    }
    write_report(report, tmp_path)
    with (tmp_path / "summary.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    scores = {
        row["solver"]: row["run_accuracy"] for row in rows if row["scope"] == "task"
    }
    assert scores == {"A": "1.0", "B": "0.0"}
    html = (tmp_path / "report.html").read_text()
    assert "100.0% (1/1)" in html
    assert "0.0% (0/1)" in html


def test_empty_report_has_valid_csv_headers_and_html(tmp_path) -> None:
    write_report({"runs": []}, tmp_path)
    assert (tmp_path / "results.csv").read_text().startswith("solver,task_id,")
    assert (tmp_path / "report.html").read_text().startswith("<!doctype html>")
