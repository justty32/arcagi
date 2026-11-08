"""r08 split flags: SPLITS / DEFAULT_SPLITS, the ``halves`` and ``nest``
splits, r07 equivalence of the old calls, budget accounting, eval_steps."""

import pytest

from arcagi import seed
from arcagi.seed import Library, decomp, lam, run, solve
from arcagi.seed.decomp import DEFAULT_SPLITS, SPLITS, normalize
from arcagi.seed.enum import Enumerator
from arcagi.seed.halves import cuts, halves_splits
from arcagi.seed.types import INPUT, INT, ListT

HALVES = DEFAULT_SPLITS | {"halves"}
NEST = DEFAULT_SPLITS | {"nest"}
BOTH = DEFAULT_SPLITS | {"halves", "nest"}

RAGGED = ((1, -2, 3), (), (-4,), (10, 20, -30, 7), (5, 5))
EMPTYISH = ((), (), ())
NEG = ((-1, -2), (-3, -4), (0, -9), (-7, 8))


def _key(r):
    return (r.program, r.nodes, r.nodes_to_first, r.near, r.eval_steps)


def mirror_top(x):
    k = len(x) // 2
    return x[:k] + x[:k][::-1]


A = ((2, 2, 2), (3, 3, 3), (0, 0, 0), (0, 0, 0))
B = ((1, 4), (8, 8), (5, 0), (0, 0), (0, 0), (0, 0))
C = ((7, 1, 1, 2), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0))


def test_split_names_and_normalize():
    assert set(DEFAULT_SPLITS) == {
        "map",
        "zip_pos",
        "if",
        "take",
        "conj_transpose",
        "conj_reverse",
        "append",
    }
    assert set(SPLITS) == DEFAULT_SPLITS | {"halves", "nest"}
    assert "halves" not in DEFAULT_SPLITS and "nest" not in DEFAULT_SPLITS
    assert normalize(True) == DEFAULT_SPLITS
    assert normalize(False) == frozenset()
    assert normalize(frozenset({"map"})) == frozenset({"map"})
    with pytest.raises(ValueError):
        normalize(frozenset({"nope"}))


@pytest.mark.parametrize("f", [mirror_top, lambda x: tuple(r[::-1] for r in x)])
def test_old_calls_equal_named_sets(f):
    train = [(A, f(A)), (B, f(B))]
    on = solve(train, Library(), 30_000)
    assert _key(on) == _key(solve(train, Library(), 30_000, decompose=DEFAULT_SPLITS))
    off = solve(train, Library(), 30_000, decompose=False)
    assert _key(off) == _key(solve(train, Library(), 30_000, decompose=frozenset()))


def test_halves_mirror_found_only_with_flag():
    train = [(A, mirror_top(A)), (B, mirror_top(B))]
    res = solve(train, Library(), 100_000, decompose=HALVES)
    assert res.program is not None
    assert run(res.program, C) == mirror_top(C)
    assert res.nodes == res.nodes_to_first <= 100_000
    off = solve(train, Library(), 100_000)
    assert off.program is None or run(off.program, C) != mirror_top(C)


def test_halves_zip_with_separator():
    # odd length: first k and last k elements combined, the middle one ignored
    def f(x):
        k = len(x) // 2
        return tuple(max(a, b) for a, b in zip(x[:k], x[len(x) - k :]))

    xs = [(1, 5, 2, 9, 0, 7, 3), (4, 0, 6, 9, 8, 1, 2), (0, 3, 3, 9, 5, 5, 1)]
    train = [((x,), (f(x),)) for x in xs]
    res = solve(train, Library(), 100_000, decompose=HALVES)
    assert res.program is not None
    probe = (6, 2, 0, 9, 1, 7, 4)
    assert run(res.program, (probe,)) == (f(probe),)


