"""Predicate generator: scoring, covered / dropped verdicts, block folders, pool cut."""

import json
import subprocess
from pathlib import Path

from arcagi.blocks.catalog import load_catalog
from arcagi.blocks.gen_predicates import (
    BUILTIN,
    GENERATOR,
    Candidate,
    judge,
    score_candidates,
    segments,
    write_blocks,
)
from arcagi.blocks.pool import run_epoch, selected_steps
from arcagi.blocks.sync import sync
from arcagi.tasks import Example, Task


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def _task(tid: str) -> Task:
    """Small (size 1) non-3 objects are deleted; others stay."""
    pairs = [
        (
            "0000000 0110020 0110000 0000300 0000000",
            "0000000 0110000 0110000 0000300 0000000",
        ),
        (
            "0000000 0300000 0001100 0001100 0201100",
            "0000000 0300000 0001100 0001100 0001100",
        ),
    ]
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid(pairs[0][0])),))


def _cand(body, tasks, order) -> Candidate:
    return Candidate(body, frozenset(tasks), order)


def test_scoring_separates_tasks() -> None:
    segs = segments([_task("a"), _task("b")])
    assert segs and {s.task for s in segs} == {"a", "b"}
    cands = score_candidates(segs, 2)
    by_body = {json.dumps(c.body): c for c in cands}
    eq2 = by_body[json.dumps(["eq", "color", 2])]
    assert eq2.tasks == {"a", "b"} and eq2.score == 1.5
    both = by_body[json.dumps(["and", ["ne", "color", 3], ["lt", "size", 2]])]
    assert both.tasks == {"a", "b"} and both.score == 1.0
    assert by_body[json.dumps(["eq", "color", 1])].tasks == frozenset()


def test_judge_covered_and_zero_score() -> None:
    short = _cand(["gt", "size", 3], {"a", "b"}, 0)
    longer = _cand(["and", ["gt", "size", 3], ["ne", "color", 0]], {"a", "b"}, 5)
    eq = _cand(["eq", "color", 2], {"c", "d"}, 1)
    sub = _cand(["lt", "h", 2], {"a"}, 2)
    zero = _cand(["and", ["lt", "w", 2], ["ne", "color", 1]], {"e"}, 6)
    verdict = judge([short, longer, eq, sub, zero])
    assert [c.body for c in verdict["live"]] == [short.body]
    covered = {json.dumps(c.body): by for c, by in verdict["covered"]}
    assert covered[json.dumps(longer.body)] == short.name
    assert covered[json.dumps(eq.body)] == BUILTIN
    assert covered[json.dumps(sub.body)] == short.name
    assert zero in verdict["dropped"]


def test_write_blocks_and_entry(tmp_path: Path) -> None:
    live = _cand(
        ["and", ["eq", "is_largest", 0], ["rank", "size", "max"]], {"a", "b", "c"}, 0
    )
    stale = tmp_path / "pred_deadbeef"
    stale.mkdir()
    (stale / "_metainfo.json").write_text(
        json.dumps({"name": "pred_deadbeef", "kind": "pred"})
    )
    written = write_blocks(tmp_path, judge([live]), {"scored": 1})
    assert written == [live.name]
    catalog = load_catalog(tmp_path)
    assert catalog.blocks[live.name].kind == "pred"
    assert catalog.blocks[live.name].meta["generator"] == GENERATOR
    assert catalog.blocks["pred_deadbeef"].status == "retired"
    assert catalog.predicates() == {live.name: live.body}
    node = json.loads((tmp_path / GENERATOR / "_metainfo.json").read_text())
    assert node["kind"] == "generator"
    # sync only touches Python primitives: pred / generator folders keep their kind
    sync(tmp_path)
    assert load_catalog(tmp_path).blocks[live.name].kind == "pred"
    assert (
        json.loads((tmp_path / GENERATOR / "_metainfo.json").read_text())["kind"]
        == "generator"
    )
    rule = tmp_path / live.name / "_rule.json"
    out = subprocess.run(
        ["uv", "run", "python", "-m", "arcagi.dsl.predicates", str(rule)],
        input=json.dumps(
            {
                "object": {"size": 3, "is_largest": 0},
                "group": [{"size": 3}, {"size": 2}],
            }
        ),
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "true"


def test_pool_generator_cut_conserves(tmp_path: Path) -> None:
    blocks = tmp_path / "blocks"
    pred = "pred_0000abcd"
    for name, extra in (
        ("delete_sel", {}),
        (pred, {"kind": "pred", "generator": GENERATOR}),
    ):
        (blocks / name).mkdir(parents=True)
        meta = {"name": name, "kind": "primitive", "cost": 1, **extra}
        (blocks / name / "_metainfo.json").write_text(json.dumps(meta))
    program = json.dumps([["delete_sel", "4same", "pred", pred]])
    trace = {
        "attempts": [{"id": "a0", "kind": "program", "program": program}],
        "selected": "a0",
    }
    assert selected_steps(trace) == ["delete_sel", pred]
    report = tmp_path / "r.json"
    report.write_text(
        json.dumps({"tasks": [{"task_id": "t", "correct": True, "trace": trace}]})
    )
    summary = run_epoch(report, 0, "training", tmp_path / "pool", blocks)
    rows = summary["blocks"]
    assert summary["conservation_ok"] and summary["retained"] == 200
    assert rows["delete_sel"]["dividend"] == 400
    assert rows[pred]["dividend"] == 320 and rows[GENERATOR]["dividend"] == 80
    ledger = (tmp_path / "pool" / "ledger.jsonl").read_text()
    assert GENERATOR in ledger
