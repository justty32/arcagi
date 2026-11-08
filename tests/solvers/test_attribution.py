"""scripts/attribution.py: who solved each task, which generated blocks."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "attribution.py"
spec = importlib.util.spec_from_file_location("attribution", SCRIPT)
attribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attribution)


def _trace(description, program, metadata, data=None):
    attempt = {"id": "a1", "description": description, "program": program}
    if data:
        attempt["data"] = data
    return {"attempts": [attempt], "selected": "a1", "metadata": metadata}


def test_blocks_in_scans_nested_strings() -> None:
    program = json.dumps(
        [
            ["extract_ab", 1],
            ["move_from", "4same", "all", 1, "formula_cd"],
            ["recolor_from", {"sel": ["pred_ef"]}],
            ["m_sub_1"],
            ["flip_lr"],
        ]
    )
    assert attribution.blocks_in(program) == [
        "extract_ab",
        "formula_cd",
        "m_sub_1",
        "pred_ef",
    ]
    assert attribution.blocks_in("not json") == []


def test_attribute_solvers() -> None:
    row = attribution.attribute(
        "t", True, _trace("program of cost 2.0", '[["llm_x"]]', {})
    )
    assert (row["solver"], row["origin"], row["blocks"]) == (
        "search",
        "python",
        "llm_x",
    )
    assert row["families"] == "llm" and row["correct"] == "1"
    row = attribution.attribute(
        "t", True, _trace("rewrite program of cost 2.0", "[]", {"source": "python"})
    )
    assert row["solver"] == "rewrite"
    row = attribution.attribute(
        "t", False, _trace("program", "[]", {"source": "native"}, {"origin": "seed"})
    )
    assert (row["solver"], row["origin"], row["correct"]) == ("native", "seed", "0")
    assert attribution.attribute("t", False, None)["solver"] == "none"
    empty = {"attempts": [], "selected": None, "metadata": {"source": "native"}}
    assert attribution.attribute("t", False, empty)["solver"] == "none"


def test_main_writes_csv_and_summary(tmp_path, capsys) -> None:
    report = {
        "tasks": [
            {"task_id": "a", "correct": True, "trace": None},
            {"task_id": "b", "correct": False, "trace": None},
        ]
    }
    (tmp_path / "r.json").write_text(json.dumps(report))
    record = {"task_id": "a", "trace": _trace("program", '[["extract_q"]]', {})}
    (tmp_path / "t.jsonl").write_text(json.dumps(record) + "\n")
    code = attribution.main(["x", str(tmp_path / "r.json"), str(tmp_path / "t.jsonl")])
    out = capsys.readouterr()
    assert code == 0
    lines = out.out.strip().splitlines()
    assert lines[0].startswith("task_id,correct,solver")
    assert lines[1].startswith("a,1,search,python,extract,extract_q")
    assert lines[2].startswith("b,0,none")
    assert "search: correct 1, wrong 0" in out.err


def test_summary_splits_python_native_and_overlap(tmp_path) -> None:
    rows = [
        attribution.attribute("a", True, _trace("program", "[]", {})),
        attribution.attribute("b", False, _trace("program", "[]", {})),
        attribution.attribute(
            "c", True, _trace("p", "[]", {"source": "native"}, {"origin": "cpp"})
        ),
    ]
    cpp_csv = tmp_path / "i.csv"
    cpp_csv.write_text("task_id,cpp_correct\na,1\nb,1\n")
    lines = attribution.summary(rows, attribution.load_cpp(str(cpp_csv)))
    assert "python own score 1, native adds 1" in lines
    overlap = [line for line in lines if line.startswith("overlap")][0]
    assert overlap.startswith("overlap (python right and C++ alone right) 1;")
    assert "interceptions (python wrong, C++ alone right) 1;" in overlap


def test_intercept_summary_counts() -> None:
    spec = importlib.util.spec_from_file_location(
        "intercept", SCRIPT.parent / "intercept.py"
    )
    intercept = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(intercept)
    out = [
        {"py_correct": "0", "cpp_correct": "1", "cpp_found": "1"},
        {"py_correct": "1", "cpp_correct": "1", "cpp_found": "1"},
        {"py_correct": "1", "cpp_correct": "0", "cpp_found": "0"},
    ]
    text = "\n".join(intercept.summary(out))
    assert "C++ right (interceptions): 1" in text
    assert "C++ also right (overlap): 1, C++ wrong: 1" in text
