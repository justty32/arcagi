"""Witness functions for ``seed.decomp``: how a problem's examples split into
a subproblem, and how a subproblem's program is rebuilt into a whole one.
Only list and integer semantics are used."""

from __future__ import annotations

from collections.abc import Iterator

from .interp import Program
from .prims import PRIMS
from .types import INT, ListT

MIN_EXAMPLES = 2
# Split names of r07 (``append`` covers both ``append_pre`` and ``append_suf``;
# ``if`` is the conditional witness of ``seed.cond``).
R07_SPLITS: tuple[str, ...] = (
    "map",
    "zip_pos",
    "if",
    "take",
    "conj_transpose",
    "conj_reverse",
    "append",
)


def subst_leaves(prog: Program, repl: dict[str, Program]) -> Program | None:
    """Replace leaves named in ``repl`` outside lambdas; None if one is inside."""

    def go(p: Program, depth: int) -> Program:
        if isinstance(p, int):
            return p
        if len(p) == 1:
            if p[0] in repl:
                if depth:
                    raise ValueError(p[0])
                return repl[p[0]]
            return p
        if p[0] == "lam":
            return ("lam", p[1], go(p[2], depth + 1))
        if p[0] == "blk":
            return ("blk", p[1], *(go(a, depth) for a in p[2:]))
        return (p[0], *(go(a, depth) for a in p[1:]))

    try:
        return go(prog, 0)
    except ValueError:
        return None


def witness_splits(
    xs: tuple, outs: tuple, types: tuple, names: frozenset[str] = frozenset(R07_SPLITS)
) -> Iterator[tuple]:
    """Yield (name, sub_xs, sub_outs, sub_types, extra_leaves, build) for the
    r07 splits listed in ``names``."""
    in_t, out_t = types
    lists = all(isinstance(x, tuple) and isinstance(y, tuple) for x, y in zip(xs, outs))
    if not lists or not isinstance(in_t, ListT) or not isinstance(out_t, ListT):
        return
    same_len = all(len(x) == len(y) for x, y in zip(xs, outs))
    if same_len and _has("map"):
        ex = _table(((a,), b) for x, y in zip(xs, outs) for a, b in zip(x, y))
        if ex is not None and "map" in names:
            sx, sy = tuple(k[0] for k in ex), tuple(ex.values())
            yield "map", sx, sy, (in_t.elem, out_t.elem), (), _wrap_map
        ex = _table(
            ((a, i), b) for x, y in zip(xs, outs) for i, (a, b) in enumerate(zip(x, y))
        )
        if ex is not None and _has("zipwith", "range", "len") and "zip_pos" in names:
            sx = tuple(k[0] for k in ex)
            pos = (("$i",), INT, tuple(k[1] for k in ex))
            yield (
                "zip_pos",
                sx,
                tuple(ex.values()),
                (in_t.elem, out_t.elem),
                (pos,),
                _wrap_zip,
            )
    ks = {len(y) for y in outs}
    if len(ks) == 1 and _has("take") and "take" in names:
        (k,) = ks
        if all(len(x) >= k for x in xs) and any(len(x) > k for x in xs):
            sx = tuple(x[:k] for x in xs)
            yield "take", sx, outs, types, (), _wrap_in(("take", k, ("$in",)))
    if in_t == out_t and _has("append") and "append" in names:
        if all(y[: len(x)] == x for x, y in zip(xs, outs)):
            rest = tuple(y[len(x) :] for x, y in zip(xs, outs))
            if any(rest):
                yield "append_pre", xs, rest, types, (), _wrap_pre
        if all(
            len(y) >= len(x) and y[len(y) - len(x) :] == x for x, y in zip(xs, outs)
        ):
            rest = tuple(y[: len(y) - len(x)] for x, y in zip(xs, outs))
            if any(rest):
                yield "append_suf", xs, rest, types, (), _wrap_suf
    for op in ("transpose", "reverse"):
        if not _has(op) or "conj_" + op not in names:
            continue
        if op == "transpose" and not (
            isinstance(in_t.elem, ListT) and isinstance(out_t.elem, ListT)
        ):
            continue
        fn = PRIMS[op].fn
        try:
            sx, sy = tuple(map(fn, xs)), tuple(map(fn, outs))
        except Exception:
            continue
        if (sx, sy) != (xs, outs):
            yield "conj_" + op, sx, sy, types, (), _wrap_conj(op)


def _table(pairs) -> dict | None:
    """Input-key -> output dict in first-seen order; None on conflict/too few."""
    out: dict = {}
    for k, v in pairs:
        if out.setdefault(k, v) != v:
            return None
    return out if len(out) >= MIN_EXAMPLES else None


def _wrap_map(f: Program) -> Program | None:
    body = subst_leaves(f, {"$in": ("$0",)})
    return None if body is None else ("map", ("lam", 1, body), ("$in",))


def _wrap_zip(g: Program) -> Program | None:
    body = subst_leaves(g, {"$in": ("$0",), "$i": ("$1",)})
    if body is None:
        return None
    return ("zipwith", ("lam", 2, body), ("$in",), ("range", ("len", ("$in",))))


def _has(*names: str) -> bool:
    return all(n in PRIMS for n in names)


def _wrap_in(arg: Program):
    """Compose ``f`` after ``arg``: replace ``$in`` in ``f`` by ``arg``."""

    def build(f: Program) -> Program | None:
        return subst_leaves(f, {"$in": arg})

    return build


def _wrap_conj(op: str):
    """``op (f (op $in))`` for an involution ``op``."""

    def build(f: Program) -> Program | None:
        inner = subst_leaves(f, {"$in": (op, ("$in",))})
        return None if inner is None else (op, inner)

    return build


def _wrap_pre(r: Program) -> Program:
    return ("append", ("$in",), r)


def _wrap_suf(r: Program) -> Program:
    return ("append", r, ("$in",))
