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
from .prims import task_consts
from .probe import probes
from .types import INPUT, FnT, Type, is_ground, resolve, unify

MAX_SIZE = 24
NEAR_KEEP = 8


@dataclass
class Result:
    program: Program | None
    nodes: int
    nodes_to_first: int | None
    seconds: float
    near: list[tuple[Program, float]] = field(default_factory=list)
    eval_steps: int = 0  # approximate interpreter work (see Enumerator.steps)


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
        lam_depth: int | None = None,
        lam_body_max: int | None = None,
    ) -> None:
        """``sub``: a decomposition subproblem; lambda bodies then cannot see
        ``$in`` and no near list is kept. ``extra``: more (prog, type, vals)
        leaves, e.g. a position variable. ``consts``: integer leaves (default:
        ``task_consts`` of these examples). ``lam_depth``/``lam_body_max``:
        lambda body pool limits (None: ``seed.lam`` defaults)."""
        self.lam_depth, self.lam_body_max = lam_depth, lam_body_max
        self._steps = 0
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

    @property
    def steps(self) -> int:
        """Approximate evaluation work: primitive applications on train
        examples and lambda probes, plus interpreter steps of expanded runs
        (calls of lambda arguments inside higher-order primitives are not
        counted)."""
        return self._steps + sum(p.steps for p in self.pools.values())

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
        out = []
        try:
            node = compile_prog(expand(prog, self.lib))
            for x in self.xs:
                ctx = [x, MAX_STEPS]
                try:
                    out.append(node(ctx, ()))
                finally:
                    self._steps += MAX_STEPS - ctx[1]
        except Exception:
            return None
        return tuple(out)

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
        self._steps += len(self.xs)
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
                probes(self.bank, self.xs, arg_types),
                self.consts,
                None if self.sub else self.in_type,
                self.lam_depth,
                self.lam_body_max,
            )
            self.pools[arg_types] = pool
        return pool


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
    decompose: bool | frozenset[str] = True,
    sub_lam_depth: int | None = None,
) -> Result:
    """Search for the smallest program mapping every train input to its output.

    With ``decompose`` (default) the budget is shared between direct search and
    generic deductive splits (``seed.decomp``). ``True`` means
    ``seed.decomp.DEFAULT_SPLITS``, a frozenset turns on exactly the named
    splits (``seed.decomp.SPLITS``); ``False`` or an empty set is the plain
    bottom-up enumerator. ``sub_lam_depth``: lambda body depth limit inside
    split subproblems (None: ``seed.lam.LAM_DEPTH``, or ``NEST_DEPTH`` when
    ``nest`` is on). Every node of every subsearch, failed ones included, counts against
    ``budget_nodes``."""
    from .decomp import normalize, solve_split

    t0 = time.perf_counter()
    names = normalize(decompose)
    if names:
        prog, nodes, first, near, steps = solve_split(
            train, lib, budget_nodes, order, names, sub_lam_depth
        )
        return Result(prog, nodes, first, time.perf_counter() - t0, near, steps)
    en = search(Enumerator(train, lib, budget_nodes, order))
    near = [(p, sc) for sc, _, p in sorted(en.near, reverse=True)]
    secs = time.perf_counter() - t0
    return Result(en.found, en.nodes, en.nodes_to_first, secs, near, en.steps)
