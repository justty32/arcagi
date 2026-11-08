"""The ``halves`` split for ``seed.decomp``: cut each input list at a point
``k`` derived from list lengths, solve for the pieces and rebuild the whole.

Cut points: for every train pair with ``n = len(x)``, candidate formulas
``n // 2``, ``(n + 1) // 2``, ``len(y)``, ``n - len(y)`` and ``len(y) // 2``
give one ``k`` per pair. A candidate is kept only when every pair has
``1 <= k < n`` and the vector of ``k`` is expressible from the input alone: a
constant (literal), ``n - c`` (``sub (len $in) c``) or half of ``n``
(``len (filter (lam (eq (mod $0 2) r)) (range (len $in)))``, which counts the
indices below ``n`` of a given parity). Writing ``L = take k $in``, ``R = drop
k $in`` and ``T = drop (n - k) $in`` (the last ``k`` elements):

* ``halves_map``: ``y = y1 ++ y2`` with equal halves, ``g L = y1`` and
  ``g T = y2`` for one program ``g`` -> ``append (g L) (g T)``.
* ``halves_out``: ``y = y1 ++ y2`` (``len y1 = len y // 2``), each half found
  separately from ``$in`` plus leaves ``$u = L`` and ``$v = R``.
* ``halves_zip``: ``y = zipwith h L T``; ``h`` is found from the element triples, or
  (``halves_zip2``) elementwise when those elements are lists of equal lengths, giving
  ``zipwith (lam (zipwith (lam h') $0 $1)) L T``.

Only list length, take, drop, append and zipwith semantics are used.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .interp import Program
from .prims import PRIMS
from .types import ListT
from .witness import subst_leaves

MAX_CUTS = 2
MIN_EXAMPLES = 2
IN = ("$in",)


@dataclass(frozen=True)
class Part:
    """One subproblem: examples, (input, output) types and extra leaves.
    ``recurse``: solved by the recursive solver (no extra leaves allowed);
    otherwise by direct search. ``free``: ``$in`` keeps its meaning (the
    part's inputs are the parent's), so lambdas may use it when the parent's
    may."""

    xs: tuple
    outs: tuple
    types: tuple
    extra: tuple = ()
    recurse: bool = False
    free: bool = False


@dataclass(frozen=True)
class MultiSplit:
    name: str
    parts: tuple[Part, ...]
    build: Callable[[list[Program]], Program | None]


def _half(parity: int) -> Program:
    """Number of indices below ``len $in`` with the given parity: parity 1
    gives ``n // 2``, parity 0 gives ``(n + 1) // 2``."""
    test = ("eq", ("mod", ("$0",), 2), parity)
    return ("len", ("filter", ("lam", 1, test), ("range", ("len", IN))))


