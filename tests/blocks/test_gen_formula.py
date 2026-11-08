"""Formula generator: problems, scoring, verdicts, block folders, catalog hook."""

import json
import subprocess
from pathlib import Path

from arcagi.blocks.catalog import load_catalog
from arcagi.blocks.gen_formula import (
    GENERATOR,
    Candidate,
    judge,
    problems,
    run,
    score_candidates,
    write_blocks,
)
from arcagi.tasks import Example, Task


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def _double(tid: str) -> Task:
    """Output = input upscaled 2x; input heights vary so h_out = 2*h."""
    pairs = [("12 30", "1122 1122 3300 3300"), ("1 2 3", "11 11 22 22 33 33")]
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid("12")),))


def _constant(tid: str) -> Task:
    pairs = [("12 30", "5"), ("123", "6")]
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid("1")),))


def test_problems_skip_constant_targets() -> None:
    probs = problems([_double("a"), _constant("c")])
    assert {(p.task, p.target) for p in probs} == {("a", "h_out"), ("a", "w_out")}


def test_scoring_and_judge() -> None:
    cands = score_candidates(problems([_double("a"), _double("b"), _constant("c")]))
    by_body = {json.dumps(c.body): c for c in cands}
    lin = by_body[json.dumps(["lin", "h", 2, 0])]
    assert lin.tasks == {"a", "b"} and lin.score == 2 and "h_out" in lin.targets
    verdict = judge(cands)
    live = [c.body for c in verdict["live"]]
    assert all(c.score > 0 for c in verdict["live"])
    assert all(c.score == 0 for c in verdict["dropped"])
    # Nothing in live has a support explained by simpler live bodies.
    assert len(live) == len({json.dumps(b) for b in live})
    covered_names = {by for _c, by in verdict["covered"]}
    assert covered_names <= {c.name for c in verdict["live"]}


def test_judge_same_support_keeps_shortest() -> None:
    short = Candidate(["lin", "h", 2, 0], 0, {"a", "b"}, {"h_out"})
    longer = Candidate(["lin", "h", 2, 1], 1, {"a", "b"}, {"h_out"})
    extra = Candidate(["mul", "h", "w"], 2, {"a"}, {"h_out"})
    zero = Candidate(["sq", "h"], 3)
    verdict = judge([short, longer, extra, zero])
    assert [c.body for c in verdict["live"]] == [short.body]
    assert {(c.name, by) for c, by in verdict["covered"]} == {
        (longer.name, short.name),
        (extra.name, short.name),
    }
    assert verdict["dropped"] == [zero]


def test_write_blocks_and_catalog(tmp_path: Path) -> None:
    verdict, stats = run([_double("a"), _double("b")])
    stale = tmp_path / "formula_deadbeef"
    stale.mkdir()
    (stale / "_metainfo.json").write_text(
        '{"name": "formula_deadbeef", "kind": "formula"}'
    )
    written = write_blocks(tmp_path, verdict, stats)
    assert written
    meta = json.loads((tmp_path / written[0] / "_metainfo.json").read_text())
    assert meta["kind"] == "formula" and meta["generator"] == GENERATOR
    assert meta["status"] == "live" and meta["support_tasks"] == ["a", "b"]
    rule = json.loads((tmp_path / written[0] / "_rule.json").read_text())
    assert rule["kind"] == "formula" and rule["in"] == "features"
    node = json.loads((tmp_path / GENERATOR / "_metainfo.json").read_text())
    assert node["kind"] == "generator" and "gen_seconds" in node
    assert (tmp_path / GENERATOR / "_entry").stat().st_mode & 0o100
    assert json.loads((stale / "_metainfo.json").read_text())["status"] == "retired"
    rules = load_catalog(tmp_path).rules("formula")
    assert set(rules) == {c.name for c in verdict["live"]}


def test_block_entry_cli(tmp_path: Path) -> None:
    verdict, stats = run([_double("a"), _double("b")])
    write_blocks(tmp_path, verdict, stats)
    name = verdict["live"][0].name
    out = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "arcagi.dsl.formula",
            str(tmp_path / name / "_rule.json"),
        ],
        input="[[1,2],[3,0]]",
        capture_output=True,
        text=True,
        check=True,
    )
    assert verdict["live"][0].body == ["lin", "h", 2, 0]
    assert int(out.stdout) == 4


def _sum(tid: str) -> Task:
    """h_out = h + w (no one-layer body: needs the two-layer ``lin2``)."""
    pairs = [("11", "1 1 1"), ("11 11", "1 1 1 1"), ("1 1 1", "1 1 1 1")]
    pairs += [("1111 1111", "1 1 1 1 1 1")]
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid("1")),))


def test_two_layer_only_on_unfit_problems_and_budget() -> None:
    verdict, stats = run([_double("a"), _sum("s")], budget=5000)
    assert stats["two_layer"] > 0 and stats["unfit_problems"] == 1
    assert stats["one_layer"] + stats["two_layer"] <= 5000
    live = {json.dumps(c.body): c for c in verdict["live"]}
    two = [c for c in live.values() if c.body[0] in ("lin2", "mulc")]
    assert two and all(c.tasks == {"s"} for c in two)
    assert json.dumps(["lin2", "h", 1, "w", 1]) in live
    _, small = run([_double("a"), _sum("s")], budget=100)
    assert small["one_layer"] + small["two_layer"] == 100


def test_extract_features_reach_the_rule(tmp_path: Path) -> None:
    # w_out = size of the largest object (an extract feature), not a base one.
    pairs = [("100 022 000", "11"), ("333 000 000", "111"), ("100 000 000", "1")]
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    task = Task("x", train, (Example(grid("1")),))
    ext = {"extract_aaaa0001": ["size", ["largest", "4same"]]}
    verdict, stats = run([task], extracts=ext)
    assert stats["extracts"] == 1
    # max_obj_size says the same, so the extract body is covered by it.
    kept = verdict["live"] + [c for c, _ in verdict["covered"]]
    hit = [c for c in kept if c.body == ["lin", "extract_aaaa0001", 1, 0]]
    assert hit and hit[0].extracts == ext
    write_blocks(tmp_path, verdict, stats)
    rule = json.loads((tmp_path / hit[0].name / "_rule.json").read_text())
    assert rule["extracts"] == ext
