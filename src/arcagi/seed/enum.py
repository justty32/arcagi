"""Size-ordered, type-directed bottom-up enumeration with observational
equivalence.

Ground terms (no lambda parameters) are built smallest first. Each candidate is
evaluated on all train inputs at once by applying the primitive to the cached
argument values; candidates whose train outputs collide with an earlier one of
the same type are dropped. A node is one candidate built (and evaluated).

Lambda arguments come from per-environment body pools (``lam.BodyPool``).
Library blocks act as primitives; their applications are evaluated by
expanding the block, so holes keep syntactic substitution semantics.
"""

from __future__ import annotations

import heapq
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .interp import MAX_STEPS, Program, compile_prog, expand, to_value
from .lam import BodyPool, Op, build_ops, leaf_entries, splits
from .library import Library
from .prims import CONSTS, task_consts
from .types import BOOL, INPUT, INT, FnT, ListT, Type, is_ground, resolve, unify

MAX_SIZE = 24
NEAR_KEEP = 8


@dataclass
class Result:
    program: Program | None
    nodes: int
    nodes_to_first: int | None
    seconds: float
    near: list[tuple[Program, float]] = field(default_factory=list)


class _DoneError(Exception):
    pass


class _Entry:
    __slots__ = ("prog", "typ", "vals", "seq")

    def __init__(self, prog: Program, typ: Type, vals: tuple, seq: int) -> None:
        self.prog, self.typ, self.vals, self.seq = prog, typ, vals, seq


def elem_score(got: Any, want: Any) -> float:
    """Fraction of equal entries when both are equal-length lists of lists."""
    if not isinstance(got, tuple) or len(got) != len(want):
        return 0.0
    hit = tot = 0
    for g, w in zip(got, want, strict=True):
        if not isinstance(g, tuple) or len(g) != len(w):
            return 0.0
        tot += len(w)
        hit += sum(a == b for a, b in zip(g, w, strict=True))
    return hit / tot if tot else 1.0


