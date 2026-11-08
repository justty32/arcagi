import importlib.util
import json
import random
from pathlib import Path

from arcagi.grow import compress as g1
from arcagi.grow import curve, evolve, meta
from arcagi.grow import knobs as kn
from arcagi.grow import prog as pg
from arcagi.grow.sig import infer_sig

ROOT = Path(__file__).resolve().parents[2]
IN = ("$in",)


def test_anti_unify_two_holes_max():
    a = ("map", ("lam", 1, ("sort", ("$0",))), ("reverse", IN))
    b = ("map", ("lam", 1, ("sort", ("$0",))), ("transpose", IN))
    t = g1.anti_unify(a, b, 2)
    assert t == ("map", ("lam", 1, ("sort", ("$0",))), ("$h0",))
    c = ("append", ("reverse", IN), ("head", IN))
    d = ("append", ("transpose", IN), ("last", IN))
    assert g1.anti_unify(c, d, 1) is None
    assert g1.n_holes(g1.anti_unify(c, d, 2)) == 2


def test_candidates_mdl_and_update_retire():
    sub = ("sort", ("transpose", ("reverse", IN)))
    progs = {"t1": ("transpose", sub), "t2": ("reverse", sub)}
    cands = g1.candidates(progs, g1.Params(m=3, k=2.0, max_holes=2))
    best = cands[0]
    assert best["saving"] > 0 and best["src_tasks"] == ["t1", "t2"]
    # saving = occ * size - size - k * holes
    occ, sz, h = best["occurrences"], best["size"], best["holes"]
    assert best["saving"] == occ * sz - sz - 2.0 * h
    blocks, added = g1.update([], progs, g1.Params(m=2), 0)
    assert len(added) == 2 and all(b["sig"] for b in blocks)
    for p in range(1, 1 + g1.RETIRE_AFTER):
        blocks, _ = g1.update(blocks, {}, g1.Params(m=0), p)
    assert blocks == []


def test_infer_sig():
    assert infer_sig(("reverse", ("$h0",))) == "(list[a]) -> list[a]"
    assert infer_sig(("sort", ("transpose", IN))) == "list[list[int]]"
    assert infer_sig(("add", ("head", IN), 1)) is None  # head IN is list[int]


def test_evolve_is_seeded():
    train = [([[1, 2], [3, 4]], [[2, 1], [4, 3]])]
    near = [(("transpose", IN), 0.5), (IN, 0.0)]
    donors = [("map", ("lam", 1, ("reverse", ("$0",))), IN)]
    r1 = evolve.evolve("x", train, near, None, 300, 0, donors)
    r2 = evolve.evolve("x", train, near, None, 300, 0, donors)
    assert r1 == r2
    assert r1[0] is not None and evolve.fitness(r1[0], train, None) == 1.0


def test_pixel_score():
    assert pg.pixel_score([[1, 2]], [[1, 3]]) == 0.5
    assert pg.pixel_score([[1]], [[1], [2]]) == 0.0


def test_empty_curve_is_deterministic(tmp_path):
    cfg = curve.Config(tree="empty", passes=2, budget=3000, workers=2,
                       learn=False, g4=False)
    shas = []
    for i in range(2):
        curve.run_curve(cfg, tmp_path / f"o{i}", tmp_path / f"l{i}",
                        log=lambda *_: None)
        shas.append(curve.curve_sha(tmp_path / f"o{i}" / "curve.csv"))
    assert shas[0] == shas[1]
    head = (tmp_path / "o0" / "curve.csv").read_text().splitlines()[0]
    assert head.split(",") == curve.COLUMNS


def test_meta_ledger_and_thompson(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    meta.append_ledger({"kind": "r07", "knob": "m", "accepted": True}, ledger)
    meta.append_ledger({"kind": "r07", "knob": "m", "accepted": False}, ledger)
    meta.append_ledger({"kind": "other", "knob": "m"}, ledger)
    st = meta.knob_stats(ledger)
    assert meta.real_gain([2, 2, 2], [3, 3, 2]) is False
    assert meta.real_gain([2, 2, 2], [3, 3, 3]) is True
    assert st["m"] == (2, 1) and st["k"] == (0, 0)
    a = meta.pick_knob(random.Random(1), st, kn.Knobs())
    b = meta.pick_knob(random.Random(1), st, kn.Knobs())
    assert a == b and a in kn.CHOICES


def test_taskset_rule():
    spec = importlib.util.spec_from_file_location(
        "r07_taskset", ROOT / "scripts" / "r07_taskset.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = mod.build()
    assert data == json.loads((ROOT / "data/r07/taskset.json").read_text())
    for part, n in (("learn", 8), ("holdout", 4)):
        flags = [e["r06_solved"] for e in data[part]]
        assert flags.count(True) == n and flags.count(False) == n


def test_baseline_seedlib_stays_empty():
    base = ROOT / "aos" / "seedlib" / "blocks.json"
    assert not base.exists() or json.loads(base.read_text()) == []


def test_change_score_ignores_copied_cells():
    inp = [[1, 1], [1, 1]]
    target = [[1, 2], [1, 1]]
    assert pg.change_score(inp, target, inp) == 0.0  # copying the input
    assert pg.change_score([[1, 2], [0, 0]], target, inp) == 1.0 - 0.0
    assert pg.change_score([[1]], target, inp) == 0.0


def test_cold_start_extra_feeds_templates_only():
    sub = ("sort", ("transpose", ("reverse", IN)))
    blocks, added = g1.update([], {}, g1.Params(m=1, k=1.0), 0,
                              {"a~near": ("transpose", sub), "b~near": sub})
    assert added and all(b["uses"] == 0 for b in blocks)
