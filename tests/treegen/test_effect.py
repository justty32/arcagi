"""Mutation-to-hammer round trips and the GA's measurement track."""

import copy
import json
import time

import pytest

from arcagi.hammer import formats as fm
from arcagi.hammer.route import pick_arm
from arcagi.seed.types import INPUT, show
from arcagi.treegen import bounds, check, effect, genome, meter, mutate, quick
from arcagi.treegen.export import export_tree

DEAD_TARGETS = []


@pytest.fixture
def parent(tmp_path, monkeypatch):
    monkeypatch.setattr(genome, "SCRATCH", tmp_path / "checks")
    monkeypatch.setattr(effect, "SCRATCH", tmp_path / "probes")
    taskset = tmp_path / "tasks.json"
    fm.write_json(
        taskset,
        {
            "learn": list(effect.FIXTURE_TASKS),
            "P48": [],
            "holdout": [],
            "holdout24": [],
        },
    )
    root = fm.init_root(tmp_path / "source", taskset)
    ops = fm.load_ops(root)
    for name, status in (("alpha", "live"), ("beta", "dormant"), ("gamma", "live")):
        ops.append(
            fm.new_op(
                f"comb_{name}",
                "comb",
                {"name": name, "body": ["$in"]},
                "user",
                0,
                sig=show(INPUT),
                status=status,
            )
        )
    fm.write_ops(root, ops)
    doc = export_tree(root, tmp_path / "export")
    return doc


def edit_op(doc, oid, operator):
    tree = genome.expanded(doc)
    op = next(o for o in tree["ops.jsonl"] if o["id"] == oid)
    if operator == "M2":
        op["status"] = "dormant" if op["status"] == "live" else "live"
    else:
        tree["ops.jsonl"].remove(op)
    return genome.pack(doc, tree)


def test_round_trip_every_candidate(parent, tmp_path):
    """Every route candidate must witness a change; report dead M1 draws."""
    original = copy.deepcopy(parent)
    options = mutate.candidates(genome.expanded(parent))
    assert options["M5"] == []
    assert not any(
        t[0].startswith("nodes/") for t in bounds.targets(genome.expanded(parent))
    )
    for operator in ("M2", "M3"):
        ids = {o["id"] for o in options[operator]}
        assert "route_starve_rt_sleep" not in ids
        assert "route_ok_rt_sleep" in ids
    dead, timings = [], []
    limits = fm.read_json(bounds.BOUNDS)["limits"]
    for operator in ("M1", "M2", "M3"):
        for target in options[operator]:
            tree = genome.expanded(parent)
            if operator == "M1":
                path, container, key, _, name = next(
                    t for t in bounds.targets(tree) if t[0] == target[0]
                )
                value, rule = container[key], limits[name]
                proposed = value + 2 if type(value) is int else value * 1.2
                if proposed > rule["max"]:
                    proposed = value - 2 if type(value) is int else value * 0.8
                container[key] = max(rule["min"], min(rule["max"], proposed))
                assert container[key] != value
                child = genome.pack(parent, tree)
            else:
                path = f"ops/{target['id']}"
                child = edit_op(parent, target["id"], operator)
            result = effect.probe(parent, child)
            timings.append(result["wall_s"])
            if operator in ("M2", "M3") and target["kind"] == "route":
                assert result["changed"], (operator, path, result)
            if operator == "M1" and not result["changed"]:
                dead.append(path)
    DEAD_TARGETS[:] = sorted(dead)
    print("DEAD_TARGETS=" + json.dumps(DEAD_TARGETS))
    print(f"PROBE_MAX_S={max(timings):.6f}")
    fm.write_json(
        tmp_path / "roundtrip.json", {"DEAD_TARGETS": DEAD_TARGETS, "wall_s": timings}
    )
    assert max(timings) < 30
    assert parent == original


@pytest.mark.parametrize("operator", ["M2", "M3"])
def test_handmade_masked_route_has_no_effect(parent, operator):
    child = edit_op(parent, "route_starve_rt_sleep", operator)
    result = effect.probe(parent, child)
    assert result["changed"] == [] and result["detail"] == {}
    assert result["fixture"]["ran_epoch"]


def test_node_weight_is_not_a_bound_or_a_behavior(parent):
    tree = genome.expanded(parent)
    tree["nodes"]["grow"]["_metainfo.json"]["weight"] = 1000
    child = genome.pack(parent, tree)
    assert not bounds.validate(tree)
    # Hammer's check_metainfo only requires the weight field to exist.
    assert check.check(child, parent)["ok"]
    assert effect.probe(parent, child)["changed"] == []


def test_effective_arms_matches_pick_arm_and_collapses_noops(parent):
    tree = genome.expanded(parent)
    ops = tree["ops.jsonl"]
    arms = effect.effective_arms(ops)
    assert arms == {
        "ok": "NOOP",
        "starve": "rt_pool",
        "saturate": "rt_vsplit",
        "stop": "rt_vsplit",
    }
    for status, arm in arms.items():
        picked = pick_arm(ops, status)
        assert arm == ("NOOP" if picked in effect.NOOP_ARMS else picked)
    assert effect.effective_arms([]) == dict.fromkeys(fm.STALL_STATES, "NOOP")
    # Equal priority uses op id, and a NOOP winner may hide a real fallback.
    for op in ops:
        if op["kind"] == "route":
            op["payload"]["priority"] = 1
    assert effect.effective_arms(ops)["saturate"] == "NOOP"
    options = mutate.candidates(tree)
    assert "route_saturate_rt_gatescan" in {o["id"] for o in options["M2"]}