def test_cut_points_from_lengths():
    # equal input lengths: literal k; varying lengths: k from len $in
    (ks, kp, tp), *_ = cuts(((1, 2, 3, 4), (5, 6, 7, 8)), ((1,), (2,)))
    assert ks == (2, 2) and kp == 2 and tp == 2
    xs = ((1, 2, 3, 4), (5, 6, 7, 8, 9, 10), (1, 2, 3, 4, 5))
    outs = tuple(x[: len(x) // 2] for x in xs)
    first = cuts(xs, outs)[0]
    assert first[0] == (2, 3, 2)
    for x in (*xs, (), (4,), (1, 2, 3, 4, 5, 6, 7, 8, 9)):
        assert run(("take", first[1], ("$in",)), x) == x[: len(x) // 2]
        assert run(("drop", first[2], ("$in",)), x) == x[len(x) - len(x) // 2 :]
    # no cut when some input is too short to split
    assert cuts(((1,), (1, 2)), ((1,), (1,))) == []
    assert cuts(((), (1, 2)), ((), (1,))) == []


@pytest.mark.parametrize("names", [HALVES, NEST, BOTH])
@pytest.mark.parametrize("data", [RAGGED, EMPTYISH, NEG])
def test_new_splits_survive_odd_data(names, data):
    variants = [data, data[::-1], tuple(r[::-1] for r in data)]
    outs = [tuple(r for r in d if r) + tuple(r[::-1] for r in d if r) for d in variants]
    train = list(zip(variants, outs, strict=True))
    res = solve(train, Library(), 20_000, decompose=names)
    assert 0 < res.nodes <= 20_000
    if res.program is not None:
        for x, y in train:
            assert run(res.program, x) == y
    for x, y in [(RAGGED, RAGGED[::-1]), (EMPTYISH, EMPTYISH), (NEG, NEG)]:
        list(halves_splits((x, x[1:]), (y, y[1:]), (INPUT, INPUT)))


def test_all_subsearch_nodes_are_charged(monkeypatch):
    spent = []
    real_search, real_cond = decomp.search, decomp.cond_witness

    def counting_search(en):
        out = real_search(en)
        spent.append(en.nodes)
        return out

    def counting_cond(en, limit):
        prog, used = real_cond(en, limit)
        spent.append(used)
        return prog, used

    monkeypatch.setattr(decomp, "search", counting_search)
    monkeypatch.setattr(decomp, "cond_witness", counting_cond)
    hard = [(A, tuple(r[::-1] for r in A[::-1])[:3]), (B, B[1:4]), (C, C[:3])]
    for names in (DEFAULT_SPLITS, BOTH):
        spent.clear()
        res = solve(hard, Library(), 40_000, decompose=names)
        assert res.nodes == sum(spent) <= 40_000
        assert len(spent) > 2 and res.eval_steps > 0


def test_eval_steps_reported_and_deterministic():
    train = [(A, mirror_top(A)), (B, mirror_top(B))]
    a = solve(train, Library(), 50_000, decompose=HALVES)
    b = solve(train, Library(), 50_000, decompose=HALVES)
    assert a.eval_steps == b.eval_steps > 0
    off = solve(train, Library(), 5_000, decompose=False)
    assert off.eval_steps > 0


def test_nest_depth_only_inside_subproblems(monkeypatch):
    seen = []
    real = decomp.Enumerator

    class Spy(real):
        def __init__(self, *a, **kw):
            seen.append((kw.get("sub"), kw.get("lam_depth"), kw.get("lam_body_max")))
            super().__init__(*a, **kw)

    monkeypatch.setattr(decomp, "Enumerator", Spy)
    train = [(A, tuple(r[::-1] for r in A)), (B, tuple(r[::-1] for r in B))]
    for names, sld, want in [
        (DEFAULT_SPLITS, None, None),
        (NEST, None, decomp.NEST_DEPTH),
        (DEFAULT_SPLITS, 3, 3),
        (NEST, 2, 2),
    ]:
        seen.clear()
        solve(train, Library(), 20_000, decompose=names, sub_lam_depth=sld)
        assert seen[0] == (False, None, None)  # top-level probe: blind limits
        assert len(seen) > 1 and all(d == want for _, d, _ in seen[1:])


def test_deeper_pool_has_deeper_bodies():
    rows = [((1, 3, 4), (1, 4)), ((9, 2, 5), (2, 5))]

    def max_depth(d, bm):
        en = Enumerator(
            rows,
            Library(),
            50,
            in_type=ListT(INT),
            out_type=ListT(INT),
            sub=True,
            lam_depth=d,
            lam_body_max=bm,
        )
        pool = lam.BodyPool(
            (INT,), Library(), [((), (v,)) for v in range(-2, 6)], (0, 1, 3)
        )
        pool.depth, pool.body_max = en.lam_depth, en.lam_body_max
        pool.lambdas(4)
        return max(b.depth for lvl in pool.bank for bs in lvl.values() for b in bs)

    assert max_depth(2, 4) == 2
    assert max_depth(3, 6) == 3


def test_runtime_lam_depth_knob_still_applies(monkeypatch):
    monkeypatch.setattr(lam, "LAM_DEPTH", 1)
    assert lam.BodyPool((INT,), Library(), [], (0,)).depth == 1


def test_enumerate_forwards_flags():
    from arcagi.tasks.models import Example, Task

    task = Task(
        "t",
        [
            Example(list(map(list, A)), list(map(list, mirror_top(A)))),
            Example(list(map(list, B)), list(map(list, mirror_top(B)))),
        ],
        [Example(list(map(list, C)), list(map(list, mirror_top(C))))],
    )
    (s,) = seed.enumerate(Library(), [task], 100_000, decompose=HALVES)
    assert s.train_ok and s.test_ok and s.eval_steps > 0
    (s0,) = seed.enumerate(Library(), [task], 100_000)
    assert not s0.test_ok


R07_PASS0 = {  # reports/curve-r07/dec/solutions.jsonl, pass 0 (seed efdee5d)
    "68b16354": (23, ("reverse", ("$in",))),
    "1e0a9b12": (
        24739,
        ("transpose", ("map", ("lam", 1, ("sort", ("$0",))), ("transpose", ("$in",)))),
    ),
    "d10ecb37": (
        6369,
        ("map", ("lam", 1, ("take", 2, ("$0",))), ("take", 2, ("$in",))),
    ),
    "beb8660c": (
        89029,
        ("sort", ("map", ("lam", 1, ("sort", ("$0",))), ("$in",))),
    ),
}


def test_r07_l16_pass0_unchanged_under_default():
    import json
    from pathlib import Path

    from arcagi.tasks.io import load_task

    root = Path(__file__).resolve().parents[2]
    tset = root / "data" / "r07" / "taskset.json"
    tdir = root / "data" / "ARC-AGI" / "data" / "training"
    if not tset.exists() or not tdir.exists():
        pytest.skip("r07 taskset or ARC data missing")
    ids = [e["task_id"] for e in json.loads(tset.read_text())["learn"]]
    tasks = [load_task(tdir / f"{t}.json") for t in ids]
    for dec in (True, DEFAULT_SPLITS):
        sols = seed.enumerate(Library(), tasks, 100_000, workers=2, decompose=dec)
        got = {s.task_id: (s.nodes_to_first, s.program) for s in sols if s.test_ok}
        assert got == R07_PASS0
        for s in sols:
            if s.task_id in R07_PASS0:
                assert s.nodes == s.nodes_to_first