class Enumerator:
    def __init__(
        self,
        train: list[tuple[Any, Any]],
        lib: Library,
        budget_nodes: int,
        order: dict | None = None,
        in_type: Type = INPUT,
        out_type: Type = INPUT,
        extra: tuple = (),
        sub: bool = False,
        consts: tuple[int, ...] | None = None,
    ) -> None:
        """``sub``: a decomposition subproblem; lambda bodies then cannot see
        ``$in`` and no near list is kept. ``extra``: more (prog, type, vals)
        leaves, e.g. a position variable. ``consts``: integer leaves (default:
        ``task_consts`` of these examples)."""
        self.xs = tuple(to_value(i) for i, _ in train)
        self.outs = tuple(to_value(o) for _, o in train)
        if consts is None:
            consts = task_consts((*self.xs, *self.outs))
        self.consts = consts
        self.in_type, self.out_type = in_type, out_type
        self.extra, self.sub = extra, sub
        self.lib = lib
        self.budget = budget_nodes
        self.nodes = 0
        self.found: Program | None = None
        self.nodes_to_first: int | None = None
        self.seen: set[tuple] = set()
        self.bank: list[dict[Type, list[_Entry]]] = [{}]
        self.near: list[tuple[float, int, Program]] = []
        self.ops: list[Op] = build_ops(lib, order or {}, bodies=False)
        self.pools: dict[tuple[Type, ...], BodyPool] = {}

    # -- bookkeeping -------------------------------------------------------
    def _offer(self, size: int, prog: Program, typ: Type, vals: tuple) -> None:
        self.nodes += 1
        key = (typ, vals)
        if key not in self.seen:
            self.seen.add(key)
            self.bank[size].setdefault(typ, []).append(
                _Entry(prog, typ, vals, len(self.seen))
            )
            if typ == self.out_type and vals == self.outs:
                self.found = prog
                self.nodes_to_first = self.nodes
                raise _DoneError
            if typ == INPUT and not self.sub:
                sc = sum(map(elem_score, vals, self.outs)) / len(self.outs)
                item = (sc, -self.nodes, prog)
                if len(self.near) < NEAR_KEEP:
                    heapq.heappush(self.near, item)
                elif item > self.near[0]:
                    heapq.heapreplace(self.near, item)
        if self.nodes >= self.budget:
            raise _DoneError

    def _run_expanded(self, prog: Program) -> tuple | None:
        try:
            node = compile_prog(expand(prog, self.lib))
            return tuple(node([x, MAX_STEPS], ()) for x in self.xs)
        except Exception:
            return None

    # -- search ------------------------------------------------------------
    def run(self) -> None:
        self.bank.append({})
        for prog, typ, vals in leaf_entries(
            self.lib, self.xs, self.in_type, self.consts, self._run_expanded
        ):
            self._offer(1, prog, typ, vals)
        for prog, typ, vals in self.extra:
            self._offer(1, prog, typ, vals)
        for size in range(2, MAX_SIZE + 1):
            self.bank.append({})
            for op in self.ops:
                for comp in splits(size - 1, op.arity):
                    if op.comm and comp[0] > comp[1]:
                        continue
                    self._apply(size, op, comp)

    def _apply(self, size: int, op: Op, comp: tuple[int, ...]) -> None:
        for subst, chosen in self._choose(op, comp, 0, {}, [None] * op.arity):
            if op.comm and comp[0] == comp[1] and chosen[0].seq > chosen[1].seq:
                continue
            ret = resolve(op.ret, subst)
            if op.block is None:
                vals = self._eval_prim(op, chosen)
            else:
                vals = self._run_expanded(("blk", op.name, *(c.prog for c in chosen)))
            if vals is not None:
                prog = (
                    (op.name, *(c.prog for c in chosen))
                    if op.block is None
                    else ("blk", op.name, *(c.prog for c in chosen))
                )
                self._offer(size, prog, ret, vals)
            else:
                self.nodes += 1
                if self.nodes >= self.budget:
                    raise _DoneError

    def _eval_prim(self, op: Op, chosen: list) -> tuple | None:
        fn = op.fn
        out = []
        try:
            for j, x in enumerate(self.xs):
                args = []
                for c in chosen:
                    if isinstance(c, _Entry):
                        args.append(c.vals[j])
                    else:
                        args.append(c.bind(x))
                out.append(fn(*args))
        except Exception:
            return None
        return tuple(out)

    def _choose(
        self, op: Op, comp: tuple[int, ...], i: int, subst: dict, chosen: list
    ) -> Iterator[tuple[dict, list]]:
        if i == op.arity:
            yield subst, chosen
            return
        pos = op.visit[i]
        want = resolve(op.args[pos], subst)
        sz = comp[pos]
        if isinstance(want, FnT):
            pool = self._pool(want.args)
            if pool is None:
                return
            for typ, lams in pool.lambdas(sz):
                s2 = unify(want.ret, typ, subst)
                if s2 is None:
                    continue
                for lam in lams:
                    chosen[pos] = lam
                    yield from self._choose(op, comp, i + 1, s2, chosen)
            return
        for typ, entries in self.bank[sz].items():
            s2 = unify(want, typ, subst)
            if s2 is None:
                continue
            for e in entries:
                chosen[pos] = e
                yield from self._choose(op, comp, i + 1, s2, chosen)

    def _pool(self, arg_types: tuple[Type, ...]) -> BodyPool | None:
        if any(not is_ground(t) for t in arg_types):
            return None
        pool = self.pools.get(arg_types)
        if pool is None:
            pool = BodyPool(
                arg_types,
                self.lib,
                self._probes(arg_types),
                self.consts,
                None if self.sub else self.in_type,
            )
            self.pools[arg_types] = pool
        return pool

    def _probes(self, arg_types: tuple[Type, ...]) -> list[tuple[Any, tuple]]:
        per = [self._probe_values(t) for t in arg_types]
        if any(not p for p in per):
            return []
        if len(per) == 1:
            return [(x, (v,)) for v, x in per[0]]
        a, b = per
        n = max(len(a), len(b))
        out = [
            (a[i % len(a)][1], (a[i % len(a)][0], b[i % len(b)][0])) for i in range(n)
        ]
        out += [(x, (u, v)) for u, x in a[:3] for v, _ in b[:3]]
        return out

    def _probe_values(self, t: Type, cap: int = 10) -> list[tuple[Any, Any]]:
        seen: set = set()
        out: list[tuple[Any, Any]] = []

        def add(v: Any, x: Any) -> None:
            k = (type(v), v)
            if k not in seen and len(out) < cap:
                seen.add(k)
                out.append((v, x))

        for size in range(1, min(4, len(self.bank))):
            for e in self.bank[size].get(t, ()):
                for v, x in zip(e.vals, self.xs, strict=True):
                    add(v, x)
            for e in self.bank[size].get(ListT(t), ()):
                for vs, x in zip(e.vals, self.xs, strict=True):
                    for v in vs[:6]:
                        add(v, x)
        extra: tuple = CONSTS if t == INT else ((True, False) if t == BOOL else ())
        for v in extra:
            add(v, self.xs[0])
        return out


def search(en: Enumerator) -> Enumerator:
    """Run an enumerator until it finds a program or spends its budget."""
    try:
        en.run()
    except _DoneError:
        pass
    return en


def solve(
    train: list[tuple[Any, Any]],
    lib: Library,
    budget_nodes: int,
    order: dict | None = None,
    decompose: bool = True,
) -> Result:
    """Search for the smallest program mapping every train input to its output.

    With ``decompose`` (default) the budget is shared between direct search and
    generic deductive splits (``seed.decomp``); ``decompose=False`` is the plain
    bottom-up enumerator."""
    t0 = time.perf_counter()
    if decompose:
        from .decomp import solve_split

        prog, nodes, first, near = solve_split(train, lib, budget_nodes, order)
        return Result(prog, nodes, first, time.perf_counter() - t0, near)
    en = search(Enumerator(train, lib, budget_nodes, order))
    near = [(p, sc) for sc, _, p in sorted(en.near, reverse=True)]
    return Result(en.found, en.nodes, en.nodes_to_first, time.perf_counter() - t0, near)
