"""Task-by-task comparison, category grouping, and label file loading."""

import csv
import json
import sys
from pathlib import Path

import pytest

from arcagi.cli import main
from arcagi.experiments.compare import compare_reports
from arcagi.experiments.labels import UNLABELED, load_labels


def eval_report(path: Path, solver: str, correct: dict[str, bool]) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "arcagi-evaluation/1",
                "solver": solver,
                "tasks": [
                    {"task_id": task_id, "correct": value}
                    for task_id, value in correct.items()
                ],
            }
        )
    )
    return path


def experiment_report(path: Path, runs: list[tuple[str, str, bool]]) -> Path:
    path.mkdir()
    (path / "results.json").write_text(
        json.dumps(
            {
                "schema": "arcagi-experiment/1",
                "runs": [
                    {"solver": solver, "task_id": task_id, "correct": correct}
                    for solver, task_id, correct in runs
                ],
            }
        )
    )
    return path


@pytest.fixture
def reports(tmp_path: Path) -> tuple[Path, Path]:
    base = eval_report(
        tmp_path / "base.json", "base", {"t1": True, "t2": False, "t3": True}
    )
    new = eval_report(
        tmp_path / "new.json", "new", {"t1": True, "t2": True, "t3": False, "t4": True}
    )
    return base, new


def test_pairwise_changes_and_matrix(reports) -> None:
    base, new = reports
    result = compare_reports([str(base), str(new)])
    assert result["baseline"] == "base"
    assert [
        (m["name"], m["tasks_solved"], m["tasks_total"]) for m in result["methods"]
    ] == [
        ("base", 2, 3),
        ("new", 3, 4),
    ]
    pair = result["pairs"][0]
    assert pair["common_tasks"] == 3
    assert pair["both_solved"] == 1 and pair["neither_solved"] == 0
    assert pair["only_a_solved"] == ["t3"] and pair["only_b_solved"] == ["t2"]
    assert result["changes"] == [
        {
            "method": "new",
            "baseline": "base",
            "newly_solved": ["t2"],
            "regressed": ["t3"],
        }
    ]
    t4 = next(task for task in result["tasks"] if task["task_id"] == "t4")
    assert t4["results"]["base"] is None and t4["results"]["new"]["solved"] is True
    assert result["categories"] == []


def test_categories_overlap_and_include_unlabeled(reports) -> None:
    base, new = reports
    labels = {"t1": ("fill", "symmetry"), "t2": ("fill",)}
    result = compare_reports([str(base), str(new)], labels)
    groups = {group["category"]: group for group in result["categories"]}
    assert set(groups) == {"fill", "symmetry", UNLABELED}
    assert groups["fill"]["methods"]["base"] == {
        "tasks_total": 2,
        "tasks_solved": 1,
        "accuracy": 0.5,
    }
    assert groups["fill"]["methods"]["new"]["tasks_solved"] == 2
    assert groups[UNLABELED]["tasks_total"] == 2
    assert groups[UNLABELED]["methods"]["base"]["tasks_total"] == 1


def test_experiment_runs_require_all_repeats_and_names(tmp_path: Path) -> None:
    exp = experiment_report(
        tmp_path / "exp",
        [("a", "t1", True), ("a", "t1", False), ("b", "t1", True), ("b", "t1", True)],
    )
    result = compare_reports([f"run1={exp}"])
    names = [method["name"] for method in result["methods"]]
    assert names == ["run1/a", "run1/b"]
    cell = result["tasks"][0]["results"]["run1/a"]
    assert cell == {"runs": 2, "correct": 1, "solved": False}
    assert result["changes"][0]["newly_solved"] == ["t1"]


def test_duplicate_names_and_unknown_reports_rejected(reports, tmp_path) -> None:
    base, _ = reports
    with pytest.raises(ValueError, match="Duplicate method name"):
        compare_reports([str(base), str(base)])
    assert (
        compare_reports([str(base), f"again={base}"])["methods"][1]["name"] == "again"
    )
    other = tmp_path / "other.json"
    other.write_text("{}")
    with pytest.raises(ValueError, match="not an arcagi"):
        compare_reports([str(other)])


