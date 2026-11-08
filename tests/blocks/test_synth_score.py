"""Synthetic majority check, extract meta settings, meta ledger, scratch pool."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from arcagi.blocks import gen_formula as gf
from arcagi.blocks import gen_meta as gm
from arcagi.blocks import synth_score as ss
from arcagi.blocks.meta import ledger
from arcagi.blocks.pool import budget
from arcagi.tasks import Example, Task


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def _task(tid: str, pairs) -> Task:
    train = tuple(Example(grid(a), grid(b)) for a, b in pairs)
    return Task(tid, train, (Example(grid("1")),))


# Output height = 2 x input height.
DBL = _task("dbl", [("1 2", "1 1 2 2"), ("1", "1 1"), ("1 2 3", "1 1 1 2 2 2")])
# Synthetic resample where the rule breaks (output height constant 1).
BROKEN = _task("dbl", [("1 2", "11"), ("1", "1"), ("1 2 3", "111")])


@dataclass
class Fake:
    name: str
    tasks: set


def test_apply_majority_narrows_but_spares_protected() -> None:
    cands = [Fake("a", {"t1", "t2"}), Fake("b", {"t1"}), Fake("c", {"t2"})]
    rates = {"a": {"t1": 0.75, "t2": 0.25}, "b": {"t1": 0.0}, "c": {"t2": 0.5}}
    out = ss.apply_majority(cands, rates, protected=["b"])
    assert cands[0].tasks == {"t1"} and cands[2].tasks == {"t2"}
    assert cands[1].tasks == {"t1"} and cands[1].synth_protected
    assert out == {"claims": 4, "failed": 2, "protected": ["b"]}
    assert ss.fail_rate(cands) == 0.5
    assert ss.meta_fields(cands[1])["synth_protected"] is True


def test_apply_majority_measure_only() -> None:
    cands = [Fake("a", {"t1", "t2"})]
    ss.apply_majority(cands, {"a": {"t1": 1.0, "t2": 0.0}}, [], narrow=False)
    assert cands[0].tasks == {"t1", "t2"} and cands[0].synth_tasks == {"t1"}


def test_formula_threshold_keeps_true_rules_and_drops_memorised() -> None:
    good = ss.Views([{"dbl": DBL}] * ss.CHUNKS)
    bad = ss.Views([{"dbl": BROKEN}] * ss.CHUNKS)
    verdict, stats = gf.run([DBL], synth=good)
    assert verdict["live"] and stats["synth"]["failed"] == 0
    assert all(c.synth_rate == 1.0 for c in verdict["live"])
    body = verdict["live"][0].body
    assert ss.pass_rates("formula", body, ["dbl"], good) == {"dbl": 1.0}
    assert ss.pass_rates("formula", body, ["dbl"], bad) == {"dbl": 0.0}
    verdict, stats = gf.run([DBL], synth=bad)
    assert not verdict["live"] and stats["synth"]["failed"] > 0


def test_load_missing_root_is_none(tmp_path: Path) -> None:
    assert ss.load(tmp_path) is None


def test_extract_mutations_bounded_unique() -> None:
    rows = gm.extract_mutations({})
    assert rows[0]["object_scope"] is True and len(rows) <= gm.MAX_TRIALS
    assert len({json.dumps(r, sort_keys=True) for r in rows}) == len(rows)


def test_meta_ledger_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCAGI_META", str(tmp_path))
    (tmp_path / "b" / "x").mkdir(parents=True)
    h = ledger.blocks_root_hash(tmp_path / "b")
    ledger.append({"run_id": "r", "score_main": 1.5, "blocks_root_hash": h})
    row = json.loads((tmp_path / "ledger.jsonl").read_text())
    assert set(ledger.FIELDS) <= set(row) and row["score_main"] == 1.5
    assert row["time"] and row["base_commit"]


def test_pool_root_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCAGI_POOL", str(tmp_path))
    assert budget.pool_root() == tmp_path and budget.latest_epoch() is None
    assert budget.income() == {}


def test_paired_task_wins() -> None:
    from arcagi.blocks.meta import library

    a = {"per_task": {"x": {"net": 1}, "y": {"net": -1}, "z": {"net": 0}}}
    b = {"per_task": {"x": {"net": 0}, "y": {"net": 0}, "z": {"net": 0}}}
    assert library.paired(a, b) == {"wins": 1, "losses": 1, "net": 0}
