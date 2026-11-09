"""Block-3 open costs, epoch-local credit, health and adversarial acceptance."""

import copy
import math

import pytest

from arcagi.hammer import formats as fm
from arcagi.treegen import boundary, cost, credit, health, ledger
from arcagi.treegen.cli import main


@pytest.mark.parametrize(
    "bad",
    [
        {"wall_s": "abc"},
        {"wall_s": -1},
        {"wall_s": True},
        {"wall_s": None},
        {"wall_s": math.inf},
        {"wall_s": math.nan},
        {"wall_s": 10**400},
        {"evals": 1, "evals.body": 2},
        {"a": 0, "a.b.c": 1},
        {"Wall_s": 1},
        {".gpu": 1},
        {"a..b": 1},
        {"a-b": 1},
        {1: 2},
        [],
    ],
)
def test_validate_rejects_bad_dimensions(bad):
    assert cost.validate(bad)


def test_price_rollup_and_segment_prefixes():
    values = {
        "evals.body": 2,
        "evals.shadow": 3,
        "evals2.body": 9,
        "agent.ideas.tokens": 7,
        "gpu.sec": 4,
        "wall_s": 0,
    }
    rates = {"evals.body": 1, "evals.shadow": 2, "evals2.body": 100, "gpu.sec": 0.5}
    original = copy.deepcopy(values)
    assert cost.validate(values) == []
    assert cost.price(values, rates) == 910
    assert cost.price(values, rates, ["evals"]) == 8
    assert cost.price(values, rates, ["evals.body"]) == 2
    assert cost.price(values, rates, ["evals", "evals.body"]) == 8
    assert cost.price(values, rates, []) == 0
    assert cost.price({"new.cost": 15}, rates) == 0
    assert cost.rollup(values, 1) == {
        "evals": 5,
        "evals2": 9,
        "agent": 7,
        "gpu": 4,
        "wall_s": 0,
    }
    assert cost.rollup(values, 2)["agent.ideas"] == 7
    assert cost.rollup(values, 10) == values == original
    assert cost.validate({"evals": 1, "evals.body": 2}, rates=True) == []
    assert cost.validate({"gpu.sec": True}, rates=True)
    with pytest.raises(ValueError):
        cost.price(values, {"gpu.sec": -1})
    for depth in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="depth"):
            cost.rollup(values, depth)


