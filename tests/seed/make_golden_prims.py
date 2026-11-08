"""Generate ``tests/seed/golden_prims.json``: input -> output cases for every
seed primitive, computed by the Python implementation (``seed.interp.run``).

Run: ``uv run python tests/seed/make_golden_prims.py``. Each case is a whole
seed program applying one primitive, so a port can check it through its own
interpreter: integer arguments are literals, list/bool arguments come from
``$in`` (``["$in"]`` when there is one, else ``["nth", ["$in"], j]``), function
arguments are lambdas. First-order cases also list ``args`` (the argument
values). ``output`` is ``"ERR"`` when evaluation fails.
"""

from __future__ import annotations

import json
from pathlib import Path

from arcagi.seed import PRIMS, EvalError, interp, run
from arcagi.seed.prims import MAX_INT

OUT = Path(__file__).with_name("golden_prims.json")

RAG = (1, 2, 3)
LISTS = [(), (5,), (1, -2, 3), (0, 0, 0, 0), (-7, 9, -7, 2, 2), (3, 1, 2), (10, -10)]
NESTED = [
    (),
    ((),),
    ((1, 2, 3), (4,), ()),
    ((-1, -2), (3, 4), (5, 6)),
    ((1,), (2, 3), (4, 5, 6)),
    ((0, 0), (0, 0)),
    ((7, 8, 9),),
    ((), (1, -1), ()),
]
INTS = [0, 1, -1, 2, -3, 7, 10, -10, 99, -100, 123456, -999999]
BOOLS = [(True, False), (False, True), (True, True), (False, False)]
BIG = MAX_INT // 2 + 1

F1_INT = [
    ("lam", 1, ("add", ("$0",), 1)),
    ("lam", 1, ("neg", ("$0",))),
    ("lam", 1, ("mul", ("$0",), ("$0",))),
    ("lam", 1, 7),
]
P1_INT = [
    ("lam", 1, ("lt", 0, ("$0",))),
    ("lam", 1, ("eq", ("mod", ("$0",), 2), 0)),
    ("lam", 1, ("not", ("eq", ("$0",), -7))),
]
F2_INT = [
    ("lam", 2, ("add", ("$0",), ("$1",))),
    ("lam", 2, ("sub", ("$0",), ("$1",))),
    ("lam", 2, ("max", ("$0",), ("$1",))),
    ("lam", 2, ("$1",)),
]


def _ints2() -> list[tuple]:
    out = [(a, b) for a in INTS[:6] for b in INTS[:6] if a <= b or b < 0]
    return out[:22] + [(BIG, BIG), (-BIG, -BIG), (MAX_INT, 1)]


def _cases(name: str) -> list[tuple]:
    """Argument tuples (python values or lambda programs) for ``name``."""
    lists, nested = LISTS, NESTED
    if name in ("add", "sub", "mul", "max", "min", "lt"):
        return _ints2()
    if name == "mod":
        return _ints2() + [(5, 0), (-7, 3), (7, -3), (-7, -3)]
    if name == "neg":
        extra = (3, 4, 5, 6, 8, -8, 1000, -1000)
        return [(v,) for v in INTS + [MAX_INT, -MAX_INT, *extra]]
    if name == "eq":
        return (
            [(a, b) for a, b in _ints2()[:8]]
            + [(x, y) for x in lists[:4] for y in lists[:3]]
            + [
                (nested[2], nested[2]),
                (nested[3], nested[4]),
                (True, True),
                (True, False),
            ]
        )
    if name == "if":
        return (
            [(c, a, b) for c in (True, False) for a, b in _ints2()[:5]]
            + [(c, x, y) for c in (True, False) for x, y in zip(lists, lists[1:])][:8]
            + [(True, nested[2], nested[3]), (False, nested[2], nested[3])]
        )
    if name in ("len", "head", "last", "reverse", "sort"):
        more = [(9,) * 10, (-1, -1, -1), (2, 1), ((4,), (4,)), ((2, 1), (1, 9, 9))]
        return [(x,) for x in lists + nested + more] + [
            (((3, 1), (2,), (3, 0)),),
            ((True, False),),
        ]
    if name == "nth":
        return [(x, i) for x in lists[:5] + nested[2:5] for i in (0, 1, -1, 3)][:30]
    if name in ("take", "drop"):
        return [(k, x) for x in lists[:4] + nested[2:4] for k in (0, 2, -1, 5)]
    if name == "cons":
        return [(v, x) for v in (0, -3, 9) for x in lists[:6]] + [
            ((1, 2), nested[2]),
            ((), nested[0]),
            ((9,) * 3, ((1,),) * 1023),
        ]
    if name == "append":
        return [(x, y) for x in lists[:4] for y in lists[:5]] + [
            (nested[2], nested[3]),
            (nested[0], nested[1]),
            ((0,) * 600, (1,) * 600),
        ]
    if name == "concat":
        return (
            [(x,) for x in nested]
            + [
                (((1, 2), (3,)),),
                ((((1,), (2,)), ((3,),)),),
                (((0,) * 600, (1,) * 600),),
            ]
            + [((x, x),) for x in lists]
            + [((x, (), x),) for x in lists[1:4]]
        )
    if name == "range":
        return [(v,) for v in (0, 1, 2, 5, -1, -10, 1024, 1025)] + [
            (v,) for v in range(-5, 20)
        ]
    if name == "repeat":
        return (
            [(k, v) for k in (0, 1, 3, -2) for v in (0, -5)]
            + [(2, x) for x in lists[:4] + nested[2:4]]
            + [(1025, 0), (1024, 1), (3, (1, 2))]
            + [(k, v) for k in (2, 5) for v in (7, -1)]
        )
    if name == "count":
        return [(v, x) for v in (0, -7, 2) for x in lists] + [
            ((), nested[2]),
            ((1, 2, 3), nested[2]),
        ]
    if name == "map":
        return [(f, x) for f in F1_INT for x in lists[:5]] + [
            (("lam", 1, ("len", ("$0",))), x) for x in nested[:4]
        ]
    if name == "filter":
        return [(p, x) for p in P1_INT for x in lists] + [
            (("lam", 1, ("lt", 1, ("len", ("$0",)))), x) for x in nested[2:5]
        ]
    if name == "zipwith":
        return [
            (f, x, y) for f in F2_INT for x, y in zip(lists, lists[2:] + lists[:2])
        ][:22] + [
            (("lam", 2, ("append", ("$0",), ("$1",))), nested[2], nested[3]),
            (("lam", 2, ("append", ("$0",), ("$1",))), nested[3], nested[1]),
        ]
    if name == "fold":
        return [(f, z, x) for f in F2_INT for z in (0, -5) for x in lists[1:4]] + [
            (("lam", 2, ("append", ("$0",), ("$1",))), (), x) for x in nested[2:5]
        ]
    if name == "transpose":
        return (
            [(x,) for x in nested]
            + [
                (((1, 2, 3), (4, 5, 6)),),
                (((1,), (2, 3), (4, 5, 6)),),
                (((1, 2, 3), (), (4, 5)),),
                (((-1, -2, -3),),),
                (((), ()),),
                ((((1,), (2,)), ((3,),)),),
            ]
            + [
                ((tuple(x[i:] + x[:i] for i in range(3)),),)
                for x in ((1, 2, 3), (0, -1, 4))
            ]
            + [((((1,) * 2,) * 3,),) for _ in range(1)]
            + [(tuple((v,) * 3 for v in range(k)),) for k in range(2, 6)]
        )
    raise KeyError(name)