@pytest.mark.parametrize("status", ["live", "dormant"])
def test_only_noop_fallbacks_and_masked_dormant_routes_are_excluded(parent, status):
    tree = genome.expanded(parent)
    ops = tree["ops.jsonl"]
    for op in ops:
        if op["kind"] == "route":
            if op["payload"]["when_stall"] == "ok":
                op["payload"]["arm"] = "rt_gatescan"
            if op["id"] == "route_starve_rt_sleep":
                op["status"] = status
    options = mutate.candidates(tree)
    for operator in ("M2", "M3"):
        ids = {op["id"] for op in options[operator]}
        assert "route_starve_rt_sleep" not in ids
        assert "route_ok_rt_sleep" not in ids


def test_cfg_and_arms_skip_epochs_and_share_cfg_root(parent, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("static effect must skip epoch search")

    monkeypatch.setattr(effect.epoch, "run_epoch", forbidden)
    result = effect.probe(parent, edit_op(parent, "route_ok_rt_sleep", "M2"))
    assert result["changed"] == ["arms"]
    assert not result["fixture"]["ran_epoch"]
    tree = genome.expanded(parent)
    tree["ops.jsonl"][0]["payload"]["params"]["m"] += 1
    result = effect.probe(parent, genome.pack(parent, tree))
    assert result["changed"] == ["cfg"]
    before, after = result["detail"]["cfg"].values()
    assert before["body"]["tmp_dir"] == after["body"]["tmp_dir"]


def test_comb_state_reaches_hammers_library(parent):
    child = edit_op(parent, "comb_alpha", "M2")
    result = effect.probe(parent, child)
    assert "library" in result["changed"]
    assert result["fixture"]["ran_epoch"]
    assert effect.meter_track(parent, child) == "targeted"


def test_probe_reads_epoch_outputs_and_ignores_clock_noise(parent, monkeypatch):
    calls = []

    def run(root, n, **kwargs):
        assert n == 0 and kwargs["holdout"] is False and kwargs["threads"] == 1
        assert fm.load_frozen(root)["budgets"]["L"] == effect.FIXTURE_BUDGET
        side = len(calls)
        calls.append(root)
        fm.write_json(root / "live/state.json", {"pool_mult": 1 + side, "uses": {}})
        fm.write_json(root / "epochs/0/status.json", {"arm": None, "gate_in": side})
        fm.write_jsonl(
            root / "epochs/0/solutions.jsonl",
            [{"program": None, "seconds": time.time()}],
        )

    monkeypatch.setattr(effect.epoch, "run_epoch", run)
    result = effect.probe(parent, parent)
    assert result["changed"] == ["pool_mult", "feed"]
    assert len(calls) == 2


def test_meter_track_compares_the_whole_genome_to_g0(parent):
    assert effect.meter_track(parent, parent) == "all"
    child = edit_op(parent, "comb_alpha", "M3")
    assert effect.meter_track(parent, child) == "targeted"
    tree = genome.expanded(child)
    tree["ops.jsonl"][0]["payload"]["params"]["m"] += 1
    assert effect.meter_track(parent, genome.pack(child, tree)) == "all"
    # A crossover can restore g0's comb but retain an edit inherited elsewhere.
    tree = genome.expanded(parent)
    tree["frozen.json"]["judge"]["ablate_max"] += 1
    assert effect.meter_track(parent, genome.pack(parent, tree)) == "all"
    tree = genome.expanded(parent)
    next(o for o in tree["ops.jsonl"] if o["id"] == "comb_alpha")["payload"]["body"] = [
        "rot90",
        ["$in"],
    ]
    assert effect.meter_track(parent, genome.pack(parent, tree)) == "all"


@pytest.mark.parametrize("operator", ["M2", "M3"])
def test_existing_targeted_meter_accepts_comb_children(
    parent, operator, tmp_path, monkeypatch
):
    allowed = tmp_path / "meters"
    monkeypatch.setattr(quick, "SCRATCH", allowed)
    monkeypatch.setattr(meter, "SCRATCH", allowed)
    child = edit_op(parent, "comb_alpha", operator)
    source = tmp_path / "child/tree.json"
    fm.write_json(source, child)
    run = allowed / "child"
    meta = meter.prepare_meter(
        source,
        run,
        list(effect.FIXTURE_TASKS),
        strip=effect.meter_track(parent, child),
        L=effect.FIXTURE_BUDGET,
        epochs=1,
    )
    assert meta["cfg"]["strip"] == "targeted"
    # Only direct e0 library hits are removed; all other child edits survive.
    expected = [
        op
        for op in genome.expanded(child)["ops.jsonl"]
        if op["id"] not in meta["stripped_ops"]
    ]
    assert fm.read_jsonl(run / "initial_ops.jsonl") == fm.load_ops(run / "root")
    assert [
        {k: op[k] for k in genome.boundary.OP_DEFINITION_FIELDS}
        for op in fm.load_ops(run / "root")
    ] == expected


def test_probe_respects_stop_switch(parent, monkeypatch):
    def stopped():
        raise RuntimeError("STOP")

    monkeypatch.setattr(effect.boundary, "check_stop", stopped)
    with pytest.raises(RuntimeError, match="STOP"):
        effect.probe(parent, parent)