@pytest.fixture
def tree(tmp_path):
    taskset = tmp_path / "taskset.json"
    fm.write_json(
        taskset,
        {
            "learn": ["old", "a", "b", "plain"],
            "P48": [],
            "holdout": ["h8"],
            "holdout24": ["h24"],
        },
    )
    root = fm.init_root(tmp_path / "source", taskset)
    ops = [
        fm.new_op(
            "comb_alpha",
            "comb",
            {"name": "alpha", "body": []},
            "user",
            0,
            status="dormant",
        ),
        fm.new_op(
            "comb_beta", "comb", {"name": "beta", "body": []}, "user", 2, status="live"
        ),
        fm.new_op(
            "comb_ghost",
            "comb",
            {"name": "ghost", "body": []},
            "user",
            0,
            status="live",
        ),
        fm.new_op(
            "decomp_late", "decomp", {"name": "halves"}, "user", 3, status="live"
        ),
        fm.new_op(
            "decomp_dead", "decomp", {"name": "nest"}, "user", 0, status="dormant"
        ),
        fm.new_op("gate_g1", "gate", {}, "user", 0, status="live"),
        fm.new_op("route_early", "route", {}, "user", 0, status="live"),
        fm.new_op("route_late", "route", {}, "user", 4, status="live"),
    ]
    # Deliberately conflicting terminal evidence must never grant epoch credit.
    for op in ops:
        op["evidence"]["new_solves"] = ["invented_terminal_task"]
        op["blamed_by"] = "terminal_blame"
    fm.write_ops(root, ops)
    for index, name in enumerate(fm.NODES, 1):
        path = root / "nodes" / name / "_metainfo.json"
        fm.write_json(path, {**fm.read_json(path), "weight": index})
    for epoch in ledger.EPOCHS:
        ed = root / "epochs" / str(epoch)
        row = {
            "epoch": epoch,
            "solved_L": 4 if epoch else 1,
            "solved_P": 0,
            "solved_H8": 0,
            "solved_H24": 0,
            "logcost_L": 10 - epoch,
            "evals_body": 10_000_000 if epoch == 4 else 100_000,
            "evals_shadow": 1000,
            "evals_meta": 2000,
            "evals_foundry": 3000,
            "llm_calls": 2,
            "wall_s": 0.5,
            "stall": "ok",
            "arm": "rt_sleep",
            "lib_size": 2 if epoch else 0,
            "lib_bits": 10,
        }
        fm.write_json(ed / "status.json", row)
        fm.write_text(
            ed / "curve.csv",
            ",".join(row)
            + "\n"
            + ",".join(str(value) for value in row.values())
            + "\n",
        )
        blocks = [{"name": "alpha"}, {"name": "beta"}] if epoch else []
        fm.write_json(ed / "blocks.json", blocks)
        fm.write_json(ed / "shadow_blocks.json", [{"name": "ghost"}])
        fm.write_jsonl(
            ed / "solutions.jsonl",
            [
                {
                    "task_id": task,
                    "set": "L16",
                    "train_ok": task == "old" or epoch > 0,
                    "program": program,
                }
                for task, program in (
                    ("old", ["blk", "alpha"]),
                    ("a", ["pair", ["blk", "alpha"], {"nested": ["blk", "alpha"]}]),
                    ("b", ["pair", ["blk", "alpha"], ["blk", "beta"]]),
                    ("plain", ["$in"]),
                )
            ]
            + [
                {
                    "task_id": "p",
                    "set": "P",
                    "train_ok": True,
                    "program": ["blk", "ghost"],
                }
            ],
        )
    return root


@pytest.fixture
def built(tree, tmp_path, monkeypatch):
    # The real acceptance invokes pytest; nested acceptance tests isolate only
    # that subprocess, avoiding recursive suites. C7 itself is checked below.
    monkeypatch.setattr(
        ledger,
        "_regression",
        lambda: {
            "pass": True,
            "pytest_exit": 0,
            "tests_passed": 1,
            "guard_missing": 0,
            "errors": [],
        },
    )
    rates = tmp_path / "rates.json"
    fm.write_json(rates, cost.LEGACY_RATES)
    out = tmp_path / "ledger"
    ledger.generate(tree, out, rates)
    return out


def test_epoch_local_attribution_live_status_and_missing_blk(tree):
    audit = health.load_script("think1_audit")
    attributed, unassigned = credit.new_solves(tree, 1, audit.block_refs)
    assert attributed == {"comb_alpha": ["a", "b"], "comb_beta": ["b"]}
    assert unassigned == ["plain"]
    assert credit.new_solves(tree, 2, audit.block_refs) == ({}, [])
    first = credit.live_ops(tree, 1)
    assert first["solve"] == ["comb_alpha", "comb_beta"]
    assert credit.live_ops(tree, 3)["solve"] == [
        "comb_alpha",
        "comb_beta",
        "decomp_late",
    ]
    assert credit.live_ops(tree, 3)["route"] == ["route_early"]
    assert credit.live_ops(tree, 4)["route"] == ["route_early", "route_late"]