def _int_expr(ks: tuple[int, ...], ns: tuple[int, ...]) -> Program | None:
    if len(set(ks)) == 1:
        return ks[0]
    if len({n - k for n, k in zip(ns, ks)}) == 1:
        return ("sub", ("len", IN), ns[0] - ks[0])
    if all(k == n // 2 for n, k in zip(ns, ks)):
        return _half(1)
    if all(k == (n + 1) // 2 for n, k in zip(ns, ks)):
        return _half(0)
    return None


def cuts(xs: tuple, outs: tuple) -> list[tuple[tuple[int, ...], Program, Program]]:
    """Up to ``MAX_CUTS`` (ks, k program, n - k program), first-found order."""
    ns = tuple(len(x) for x in xs)
    forms = (
        lambda n, y: n // 2,
        lambda n, y: (n + 1) // 2,
        lambda n, y: len(y),
        lambda n, y: n - len(y),
        lambda n, y: len(y) // 2,
    )
    out: list = []
    seen: set = set()
    for f in forms:
        ks = tuple(f(n, y) for n, y in zip(ns, outs))
        if ks in seen or not all(1 <= k < n for n, k in zip(ns, ks)):
            continue
        seen.add(ks)
        kp = _int_expr(ks, ns)
        tp = _int_expr(tuple(n - k for n, k in zip(ns, ks)), ns)
        if kp is not None and tp is not None:
            out.append((ks, kp, tp))
            if len(out) == MAX_CUTS:
                break
    return out


def _table(pairs) -> dict | None:
    out: dict = {}
    for k, v in pairs:
        if out.setdefault(k, v) != v:
            return None
    return out if len(out) >= MIN_EXAMPLES else None


def halves_splits(xs: tuple, outs: tuple, types: tuple) -> Iterator[MultiSplit]:
    in_t, out_t = types
    if not isinstance(in_t, ListT) or not isinstance(out_t, ListT):
        return
    if not all(isinstance(x, tuple) and isinstance(y, tuple) for x, y in zip(xs, outs)):
        return
    if not all(n in PRIMS for n in ("take", "drop", "len", "append", "zipwith")):
        return
    for ks, kp, tp in cuts(xs, outs):
        lo = tuple(x[:k] for x, k in zip(xs, ks))
        hi = tuple(x[k:] for x, k in zip(xs, ks))
        tail = tuple(x[len(x) - k :] for x, k in zip(xs, ks))
        lp, rp, tpp = ("take", kp, IN), ("drop", kp, IN), ("drop", tp, IN)
        yield from _same(lo, tail, outs, types, lp, tpp)
        yield from _out(xs, lo, hi, outs, types, lp, rp)
        yield from _zip(lo, tail, ks, outs, types, lp, tpp)


def _same(lo, tail, outs, types, lp, tpp) -> Iterator[MultiSplit]:
    if not all(len(y) % 2 == 0 for y in outs):
        return
    y1 = tuple(y[: len(y) // 2] for y in outs)
    y2 = tuple(y[len(y) // 2 :] for y in outs)

    def build(subs: list[Program]) -> Program | None:
        a = subst_leaves(subs[0], {"$in": lp})
        b = subst_leaves(subs[0], {"$in": tpp})
        return None if a is None or b is None else ("append", a, b)

    part = Part(lo + tail, y1 + y2, types, recurse=True)
    yield MultiSplit("halves_map", (part,), build)


def _out(xs, lo, hi, outs, types, lp, rp) -> Iterator[MultiSplit]:
    if not all(len(y) >= 2 for y in outs):
        return
    in_t = types[0]
    extra = ((("$u",), in_t, lo), (("$v",), in_t, hi))
    y1 = tuple(y[: len(y) // 2] for y in outs)
    y2 = tuple(y[len(y) // 2 :] for y in outs)
    repl = {"$u": lp, "$v": rp}

    def build(subs: list[Program]) -> Program | None:
        a, b = (subst_leaves(s, repl) for s in subs)
        return None if a is None or b is None else ("append", a, b)

    parts = (
        Part(xs, y1, types, extra, free=True),
        Part(xs, y2, types, extra, free=True),
    )
    yield MultiSplit("halves_out", parts, build)


def _zip(lo, tail, ks, outs, types, lp, tpp) -> Iterator[MultiSplit]:
    if not all(len(y) == k for y, k in zip(outs, ks)):
        return
    in_t, out_t = types
    trips = [(a, b, c) for p, q, y in zip(lo, tail, outs) for a, b, c in zip(p, q, y)]
    ex = _table(((a, b), c) for a, b, c in trips)
    if ex is not None:
        keys = tuple(ex)
        extra = ((("$v",), in_t.elem, tuple(k[1] for k in keys)),)
        part = Part(
            tuple(k[0] for k in keys),
            tuple(ex.values()),
            (in_t.elem, out_t.elem),
            extra,
        )
        yield MultiSplit("halves_zip", (part,), _wrap_zip(lp, tpp, 1))
    if not (isinstance(in_t.elem, ListT) and isinstance(out_t.elem, ListT)):
        return
    if not all(
        isinstance(a, tuple)
        and isinstance(b, tuple)
        and isinstance(c, tuple)
        and len(a) == len(b) == len(c)
        for a, b, c in trips
    ):
        return
    ex = _table(((u, v), w) for a, b, c in trips for u, v, w in zip(a, b, c))
    if ex is None:
        return
    keys = tuple(ex)
    et = in_t.elem.elem
    extra = ((("$v",), et, tuple(k[1] for k in keys)),)
    part = Part(
        tuple(k[0] for k in keys), tuple(ex.values()), (et, out_t.elem.elem), extra
    )
    yield MultiSplit("halves_zip2", (part,), _wrap_zip(lp, tpp, 2))


def _wrap_zip(lp: Program, tpp: Program, levels: int):
    def build(subs: list[Program]) -> Program | None:
        body = subst_leaves(subs[0], {"$in": ("$0",), "$v": ("$1",)})
        if body is None:
            return None
        fn: Program = ("lam", 2, body)
        for _ in range(levels - 1):
            fn = ("lam", 2, ("zipwith", fn, ("$0",), ("$1",)))
        return ("zipwith", fn, lp, tpp)

    return build


__all__ = ["MultiSplit", "Part", "cuts", "halves_splits"]
