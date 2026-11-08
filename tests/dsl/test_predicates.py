"""Predicate AST evaluation and predicate selectors (backward compatible)."""

import json

import pytest

from arcagi.dsl import predicates as pr
from arcagi.dsl.objects import OBJECTS
from arcagi.dsl.objects_props import extract, selected

BIG = {"color": 1, "size": 4, "is_largest": 1, "h": 2}
DOT = {"color": 2, "size": 1, "is_largest": 0, "h": 1}
GROUP = [BIG, DOT]


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


S1 = grid("0000000 0110020 0110000 0000300 0000000")
S2 = grid("0000000 0300000 0001100 0001100 0201100")


def test_leaf_ops() -> None:
    assert pr.evaluate(["eq", "color", 1], BIG)
    assert pr.evaluate(["ne", "color", 1], DOT)
    assert pr.evaluate(["gt", "size", 3], BIG) and not pr.evaluate(
        ["gt", "size", 3], DOT
    )
    assert pr.evaluate(["lt", "h", 2], DOT)
    assert not pr.evaluate(["gt", "missing", 0], BIG)


def test_rank_needs_group_and_ties() -> None:
    assert pr.evaluate_group(["rank", "size", "max"], GROUP) == [True, False]
    assert pr.evaluate_group(["rank", "size", "min"], [BIG, DOT, DOT]) == [
        False,
        True,
        True,
    ]
    with pytest.raises(ValueError):
        pr.evaluate(["rank", "size", "max"], BIG)


def test_connectives_literals_and_json() -> None:
    body = [
        "and",
        ["ne", "color", 3],
        ["or", ["rank", "size", "max"], ["not", ["lt", "h", 2]]],
    ]
    assert json.loads(json.dumps(body)) == body
    assert pr.validate(body) and not pr.validate(["xor", 1]) and not pr.validate([])
    assert pr.literals(body) == 3
    assert pr.evaluate_group(body, GROUP) == [True, False]
    assert pr.evaluate(pr.from_selector("color", 2), DOT)
    assert pr.evaluate(pr.from_selector("all", 1), DOT)


def test_old_selector_shape_still_runs() -> None:
    old = [o.cells for o in selected(S1, "4same", "is_largest", 1)]
    inline = [o.cells for o in selected(S1, "4same", "pred", ["eq", "is_largest", 1])]
    assert old == inline and len(old) == 1
    assert len(selected(S1, "4same", "all", 1)) == len(extract(S1, "4same"))


def test_live_predicate_becomes_candidate(monkeypatch) -> None:
    body = ["and", ["lt", "size", 2], ["ne", "color", 3]]
    monkeypatch.setattr(pr, "LIVE", {"pred_test": body})
    states = [S1, S2]
    targets = [
        grid("0000000 0110000 0110000 0000300 0000000"),
        grid("0000000 0300000 0001100 0001100 0001100"),
    ]
    cands = OBJECTS["delete_sel"].candidates(states, targets)
    assert any(p[1:3] == ("pred", "pred_test") for p in cands)
    for p in cands:
        if p[1] == "pred":
            outs = [OBJECTS["delete_sel"].apply(s, *p) for s in states]
            assert outs == targets


def test_cli_reads_rule(tmp_path, capsys, monkeypatch) -> None:
    (tmp_path / "_rule.json").write_text(
        json.dumps({"kind": "pred", "body": ["rank", "size", "max"]})
    )
    import io

    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"object": DOT, "group": GROUP}))
    )
    assert pr.main([str(tmp_path / "_rule.json")]) == 0
    assert capsys.readouterr().out.strip() == "false"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(BIG)))
    assert pr.main([str(tmp_path / "_rule.json")]) == 0
    assert capsys.readouterr().out.strip() == "true"