@pytest.mark.parametrize("amount", [37.25, -37.25, 0.0])
def test_two_layers_conserve_base_star_and_empty_nodes(amount):
    weights = {"solve": 1, "gate": 1, "route": 2, "grow": 0}
    rows = credit.allocate(
        1,
        amount,
        weights,
        {"solve": ["a", "b", "c"], "gate": [], "route": ["r", "s"]},
        {"a": ["new1", "new2"], "b": ["new3"]},
    )
    first = [row for row in rows if row["layer"] == 1]
    assert sum(row["amount"] for row in first) == pytest.approx(amount, abs=1e-14)
    assert first[0]["amount"] == pytest.approx(0.2 * amount)
    for node in ("solve", "gate", "route"):
        total = next(row["amount"] for row in first if row["to"] == f"nodes/{node}")
        second = [row for row in rows if row["from"] == f"nodes/{node}"]
        assert sum(row["amount"] for row in second) == pytest.approx(total, abs=1e-14)
        if node == "gate":
            assert len(second) == 1 and second[0]["to"] == "keep"
        else:
            assert second[0]["amount"] == pytest.approx(0.2 * total)
        if node == "solve":
            base = [row["amount"] for row in second if row["why"]["share"] == "base"]
            star = [row["amount"] for row in second if row["why"]["share"] == "star"]
            assert base == pytest.approx([0.1 * total / 3] * 3)
            assert star == pytest.approx([0.7 * total * 2 / 3, 0.7 * total / 3, 0])
        if node == "route":
            assert [row["amount"] for row in second[1:]] == pytest.approx(
                [0.05 * total] * 2 + [0.35 * total] * 2
            )


def test_real_modules_synthetic_tree_and_cli(tree, built, tmp_path, capsys):
    report = ledger.check(built, tree, tmp_path / "accept.json")
    assert report["pass"] and all(c["pass"] for c in report["checks"].values())
    assert set(report["checks"]) == {f"C{n}" for n in range(1, 8)}
    assert report["checks"]["C1"]["files_differ"] == 0
    assert report["checks"]["C3"]["coverage"] == 1
    assert report["checks"]["C4"]["delta_cost"] == 0
    assert abs(report["checks"]["C4"]["delta_eff"]) <= 1e-4
    meta = fm.read_json(built / "ledger_meta.json")
    assert meta["amounts"]["4"] < 0
    assert "invented_terminal_task" not in str(meta["attribution"])
    assert not any(
        "llm.tokens" in row["cost"] for row in fm.read_jsonl(built / "cost.jsonl")
    )
    totals = fm.read_json(built / "by_subtree.json")
    assert sum(totals.values()) == pytest.approx(0.8 * sum(meta["amounts"].values()))
    card = fm.read_json(built / "health.json")
    assert set(card["nodes"]) == set(fm.NODES)
    assert card["nodes"]["solve"]["n_ops"] == 5
    assert card["nodes"]["grow"] == {
        "ok": True,
        "verdicts": {},
        "n_ops": 0,
        "note": "no ops",
    }
    assert main(["ledger-check", str(built), "--tree", str(tree)]) == 0
    output = tmp_path / "cli-ledger"
    assert (
        main(
            [
                "ledger",
                str(tree),
                "--out",
                str(output),
                "--rates",
                str(built.parent / "rates.json"),
            ]
        )
        == 0
    )
    capsys.readouterr()


def test_open_extension_roundtrip(tree, built):
    rows = fm.read_jsonl(built / "cost.jsonl")
    rows[0]["cost"].update({"gpu.sec": 2, "agent.ideas.tokens": 7})
    fm.write_jsonl(built / "cost.jsonl", rows)
    meta = fm.read_json(built / "ledger_meta.json")
    meta["rates"]["gpu.sec"] = 3
    fm.write_json(built / "ledger_meta.json", meta)
    assert ledger.check(built, tree)["pass"]
    assert cost.price(rows[0]["cost"], meta["rates"]) == meta["prices"]["0"] + 6


