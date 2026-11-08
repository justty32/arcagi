"""Extract generator: scoring, covered / dropped verdicts, block folders."""

import json

from arcagi.blocks.catalog import load_catalog
from arcagi.blocks.gen_extract import (
    GENERATOR,
    Candidate,
    judge,
    score_candidates,
    selectors,
    write_blocks,
)
from arcagi.tasks import Example, Task


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def _crop_task(tid: str) -> Task:
    """Output = the largest object's crop."""
    pairs = [
        ("00000 01100 01100 00003", "11 11"),
        ("00000 02220 00000 30000", "222"),
    ]
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid(pairs[0][0])),))


def _count_task(tid: str) -> Task:
    """Output width = number of objects."""
    pairs = [("10101 00000", "444"), ("10001 00000", "44"), ("00100 00000", "4")]
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid(pairs[0][0])),))


def test_scoring() -> None:
    cands = score_candidates(
        [_crop_task("a"), _crop_task("b"), _count_task("c")], selectors([])
    )
    by = {json.dumps(c.body): c for c in cands}
    assert by[json.dumps(["subgrid", ["largest", "4same"]])].tasks == {"a", "b"}
    assert by[json.dumps(["count", ["all", "4same"]])].tasks == {"c"}
    assert by[json.dumps(["color", ["smallest", "4same"]])].tasks == frozenset()


def test_judge_and_write(tmp_path) -> None:
    short = Candidate(["subgrid", ["largest", "4same"]], frozenset("ab"), 0)
    same = Candidate(["subgrid", ["pred", "4same", "pred_x"]], frozenset("ab"), 1)
    sub = Candidate(["object", ["largest", "4same"]], frozenset("a"), 2)
    zero = Candidate(["size", ["all", "4same"]], frozenset(), 3)
    verdict = judge([short, same, sub, zero])
    assert verdict["live"] == [short]
    assert {c.name for c, _ in verdict["covered"]} == {same.name, sub.name}
    assert verdict["dropped"] == [zero]
    (tmp_path / "extract_old").mkdir()
    (tmp_path / "extract_old" / "_metainfo.json").write_text('{"kind": "extract"}')
    write_blocks(tmp_path, verdict, {"gen_seconds": 1.5})
    meta = json.loads((tmp_path / short.name / "_metainfo.json").read_text())
    assert meta["kind"] == "extract" and meta["generator"] == GENERATOR
    assert meta["support_tasks"] == ["a", "b"] and meta["status"] == "live"
    cov = json.loads((tmp_path / same.name / "_metainfo.json").read_text())
    assert cov["status"] == "covered" and cov["covered_by"] == short.name
    rule = json.loads((tmp_path / short.name / "_rule.json").read_text())
    assert rule == {"kind": "extract", "in": "grid", "out": "json", "body": short.body}
    node = json.loads((tmp_path / GENERATOR / "_metainfo.json").read_text())
    assert node["gen_seconds"] == 1.5 and (tmp_path / GENERATOR / "_entry").exists()
    old = json.loads((tmp_path / "extract_old" / "_metainfo.json").read_text())
    assert old["status"] == "retired"
    assert list(load_catalog(tmp_path).rules("extract")) == [short.name]