def _is_fn(a) -> bool:
    return isinstance(a, tuple) and len(a) == 3 and a[0] == "lam"


def _literal(a) -> bool:
    return isinstance(a, int) and not isinstance(a, bool)


def build(name: str, args: tuple) -> dict:
    data = [a for a in args if not _is_fn(a) and not _literal(a)]
    kids, j = [], 0
    for a in args:
        if _is_fn(a) or _literal(a):
            kids.append(a)
        elif len(data) == 1:
            kids.append(("$in",))
        else:
            kids.append(("nth", ("$in",), j))
            j += 1
    prog = (name, *kids)
    x = data[0] if len(data) == 1 else tuple(data)
    try:
        y = run(prog, x)
    except EvalError:
        y = "ERR"
    case = {"program": interp.to_json(prog), "input": _js(x), "output": _js(y)}
    if not any(_is_fn(a) for a in args):
        case["args"] = [_js(a) for a in args]
    return case


def _js(v):
    if isinstance(v, tuple):
        return [_js(e) for e in v]
    return v


def _bool_cases(name: str) -> list[dict]:
    """Bool arguments have no literal form: pick them by index from a bool
    list ``$in`` of varying length."""
    out = []
    pools = [(True, False), (False, True, True), (True, True, False, False)]
    for x in pools + [(False,) * 5, (True,) * 2, (False, True), (True, False, True)]:
        for i in range(len(x)):
            j = (i + 1) % len(x)
            args = (("nth", ("$in",), i),) + (
                () if name == "not" else (("nth", ("$in",), j),)
            )
            prog = (name, *args)
            out.append(
                {
                    "program": interp.to_json(prog),
                    "input": _js(x),
                    "output": run(prog, x),
                }
            )
    return out


def generate() -> dict:
    golden = {}
    for name in PRIMS:
        cases, seen = [], set()
        made = _bool_cases(name) if name in ("and", "or", "not") else None
        for args in _cases(name) if made is None else ():
            c = build(name, args)
            key = json.dumps(c, sort_keys=True)
            if key not in seen:
                seen.add(key)
                cases.append(c)
        cases += made or []
        assert len(cases) >= 20, (name, len(cases))
        golden[name] = cases
    doc = {
        "schema": "seed-golden-prims/1",
        "note": "generated by tests/seed/make_golden_prims.py from seed.interp.run",
        "sigs": {n: str(p.sig) for n, p in PRIMS.items()},
        "cases": golden,
    }
    return doc


def main() -> None:
    doc = generate()
    OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
    print(OUT, sum(len(v) for v in doc["cases"].values()), "cases")


if __name__ == "__main__":
    main()