@pytest.mark.parametrize(
    "case,check_id",
    [
        ("source", "C1"),
        ("amount_l1", "C2"),
        ("amount_l2", "C2"),
        ("drop_op", "C3"),
        ("drop_shadow", "C4"),
        ("root_amount", "C4"),
        ("string", "C5"),
        ("negative", "C5"),
        ("ancestor", "C5"),
        ("drop_node", "C6"),
        ("bad_counts", "C6"),
        ("bad_ok", "C6"),
        ("regression", "C7"),
    ],
)
def test_every_forgery_is_rejected(tree, built, monkeypatch, capsys, case, check_id):
    if case == "source":
        fm.write_text(tree / "nodes/solve/_witness.jsonl", '{"changed":true}\n')
    elif case in ("amount_l1", "amount_l2", "root_amount", "drop_op"):
        rows = fm.read_jsonl(built / "credit.jsonl")
        if case == "drop_op":
            op = next(row["to"] for row in rows if row["to"].startswith("ops/"))
            rows = [row for row in rows if not (row["epoch"] == 1 and row["to"] == op)]
        else:
            layer = 2 if case == "amount_l2" else 1
            next(row for row in rows if row["layer"] == layer)["amount"] += 0.01
        fm.write_jsonl(built / "credit.jsonl", rows)
    elif case in ("drop_shadow", "string", "negative", "ancestor"):
        rows = fm.read_jsonl(built / "cost.jsonl")
        values = rows[0]["cost"]
        if case == "drop_shadow":
            del values["evals.shadow"]
        else:
            values.update(
                {"wall_s": "abc"}
                if case == "string"
                else {"wall_s": -1}
                if case == "negative"
                else {"evals": 1}
            )
        fm.write_jsonl(built / "cost.jsonl", rows)
    elif case in ("drop_node", "bad_counts", "bad_ok"):
        card = fm.read_json(built / "health.json")
        if case == "drop_node":
            del card["nodes"]["solve"]
        elif case == "bad_counts":
            card["nodes"]["solve"]["n_ops"] += 1
        else:
            card["nodes"]["solve"]["ok"] = not card["nodes"]["solve"]["ok"]
        fm.write_json(built / "health.json", card)
    else:
        monkeypatch.setattr(
            ledger,
            "_regression",
            lambda: {
                "pass": False,
                "pytest_exit": 1,
                "errors": ["pytest FAIL injected"],
            },
        )
    report = ledger.check(built, tree)
    assert not report["pass"] and not report["checks"][check_id]["pass"]
    assert main(["ledger-check", str(built), "--tree", str(tree)]) == 1
    stderr = capsys.readouterr().err
    assert f"{check_id} FAIL" in stderr
    if case.startswith("amount_l"):
        assert "epoch=1" in stderr and f"layer={layer}" in stderr


def test_safety_stop_nonempty_output_and_source_overlap(
    tree, built, tmp_path, monkeypatch
):
    rates = built.parent / "rates.json"
    with pytest.raises(ValueError, match="empty"):
        ledger.generate(tree, built, rates)
    for dest in (tree, tree / "ledger", tree.parent):
        with pytest.raises(ValueError, match="overlap"):
            ledger.generate(tree, dest, rates)
    link = tmp_path / "link"
    link.symlink_to(tree, target_is_directory=True)
    with pytest.raises(ValueError, match="overlap"):
        ledger.generate(tree, link / "ledger", rates)
    with pytest.raises(ValueError, match="overlap"):
        ledger.check(built, tree, tree / "accept.json")
    fm.write_json(built / "by_subtree.json", {})
    assert not ledger.check(built, tree)["checks"]["C2"]["pass"]

    def stopped():
        raise RuntimeError("STOP")

    monkeypatch.setattr(boundary, "check_stop", stopped)
    with pytest.raises(RuntimeError, match="STOP"):
        ledger.generate(tree, tmp_path / "stopped", rates)
    assert not (tmp_path / "stopped").exists()


@pytest.mark.parametrize(
    "pytest_exit,guard_status", [(0, "PASS"), (1, "PASS"), (0, "FAIL")]
)
def test_regression_checks_actual_process_and_guard_results(
    monkeypatch, pytest_exit, guard_status
):
    class Process:
        returncode = pytest_exit

        def communicate(self, timeout=None):
            return "3 passed in 0.01s" if not pytest_exit else "1 failed", None

        def poll(self):
            return self.returncode

    monkeypatch.setattr(ledger.subprocess, "Popen", lambda *a, **kw: Process())
    monkeypatch.setattr(
        ledger.guards,
        "thresholds",
        lambda: {
            "status": guard_status,
            "unregistered": [] if guard_status == "PASS" else [{}],
        },
    )
    result = ledger._regression()
    assert result["pass"] == (pytest_exit == 0 and guard_status == "PASS")
    assert result["tests_passed"] == (3 if not pytest_exit else 0)
