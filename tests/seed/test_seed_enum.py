from arcagi.seed import Library, run, solve
from arcagi.seed.enum import elem_score

A = ((1, 2, 3), (4, 5, 6))
B = ((7, 8), (9, 0), (1, 1))
C = ((3, 1, 4, 1), (5, 9, 2, 6), (5, 3, 5, 8))


def ud(g):
    return g[::-1]


def lr(g):
    return tuple(r[::-1] for r in g)


def tr(g):
    return tuple(zip(*g, strict=True))


def _check(f, budget=50_000):
    res = solve([(A, f(A)), (B, f(B))], Library(), budget)
    assert res.program is not None
    assert run(res.program, C) == f(C)  # generalizes to an unseen input
    assert res.nodes_to_first == res.nodes <= budget
    return res


def test_finds_reverse():
    assert _check(ud).program == ("reverse", ("$in",))


def test_finds_map_reverse():
    res = _check(lr)
    assert res.program == ("map", ("lam", 1, ("reverse", ("$0",))), ("$in",))


def test_finds_transpose():
    assert _check(tr).program == ("transpose", ("$in",))


def test_budget_respected_and_near():
    train = [(A, ((9,),)), (B, ((8, 8),))]
    res = solve(train, Library(), 3000)
    assert res.program is None and res.nodes == 3000 and res.nodes_to_first is None
    assert res.near and all(0.0 <= s <= 1.0 for _, s in res.near)
    scores = [s for _, s in res.near]
    assert scores == sorted(scores, reverse=True)


def test_order_changes_preference_not_correctness():
    plain = solve([(A, lr(A)), (B, lr(B))], Library(), 50_000)
    pri = solve([(A, lr(A)), (B, lr(B))], Library(), 50_000, order={"map": 5.0})
    assert pri.program is not None and pri.nodes <= plain.nodes


def test_elem_score():
    assert elem_score(A, A) == 1.0
    assert elem_score(((1, 0, 3), (4, 5, 6)), A) == 5 / 6
    assert elem_score(B, A) == 0.0
    assert elem_score(3, A) == 0.0
