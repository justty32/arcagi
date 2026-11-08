"""Pool package: extract_* params pay dividends, budget.allocate reads epochs."""

import json
from pathlib import Path

from arcagi.blocks.catalog import load_catalog
from arcagi.blocks.pool import allocate, selected_steps, settle
from arcagi.blocks.pool.__main__ import main
from arcagi.blocks.pool.budget import MIN_CANDIDATES, latest_epoch
from arcagi.blocks.pool.ledger import DEFAULT_CONFIG

OBJRULE = '[["recolor_from","4same",["eq","color",2],"extract_abcd1234"]]'


def _blocks(root: Path) -> Path:
    for name, meta in (
        ("recolor_from", {"kind": "primitive"}),
        ("extract_abcd1234", {"kind": "extract", "generator": "_gen/extract"}),
    ):
        (root / name).mkdir(parents=True)
        meta |= {"name": name, "cost": 1, "counter_uses": 0, "status": "live"}
        (root / name / "_metainfo.json").write_text(json.dumps(meta))
    return root


def test_extract_param_is_a_reference_and_pays(tmp_path: Path) -> None:
    trace = {
        "attempts": [{"id": "a0", "kind": "program", "program": OBJRULE}],
        "selected": "a0",
    }
    assert selected_steps(trace) == ["recolor_from", "extract_abcd1234"]
    catalog = load_catalog(_blocks(tmp_path / "blocks"))
    report = {"tasks": [{"task_id": "t", "correct": True, "trace": trace}]}
    summary, _, _ = settle(report, {}, dict(DEFAULT_CONFIG), catalog)
    rows = summary["blocks"]
    assert rows["extract_abcd1234"]["refs"] == 1
    assert rows["extract_abcd1234"]["dividend"] == 400 * 0.8  # generator cut 0.2
    assert rows["_gen/extract"]["dividend"] == 80
    assert summary["conservation_ok"]
    assert summary["generator_budget"]["_gen/extract"]["share"] == 1.0


def _pool(tmp_path: Path, epochs: dict[int, dict], config: dict) -> Path:
    pool = tmp_path / "pool"
    (pool / "epochs").mkdir(parents=True)
    (pool / "config.json").write_text(json.dumps(config))
    for n, budget in epochs.items():
        row = {"epoch": n, "generator_budget": budget}
        (pool / "epochs" / f"{n}.json").write_text(json.dumps(row))
    return pool


def test_allocate_uses_newest_epoch_total_and_floors(tmp_path: Path) -> None:
    old = {"_gen/formula": {"share": 1.0}}
    new = {
        "_gen/formula": {"share": 0.7},
        "_gen/pred_combiner": {"share": 0.2},
        "_gen/extract": {"share": 0.1},  # below the 0.2 floor
    }
    pool = _pool(tmp_path, {2: old, 10: new}, {"generator_total": 1000})
    newest = latest_epoch(pool)
    assert newest is not None and newest.name == "10.json"
    got = allocate(newest)
    assert got == {"_gen/extract": 200, "_gen/formula": 700, "_gen/pred_combiner": 200}
    tiny = _pool(tmp_path / "t", {0: new}, {"generator_total": 10})
    assert set(allocate(tiny / "epochs" / "0.json").values()) == {MIN_CANDIDATES}


def test_allocate_without_budget_is_equal(tmp_path: Path) -> None:
    pool = _pool(tmp_path, {0: {}}, {"generator_total": 300})
    assert allocate(pool / "epochs" / "0.json") == {
        "_gen/extract": 100,
        "_gen/formula": 100,
        "_gen/pred_combiner": 100,
    }


def test_cli_still_runs(tmp_path: Path, capsys) -> None:
    report = tmp_path / "r.json"
    report.write_text(json.dumps({"tasks": []}))
    blocks = _blocks(tmp_path / "blocks")
    assert (
        main(
            [
                "--report",
                str(report),
                "--epoch",
                "0",
                "--split",
                "training",
                "--pool",
                str(tmp_path / "pool"),
                "--blocks",
                str(blocks),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["epoch"] == 0
