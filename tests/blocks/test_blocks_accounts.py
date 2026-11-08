"""node-pool accounts and library learning on synthetic reports and traces."""

import json
from pathlib import Path

import pytest

from arcagi.blocks.catalog import load_catalog
from arcagi.blocks.library import find_macros, fragments, task_programs
from arcagi.blocks.pool import EpochError, run_epoch


def _trace(programs: list[str], selected: int | None, near: str | None = None):
    attempts = [
        {"id": f"a{i}", "kind": "program", "program": p} for i, p in enumerate(programs)
    ]
    if near:
        attempts.append(
            {
                "id": "n",
                "kind": "near_miss",
                "program": near,
                "data": {"pixel_acc": 0.9},
            }
        )
    return {
        "attempts": attempts,
        "selected": None if selected is None else f"a{selected}",
        "metadata": {"block_calls": {"rot90": 2000}},
    }


def _report(path: Path, *tasks) -> Path:
    path.write_text(json.dumps({"tasks": list(tasks)}))
    return path


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    blocks = tmp_path / "blocks"
    for name in ("rot90", "colormap", "gravity"):
        (blocks / name).mkdir(parents=True)
        meta = {"name": name, "kind": "primitive", "cost": 1, "counter_uses": 0}
        (blocks / name / "_metainfo.json").write_text(json.dumps(meta))
    return blocks, tmp_path / "pool"


def test_pool_conservation_streak_and_gradients(tmp_path: Path) -> None:
    blocks, pool = _setup(tmp_path)
    report = _report(
        tmp_path / "r.json",
        {
            "task_id": "t1",
            "correct": True,
            "trace": _trace(['[["rot90"],["colormap",[[1,2]]]]'], 0),
        },
        {"task_id": "t2", "correct": True, "trace": _trace(['[["rot90"]]'], 0)},
        {
            "task_id": "t3",
            "correct": False,
            "trace": _trace([], None, near='[["gravity","down"]]'),
        },
    )
    summary = run_epoch(report, 0, "training", pool, blocks)
    assert summary["income"] == 2000 and summary["retained"] == 400
    assert summary["conservation_ok"]
    rows = summary["blocks"]
    assert rows["rot90"]["dividend"] == 400 + 800
    assert rows["colormap"]["dividend"] == 400
    assert rows["rot90"]["spend"] == 2 * 3  # three tasks report 2000 calls each
    assert rows["gravity"]["zero_streak"] == 1
    assert rows["gravity"]["balance"] == -100
    letters = (blocks / "gravity" / "_gradients.jsonl").read_text().splitlines()
    assert json.loads(letters[0])["task"] == "t3"
    assert load_catalog(blocks).blocks["rot90"].meta["counter_uses"] == 2
    # same report again is a no-op; a different report for the same epoch fails
    assert run_epoch(report, 0, "training", pool, blocks)["income"] == 2000
    assert len((pool / "ledger.jsonl").read_text().splitlines()) == 4
    other = _report(tmp_path / "o.json")
    with pytest.raises(EpochError):
        run_epoch(other, 0, "training", pool, blocks)
    with pytest.raises(EpochError):
        run_epoch(other, 2, "training", pool, blocks)
    for epoch in (1, 2):
        summary = run_epoch(other, epoch, "training", pool, blocks)
    assert summary["blocks"]["gravity"]["zero_streak"] == 3
    assert "gravity" in summary["suggest_retire"]
    assert "rot90" not in summary["suggest_retire"]
    wallets = json.loads((pool / "wallets.json").read_text())
    assert wallets["top"]["balance"] == 400
    assert wallets["blocks"]["rot90"]["balance"] == 1200 - 6 - 300


def _record(task_id: str, *programs: str) -> dict:
    return {"task_id": task_id, "trace": _trace(list(programs), 0)}


def test_fragments_skip_learners() -> None:
    program = (("rot90",), ("upscale", 2, 2), ("colormap", ((1, 2),)))
    assert fragments(program) == {(("rot90",), ("upscale", 2, 2))}


def test_library_threshold_and_covered() -> None:
    frag = '["crop_bbox"],["upscale",2,2]'
    records = [
        _record("t1", f"[{frag}]"),
        _record("t2", f'[["rot90"],{frag}]'),
        # t3 also has a cheaper program without the fragment
        _record("t3", f'[{frag},["flip_lr"]]', '[["transpose"]]'),
        _record("t4", '[["rot90"],["flip_lr"]]'),
    ]
    programs = task_programs(records)
    macros = find_macros(programs, min_tasks=3)
    assert [m.fragment for m in macros] == [(("crop_bbox",), ("upscale", 2, 2))]
    assert macros[0].tasks == ("t1", "t2", "t3") and macros[0].status == "live"
    covered = task_programs(
        [_record(t, f'[{frag},["flip_lr"]]', '[["transpose"]]') for t in "abc"]
    )
    assert find_macros(covered, min_tasks=3)[0].status == "covered"
