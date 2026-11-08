from arcagi.seed import Library, run, solve
from arcagi.seed.witness import subst_leaves

A = ((1, 2, 3), (4, 1, 6), (1, 1, 0))
B = ((7, 1), (9, 0), (1, 1))
C = ((1, 5, 1, 8), (0, 1, 9, 1))


def recolor(g):
    return tuple(tuple(2 if v == 1 else v for v in r) for r in g)


def mirror_h(g):
    return tuple(r + r[::-1] for r in g)


def _train(f):
    return [(A, f(A)), (B, f(B))]


def test_cellwise_map_found_only_with_decomposition():
    res = solve(_train(recolor), Library(), 100_000)
    prog = res.program
    assert prog is not None and prog[0] == "map"
    inner = prog[1][2]
    assert inner[0] == "map" and inner[1][0] == "lam"  # map (lam (map g $0)) $in
    assert run(prog, C) == recolor(C)
    assert res.nodes == res.nodes_to_first <= 100_000
    off = solve(_train(recolor), Library(), 100_000, decompose=False)
    assert off.program is None and off.nodes == 100_000


def test_map_reverse_and_append_splits():
    res = solve(_train(mirror_h), Library(), 100_000)
    assert res.program == (
        "map",
        ("lam", 1, ("append", ("$0",), ("reverse", ("$0",)))),
        ("$in",),
    )
    off = solve(_train(mirror_h), Library(), 100_000, decompose=False)
    assert res.nodes < off.nodes
    lr = solve(_train(lambda g: tuple(r[::-1] for r in g)), Library(), 50_000)
    assert lr.program == ("map", ("lam", 1, ("reverse", ("$0",))), ("$in",))


def test_position_split_uses_zipwith():
    def f(g):
        return tuple(tuple(v if j != 1 else 0 for j, v in enumerate(r)) for r in g)

    res = solve(_train(f), Library(), 100_000)
    assert res.program is not None and "zipwith" in repr(res.program)
    assert run(res.program, ((5, 6, 7),)) == ((5, 0, 7),)


def test_decomposition_is_deterministic():
    a = solve(_train(recolor), Library(), 100_000)
    b = solve(_train(recolor), Library(), 100_000)
    assert (a.program, a.nodes, a.nodes_to_first, a.near) == (
        b.program,
        b.nodes,
        b.nodes_to_first,
        b.near,
    )


def test_subst_leaves_only_outside_lambdas():
    p = ("map", ("lam", 1, ("reverse", ("$0",))), ("$in",))
    assert subst_leaves(p, {"$in": ("$0",)}) == (
        "map",
        ("lam", 1, ("reverse", ("$0",))),
        ("$0",),
    )
    assert subst_leaves(("map", ("lam", 1, ("$in",)), 3), {"$in": ("$0",)}) is None


def test_take_and_transpose_conjugation_splits():
    def crop(g):
        return tuple(r[:2] for r in g[:2])

    a = ((1, 2, 3, 4), (5, 6, 7, 8), (9, 1, 2, 3))
    b = ((4, 4, 0), (3, 1, 2), (0, 0, 7))
    res = solve([(a, crop(a)), (b, crop(b))], Library(), 100_000)
    assert res.program is not None and run(res.program, C) == crop(C)

    def colsort(g):
        return tuple(zip(*(sorted(c) for c in zip(*g)), strict=True))

    res = solve([(a, colsort(a)), (b, colsort(b))], Library(), 100_000)
    assert res.program is not None and res.program[0] == "transpose"
    assert run(res.program, C) == colsort(C)
