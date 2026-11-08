"""Every seed primitive on non-rectangular data: ragged lists, negative and
large integers, empty lists. No case may crash or behave specially."""

import pytest

from arcagi.seed import PRIMS, EvalError, run
from arcagi.seed.prims import MAX_LEN

RAGGED = ((1, 2, 3), (), (-4,), (10, 200, -3000, 7))
NEG_BIG = (-5, 12, 99, -100, 0)


def inc(x):
    return x + 1


def odd(x):
    return x % 2 == 1


def plus(a, b):
    return a + b


# name -> list of (args, expected)
CASES = {
    "add": [((-5, 12), 7), ((1000, -1000), 0)],
    "sub": [((-5, 12), -17), ((99, 100), -1)],
    "mul": [((-5, 12), -60), ((0, -7), 0)],
    "neg": [((-5,), 5), ((12,), -12)],
    "mod": [((-5, 12), 7), ((123, 10), 3)],
    "eq": [((-5, -5), True), (((), ()), True), ((RAGGED, RAGGED[:2]), False)],
    "lt": [((-5, 12), True), ((100, 99), False)],
    "max": [((-5, 12), 12), ((-5, -50), -5)],
    "min": [((-5, 12), -5), ((300, 200), 200)],
    "and": [((True, False), False), ((True, True), True)],
    "or": [((False, False), False), ((True, False), True)],
    "not": [((True,), False), ((False,), True)],
    "if": [((True, RAGGED, ()), RAGGED), ((False, -1, 42), 42)],
    "len": [((RAGGED,), 4), (((),), 0), ((NEG_BIG,), 5)],
    "nth": [((RAGGED, 3), RAGGED[3]), ((NEG_BIG, 2), 99)],
    "head": [((RAGGED,), (1, 2, 3)), ((NEG_BIG,), -5)],
    "last": [((RAGGED,), RAGGED[3]), ((NEG_BIG,), 0)],
    "take": [((2, RAGGED), RAGGED[:2]), ((-3, NEG_BIG), ()), ((50, ()), ())],
    "drop": [((2, RAGGED), RAGGED[2:]), ((-3, NEG_BIG), NEG_BIG), ((5, ()), ())],
    "reverse": [((RAGGED,), RAGGED[::-1]), (((),), ())],
    "cons": [((-7, NEG_BIG), (-7, *NEG_BIG)), (((), ()), ((),))],
    "append": [((RAGGED, ()), RAGGED), ((NEG_BIG, (11,)), (*NEG_BIG, 11))],
    "concat": [((RAGGED,), (1, 2, 3, -4, 10, 200, -3000, 7)), (((),), ())],
    "range": [((3,), (0, 1, 2)), ((-4,), ()), ((0,), ())],
    "repeat": [((3, -12), (-12, -12, -12)), ((-1, 5), ()), ((2, ()), ((), ()))],
    "count": [((-5, (-5, 3, -5)), 2), (((), RAGGED), 1), ((1, ()), 0)],
    "sort": [((NEG_BIG,), (-100, -5, 0, 12, 99)), ((RAGGED,), tuple(sorted(RAGGED)))],
    "map": [((inc, NEG_BIG), (-4, 13, 100, -99, 1)), ((len, RAGGED), (3, 0, 1, 4))],
    "filter": [((odd, NEG_BIG), (-5, 99)), ((odd, ()), ())],
    "zipwith": [((plus, NEG_BIG, (1, 2)), (-4, 14)), ((plus, (), NEG_BIG), ())],
    "fold": [
        ((plus, 0, NEG_BIG), 6),
        ((plus, (), RAGGED), (1, 2, 3, -4, 10, 200, -3000, 7)),
    ],
    "transpose": [
        ((RAGGED,), ((1, -4, 10), (2, 200), (3, -3000), (7,))),
        (((),), ()),
        ((((), ()),), ()),
    ],
}


def test_every_primitive_has_cases():
    assert set(CASES) == set(PRIMS)
    assert len(PRIMS) <= 40


@pytest.mark.parametrize("name", sorted(CASES))
def test_primitive_generic(name):
    fn = PRIMS[name].fn
    for args, want in CASES[name]:
        assert fn(*args) == want, (name, args)


@pytest.mark.parametrize("prog", [("head", ("$in",)), ("last", ("$in",))])
def test_partial_on_empty_is_eval_error(prog):
    with pytest.raises(EvalError):
        run(prog, ())


def test_partial_errors_are_eval_errors():
    with pytest.raises(EvalError):
        run(("nth", ("$in",), -1), (1, 2))
    with pytest.raises(EvalError):
        run(("nth", ("$in",), 9), (1, 2))
    with pytest.raises(EvalError):
        run(("mod", 3, 0), ())
    with pytest.raises(EvalError):
        run(("range", ("mul", ("len", ("$in",)), 9)), tuple(range(MAX_LEN)))


def test_run_on_ragged_input():
    x = [[1, 2, 3], [], [-4], [10, 200, -3000, 7]]
    lam = ("lam", 1, ("reverse", ("$0",)))
    assert run(("map", lam, ("$in",)), x) == ((3, 2, 1), (), (-4,), (7, -3000, 200, 10))
    assert run(("transpose", ("$in",)), x) == ((1, -4, 10), (2, 200), (3, -3000), (7,))
    total = ("fold", ("lam", 2, ("add", ("$0",), ("len", ("$1",)))), 0, ("$in",))
    assert run(total, x) == 8
    assert run(("sort", ("concat", ("$in",))), x) == (-3000, -4, 1, 2, 3, 7, 10, 200)


def test_task_consts_and_without():
    from arcagi.seed import prims, solve
    from arcagi.seed.library import Library

    assert prims.task_consts(([(3, 12), (-7,)], ((True, 3),))) == (-7, -1, 0, 1, 3, 12)
    a = ((1, 2), (3, 4))
    train = [(a, ((1, 3), (2, 4))), (((5, 6, 7),), ((5,), (6,), (7,)))]
    assert solve(train, Library(), 20_000).program == ("transpose", ("$in",))
    with prims.without("transpose"):
        assert "transpose" not in PRIMS
        res = solve(train, Library(), 20_000)
        assert res.program is None or "transpose" not in repr(res.program)
        with pytest.raises(EvalError):
            run(("transpose", ("$in",)), a)
    assert "transpose" in PRIMS and len(PRIMS) == 32
