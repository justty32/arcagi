"""Generic deductive splits for the seed enumerator (witness functions in the
style of lambda^2 and programming by example), using only list and integer
semantics.

A problem is a set of (input value, output value) examples. Besides direct
enumeration, ``solve_split`` tries these splits, solves the subproblem with
the same machinery (sharing one node budget) and rebuilds a full program:

* ``map``: equal-length list pairs where equal input elements always give
  equal output elements -> find ``f`` with ``f(x[i]) = y[i]``; result
  ``map (lam f) $in``. Recursing once more yields ``map (lam map (lam g))``.
* ``zip_pos``: equal-length list pairs where ``y[i]`` is a function of
  ``(x[i], i)`` -> find ``g`` over ``$in`` and a position leaf ``$i``; result
  ``zipwith (lam2 g) $in (range (len $in))``.
* ``if`` (``seed.cond``, subproblems only): combine banked terms into
  ``if c t e`` when no single term fits all examples.
* ``append``: the output starts (or ends) with the input -> solve for the
  other part; result ``append $in r`` (or ``append r $in``).

Subproblem programs mention ``$in`` (and ``$i``) only outside lambdas, so
substituting the enclosing lambda parameters for them is exact.
"""

from __future__ import annotations

from typing import Any

from .cond import cond_witness
from .enum import Enumerator, search
from .interp import Program, expand, run, to_value
from .library import Library, free_vars, hole_count
from .types import INPUT, INT, ListT

PROBE = 0.05  # share of a problem's budget for a first direct search
SPLIT = 0.6  # share for all splits together (the rest: final direct search)
MAX_DEPTH = 2
MIN_EXAMPLES = 2
COND = 0.2  # share of a subproblem's direct budget for the conditional witness
MIN_COND = 3


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


def _hole_under_lambda(p: Program, depth: int = 0) -> bool:
    if isinstance(p, int):
        return False
    if len(p) == 1:
        return depth > 0 and hole_count(p) > 0
    if p[0] == "lam":
        return _hole_under_lambda(p[2], depth + 1)
    kids = p[2:] if p[0] == "blk" else p[1:]
    return any(_hole_under_lambda(k, depth) for k in kids)


def _uses_input(p: Program) -> bool:
    if isinstance(p, int):
        return False
    if len(p) == 1:
        return p[0] == "$in"
    kids = p[2:] if p[0] in ("lam", "blk") else p[1:]
    return any(_uses_input(k) for k in kids)


def sub_library(lib: Library) -> Library:
    """Blocks safe inside subproblems: no ``$in`` and no hole under a lambda."""
    keep = []
    for b in lib.blocks:
        try:
            body = expand(b.body, lib)
        except Exception:
            continue
        if not _uses_input(body) and not _hole_under_lambda(body):
            if not free_vars(body):
                keep.append(b)
    return Library(keep)


class _Solver:
    def __init__(self, lib: Library, order: dict | None, budget: int) -> None:
        self.lib, self.sublib, self.order = lib, sub_library(lib), order
        self.budget = budget
        self.spent = 0
        self.first: int | None = None
        self.near: list = []

    def _direct(
        self,
        xs: tuple,
        outs: tuple,
        types: tuple,
        budget: int,
        free: bool,
        top: bool = False,
        extra: tuple = (),
    ) -> Program | None:
        """``free``: ``$in`` may appear under lambdas (no substitution later)."""
        budget = min(budget, self.budget - self.spent)
        if budget <= 0:
            return None
        sub = not free
        use_cond = len(xs) >= MIN_COND
        en = Enumerator(
            list(zip(xs, outs, strict=True)),
            self.sublib if sub else self.lib,
            int(budget * (1 - COND)) if use_cond else budget,
            self.order,
            in_type=types[0],
            out_type=types[1],
            extra=extra,
            sub=sub,
        )
        search(en)
        if en.found is not None:
            self.first = self.spent + (en.nodes_to_first or en.nodes)
        self.spent += en.nodes
        if en.found is None and use_cond:
            prog, used = cond_witness(en, budget - en.nodes)
            self.spent += used
            if prog is not None:
                self.first = self.spent
                return prog
        if top and len(en.near) >= len(self.near):
            self.near = [(p, sc) for sc, _, p in sorted(en.near, reverse=True)]
        return en.found

    def solve(
        self,
        xs: tuple,
        outs: tuple,
        types: tuple,
        depth: int,
        budget: int,
        free: bool = False,
        top: bool = False,
    ) -> Program | None:
        start = self.spent
        if depth <= 0:
            return self._direct(xs, outs, types, budget, free, top)
        prog = self._direct(xs, outs, types, int(budget * PROBE), free, top)
        if prog is not None:
            return prog
        splits = list(self._splits(xs, outs, types))
        for name, sub_xs, sub_outs, sub_types, extra, build in splits:
            share = int(budget * SPLIT / len(splits))
            if name == "zip_pos":
                sub = self._direct(
                    sub_xs, sub_outs, sub_types, share, False, extra=extra
                )
            else:
                keep = free and name.startswith("append")
                sub = self.solve(sub_xs, sub_outs, sub_types, depth - 1, share, keep)
            if sub is None:
                continue
            whole = build(sub)
            if whole is not None and self._check(whole, xs, outs):
                return whole
            self.first = None
        rest = budget - (self.spent - start)
        return self._direct(xs, outs, types, rest, free, top)

    def _check(self, prog: Program, xs: tuple, outs: tuple) -> bool:
        try:
            return all(run(prog, x, self.lib) == y for x, y in zip(xs, outs))
        except Exception:
            return False

    def _splits(self, xs: tuple, outs: tuple, types: tuple):
        in_t, out_t = types
        lists = all(
            isinstance(x, tuple) and isinstance(y, tuple) for x, y in zip(xs, outs)
        )
        if not lists or not isinstance(in_t, ListT) or not isinstance(out_t, ListT):
            return
        same_len = all(len(x) == len(y) for x, y in zip(xs, outs))
        if same_len:
            ex = _table(((a,), b) for x, y in zip(xs, outs) for a, b in zip(x, y))
            if ex is not None:
                sx, sy = tuple(k[0] for k in ex), tuple(ex.values())
                yield "map", sx, sy, (in_t.elem, out_t.elem), (), _wrap_map
            ex = _table(
                ((a, i), b)
                for x, y in zip(xs, outs)
                for i, (a, b) in enumerate(zip(x, y))
            )
            if ex is not None:
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
        if in_t == out_t:
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


def _wrap_pre(r: Program) -> Program:
    return ("append", ("$in",), r)


def _wrap_suf(r: Program) -> Program:
    return ("append", r, ("$in",))


def solve_split(
    train: list[tuple[Any, Any]], lib: Library, budget: int, order: dict | None
) -> tuple[Program | None, int, int | None, list]:
    """Return (program, nodes spent, nodes to first solution, near list)."""
    xs = tuple(to_value(i) for i, _ in train)
    outs = tuple(to_value(o) for _, o in train)
    st = _Solver(lib, order, budget)
    prog = st.solve(xs, outs, (INPUT, INPUT), MAX_DEPTH, budget, True, True)
    return prog, st.spent, st.first if prog is not None else None, st.near
