"""Meta generator: mutations, cheap score, best setting written back."""

import json
from pathlib import Path

from arcagi.blocks import gen_formula as gf
from arcagi.blocks import gen_meta as gm
from arcagi.tasks import Example, Task


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def _task(tid: str, pairs) -> Task:
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid("1")),))


TASKS = [
    _task("dbl", [("12 30", "1122 1122 3300 3300"), ("1 2 3", "11 11 22 22 33 33")]),
    _task("sum", [("11", "1 1 1"), ("11 11", "1 1 1 1"), ("1 1 1", "1 1 1 1")]),
]


def test_mutations_are_bounded_and_start_at_current() -> None:
    rows = gm.mutations({"two_layer": False})
    assert rows[0]["two_layer"] is False and len(rows) <= gm.MAX_TRIALS
    assert any(r["two_layer"] for r in rows[1:])
    assert len({json.dumps(r, sort_keys=True) for r in rows}) == len(rows)


def test_trials_pick_two_layer_and_write_back(tmp_path: Path) -> None:
    rows = gm.trials(TASKS, {"two_layer": False}, 2000, {})
    chosen = gm.best(rows)
    assert chosen["config"]["two_layer"] and chosen["explained"] == 2
    assert rows[0]["explained"] == 1
    gm.write(tmp_path, rows, chosen)
    meta = json.loads((tmp_path / gm.NODE / "_metainfo.json").read_text())
    assert meta["levels"] == 2 and len(meta["trials"]) == len(rows)
    assert (tmp_path / gm.NODE / "_entry").stat().st_mode & 0o100
    gen = json.loads((tmp_path / gf.GENERATOR / "_metainfo.json").read_text())
    assert gen["config"] == chosen["config"]
    # gen_formula keeps the config when it rewrites its node
    verdict, stats = gf.run(TASKS, config=gen["config"])
    gf.write_blocks(tmp_path, verdict, stats)
    again = json.loads((tmp_path / gf.GENERATOR / "_metainfo.json").read_text())
    assert again["config"] == chosen["config"]


def test_min_support_drops_single_task_bodies() -> None:
    verdict, _ = gf.run(TASKS, config={"min_support": 2})
    assert all(c.score >= 2 for c in verdict["live"])
