import json

import pytest

from arcagi.llm import candidates as cd
from arcagi.llm import rescore as rs
from arcagi.llm import tasks as tk
from arcagi.llm import trace as tr
from arcagi.llm import verify as vf

GOOD = {
    "kind": "transform",
    "body": [["split_overlay", "v", "and"], ["colormap", [[10, 2]]]],
}


def test_prompt_view_has_no_test_output():
    task = tk.load("0520fde7", "training")
    text = tk.prompt_view("0520fde7", "training")
    assert "train 2: output" in text and "test 0: input" in text
    assert "test 0: output" not in text
    out = "\n".join(" ".join(map(str, r)) for r in task["test"][0]["output"])
    assert out not in text.split("## test 0: input")[1]


def test_check_and_score():
    res = vf.check("0520fde7", "training", GOOD)
    assert res["train_all"] and res["train_pass"] == 1.0
    assert "test_exact" not in res
    assert vf.score("0520fde7", "training", GOOD)["test_exact"] is True


def test_check_reports_failures_without_raising():
    bad = vf.check("0520fde7", "training", {"kind": "transform", "body": [["nope"]]})
    assert bad["train_pass"] == 0.0 and bad["pairs"][0]["error"]
    assert vf.check("0520fde7", "training", {"kind": "x"})["valid"] is False


def test_task_background_is_used():
    rule = {"kind": "transform", "body": [["recolor_sel", "4same", "size", 1, 1]]}
    assert vf.check("aedd82e4", "training", rule)["train_all"]


def test_pred_and_formula_are_syntax_only():
    res = vf.check("0520fde7", "training", {"kind": "pred", "body": ["eq", "size", 1]})
    assert res["valid"] and res["train_pass"] is None


def test_components_and_digest():
    prog = [["crop_extract", ["subgrid", ["pred", "4same", ["rank", "size", "max"]]]]]
    kinds = sorted(k for k, _ in cd.components(prog))
    assert kinds == ["extract", "pred"]
    assert cd.digest("pred", ["eq", "size", 1]) == cd.digest("pred", ["eq", "size", 1])
    assert cd.shell("extract", prog[0][1])["out"] == "grid"


def test_emit_writes_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "ROOT", tmp_path)
    prog = [["crop_extract", ["subgrid", ["pred", "4same", ["rank", "size", "max"]]]]]
    made = cd.emit(
        {"kind": "transform", "body": prog},
        prog,
        task_id="t",
        split="training",
        model="m",
    )
    assert len(made) == 3
    rule = json.loads((tmp_path / made[0] / "_rule.json").read_text())
    assert set(rule) == {"kind", "in", "out", "body"}


def test_judge_transform_needs_two_tasks():
    assert rs.judge("transform", GOOD["body"], {"a"})["verdict"] == "solution_only"
    assert rs.judge("pred", ["eq", "size", 1], set())["verdict"] == "dropped"


def test_trace_summary(tmp_path):
    path = tmp_path / "t.jsonl"
    tr.append(
        path,
        {
            "task": "a",
            "split": "training",
            "rank": 1,
            "train_pass": 1.0,
            "train_all": True,
            "test_exact": False,
            "tokens": 5,
            "seconds": 1,
        },
    )
    tr.append(
        path,
        {
            "task": "a",
            "split": "training",
            "rank": 0,
            "train_pass": 0.5,
            "train_all": False,
            "test_exact": None,
            "tokens": 5,
            "seconds": 1,
        },
    )
    (row,) = tr.summarize(tr.read(path))
    assert row["train_all"] and not row["test_exact"] and row["best_train_pass"] == 1.0


@pytest.mark.parametrize("split", ["nope"])
def test_bad_split(split):
    with pytest.raises(ValueError):
        tk.load("0520fde7", split)
