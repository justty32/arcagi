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


# --- r08 -------------------------------------------------------------------

def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_r08_taskset_rule():
    data = _load_script("r08_taskset").build()
    assert data == json.loads((ROOT / "data/r08/taskset.json").read_text())
    r07 = json.loads((ROOT / "data/r07/taskset.json").read_text())
    assert data["learn"] == r07["learn"] and data["holdout"] == r07["holdout"]
    ids = [[e["task_id"] for e in data[k]] for k in ("learn", "holdout",
                                                     "holdout24", "practice")]
    assert [len(x) for x in ids] == [16, 8, 24, 32]
    flat = [t for x in ids for t in x]
    assert len(set(flat)) == len(flat)  # disjoint
    themes = [e["theme"] for e in data["practice"]]
    assert all(themes.count(t) <= 16 for t in set(themes))
    assert len(data["rand32"]) == 32
    assert not {e["task_id"] for e in data["rand32"]} & set(ids[0] + ids[1] + ids[2])


def test_pool_budget_subset_and_logcost():
    from arcagi.grow import pool as pl
    assert [pl.budget(25_000, 2.0, 400_000, p) for p in range(6)] == [
        25_000, 50_000, 100_000, 200_000, 400_000, 400_000]
    ids = [f"t{i:02d}" for i in range(10)]
    a = pl.subset(ids, 1, 0.8)
    assert len(a) == 8 and a == pl.subset(ids, 1, 0.8) and a != pl.subset(ids, 2, 0.8)
    b = 100_000
    assert pl.task_cost(None, False, b) == pl.task_cost(5, False, b)
    c0 = pl.task_cost(1024, True, b)  # 10 bits at pass 0
    assert pl.capped(pl.task_cost(2, True, b), c0, b) == c0 - 2.0  # capped gain
    unsolved0 = pl.task_cost(None, False, b)
    assert pl.capped(1.0, unsolved0, b) == 1.0  # new solve: full credit


def test_gate_mdl_and_loo():
    from arcagi.grow import pool as pl
    train = [([[1]], [[1, 1], [1, 1]])] * 3
    deep = ("reverse", ("reverse", ("reverse", IN)))  # size 4
    assert pl.mdl_ok(("reverse", IN), train, 4)  # size 2 < 12 / 4
    assert not pl.mdl_ok(deep, train, 4)  # old r08 gate (/4)
    assert pl.mdl_ok(deep, train)  # D-r8-19 gate: 4 < 12
    assert not pl.mdl_ok(("reverse", deep), [train[0]])  # 5 >= 4 cells
    ok, _ = pl.loo_ok(train, lambda pairs: (IN, 1), lambda p, ex: True)
    assert ok
    bad, n = pl.loo_ok(train, lambda pairs: (None, 5), lambda p, ex: True)
    assert not bad and n == 5
    two = train[:2]
    assert pl.loo_ok(two, lambda pairs: (None, 5), lambda p, ex: True) == (True, 0)


def test_crn_judge_bootstrap():
    def score(lc, auc, per):
        return {"logcost": lc, "auc": auc,
                "task": {f"t{i}": [v] * 5 for i, v in enumerate(per)}}
    before = score([100.0] * 5, [32] * 5, [10.0] * 16)
    same = meta.crn_judge(before, before)
    assert not same["accepted"] and same["reward"] == 0.0
    better = score([90.0] * 5, [32] * 5, [9.0] * 16)
    j = meta.crn_judge(before, better)
    assert j["accepted"] and j["mean_drop"] == 16.0 and j["reward"] == 3.0
    worse_auc = score([90.0] * 5, [31] * 5, [9.0] * 16)
    assert not meta.crn_judge(before, worse_auc)["accepted"]
    from arcagi.grow import pool as pl
    assert pl.bootstrap({"a": 1.0, "b": 3.0}, {"a": 0.0, "b": 0.0}) == \
        pl.bootstrap({"a": 1.0, "b": 3.0}, {"a": 0.0, "b": 0.0})


def test_backend_split_sets():
    from arcagi.grow import backend
    assert backend.split_set("none") is False
    assert backend.split_set("default") is True
    if backend.HAS_SPLIT_SETS:
        assert "halves" in backend.split_set("default+halves")
    else:
        import pytest
        with pytest.raises(RuntimeError):
            backend.split_set("default+halves")


def test_r08_row_fields():
    sc = {"logcost": [10.0] * 5, "auc": [3] * 5, "cost_s": 1.0,
          "task": {"t0": [10.0] * 5}}
    row = meta.r08_row("r08", sc, sc, knob="m", before=3, after=5)
    assert row["before"] == 3 and row["after"] == 5 and not row["accepted"]