def test_load_labels_csv_variants(tmp_path: Path) -> None:
    path = tmp_path / "labels.csv"
    path.write_text(
        "task_id,family,size\n"
        "a.json,fill,small\n"
        "a,symmetry|fill,large\n"
        ",ignored,x\n"
        "b,,small\n"
    )
    assert load_labels(path) == {"a": ("fill", "symmetry|fill")}
    assert load_labels(path, separator="|") == {"a": ("fill", "symmetry")}
    assert load_labels(path, column="size") == {
        "a": ("large", "small"),
        "b": ("small",),
    }
    with pytest.raises(ValueError, match="no column"):
        load_labels(path, column="missing")
    bad = tmp_path / "bad.csv"
    bad.write_text("id,family\na,b\n")
    with pytest.raises(ValueError, match="task_id"):
        load_labels(bad)


def test_load_labels_json(tmp_path: Path) -> None:
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"a": "fill", "b": ["x", "y"]}))
    assert load_labels(path) == {"a": ("fill",), "b": ("x", "y")}
    path.write_text(json.dumps({"a": 3}))
    with pytest.raises(ValueError, match="strings"):
        load_labels(path)


def test_compare_cli_outputs(reports, tmp_path: Path, capsys) -> None:
    base, new = reports
    labels = tmp_path / "labels.csv"
    labels.write_text("task_id,kind\nt2,fill\n")
    matrix = tmp_path / "matrix.csv"
    output = tmp_path / "cmp.json"
    args = ["compare", str(base), str(new), "--labels", str(labels)]
    assert main([*args, "--matrix-csv", str(matrix), "--output", str(output)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["changes"][0]["newly_solved"] == ["t2"]
    assert json.loads(output.read_text())["schema"] == "arcagi-comparison/1"
    rows = list(csv.reader(matrix.open()))
    assert rows[0] == ["task_id", "categories", "base", "new"]
    assert rows[2] == ["t2", "fill", "0", "1"]
    assert rows[4] == ["t4", UNLABELED, "", "1"]
    assert main([*args, "--format", "markdown"]) == 0
    text = capsys.readouterr().out
    assert "newly solved (1): t2" in text and "| fill | 1 | 0/1 | 1/1 |" in text
    assert main(["compare", str(base), "--output", str(base)]) == 2
    assert "overwrite" in capsys.readouterr().err


def test_compare_real_experiment_output(tmp_path: Path, capsys) -> None:
    task = tmp_path / "t.json"
    task.write_text(
        json.dumps(
            {
                "train": [{"input": [[1]], "output": [[1]]}],
                "test": [{"input": [[1]], "output": [[1]]}],
            }
        )
    )
    solver = tmp_path / "solver.py"
    solver.write_text(
        "import json, pathlib, sys\n"
        "req = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "out = [p['input'] for p in req['task']['test']]\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({req['task_id']: out}))\n"
        "pathlib.Path(sys.argv[3]).write_text(json.dumps({'reasoning': 'copy'}))\n"
    )
    config = tmp_path / "exp.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "tasks": [{"path": "t.json"}],
                "solvers": [
                    {
                        "name": "copy",
                        "command": [
                            sys.executable,
                            "solver.py",
                            "{input}",
                            "{output}",
                            "{trace}",
                        ],
                    }
                ],
            }
        )
    )
    out = tmp_path / "run"
    assert main(["experiment", str(config), "--output", str(out)]) == 0
    capsys.readouterr()
    results = json.loads((out / "results.json").read_text())
    assert results["runs"][0]["trace"]["reasoning"] == "copy"
    assert main(["compare", str(out), "--format", "markdown"]) == 0
    assert "| copy | 1 | 1 | 100.0% |" in capsys.readouterr().out
