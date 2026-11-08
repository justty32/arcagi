"""Operators and lambda-body pools for the enumerator.

A ``BodyPool`` enumerates lambda bodies for one parameter environment (the
concrete parameter types), smallest first, with body depth at most
``LAM_DEPTH`` (a leaf has depth 0, an application 1 + its deepest argument).
Bodies are deduplicated by their values on probe environments drawn from the
task's own data; bodies never contain nested lambdas.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from .interp import MAX_STEPS, Program, compile_prog, expand
from .library import Block, Library, free_vars
from .prims import PRIMS
from .types import INPUT, INT, FnT, Type, resolve, unify

LAM_DEPTH = 2
LAM_BODY_MAX = 4
# Commutative binary primitives: only one argument order is built.
COMMUTATIVE = frozenset({"add", "mul", "max", "min", "and", "or", "eq"})


class _Err:
    __slots__ = ()

    def __repr__(self) -> str:
        return "ERR"


ERR = _Err()


@dataclass(frozen=True)
class Op:
    name: str
    args: tuple[Type, ...]
    ret: Type
    fn: Callable[..., Any] | None
    block: Block | None
    visit: tuple[int, ...]  # argument visiting order: first-order args first
    lam_pos: tuple[bool, ...]
    comm: bool = False

    @property
    def arity(self) -> int:
        return len(self.args)


def _op(name: str, args: tuple[Type, ...], ret: Type, fn: Any, block: Any) -> Op:
    lam_pos = tuple(isinstance(a, FnT) for a in args)
    visit = tuple(i for i in range(len(args)) if not lam_pos[i]) + tuple(
        i for i in range(len(args)) if lam_pos[i]
    )
    comm = block is None and name in COMMUTATIVE
    return Op(name, args, ret, fn, block, visit, lam_pos, comm)


def build_ops(lib: Library, order: dict, bodies: bool) -> list[Op]:
    """Primitives and closed holed blocks, sorted by prior then table order."""
    ops = [_op(p.name, p.sig.args, p.sig.ret, p.fn, None) for p in PRIMS.values()]
    for b in lib.blocks:
        if b.holes and not free_vars(b.body):
            ops.append(_op(b.name, b.hole_types, b.ret, None, b))
    if bodies:
        ops = [o for o in ops if not any(o.lam_pos)]
    idx = {o.name: i for i, o in enumerate(ops)}
    return sorted(ops, key=lambda o: (-float(order.get(o.name, 0.0)), idx[o.name]))


def leaf_entries(
    lib: Library,
    xs: tuple,
    in_type: Type,
    consts: tuple[int, ...],
    run_expanded: Callable[[Program], tuple | None],
) -> Iterator[tuple[Program, Type, tuple]]:
    """Size-1 terms; blocks count as one node whatever their expanded size."""
    yield ("$in",), in_type, xs
    for c in consts:
        yield c, INT, (c,) * len(xs)
    for b in lib.blocks:
        if b.holes == 0 and not isinstance(b.sig, FnT) and not free_vars(b.body):
            vals = run_expanded(("blk", b.name))
            if vals is not None:
                yield ("blk", b.name), b.sig, vals


class LamEntry:
    __slots__ = ("prog", "node")

    def __init__(self, prog: Program, lib: Library) -> None:
        self.prog = prog
        self.node = compile_prog(expand(prog, lib))

    def bind(self, x: Any) -> Callable:
        return self.node([x, MAX_STEPS], ())


class _Body:
    __slots__ = ("prog", "typ", "vals", "depth", "seq")

    def __init__(
        self, prog: Program, typ: Type, vals: tuple, depth: int, seq: int
    ) -> None:
        self.prog, self.typ, self.vals, self.depth = prog, typ, vals, depth
        self.seq = seq


class BodyPool:
    def __init__(
        self,
        arg_types: tuple[Type, ...],
        lib: Library,
        probes: list,
        consts: tuple[int, ...],
        in_type: Type | None = INPUT,
    ) -> None:
        self.consts = consts
        self.in_type = in_type  # None: bodies cannot reference $in
        self.arg_types = arg_types
        self.n = len(arg_types)
        self.lib = lib
        self.probes = probes
        self.ops = build_ops(lib, {}, bodies=True)
        self.bank: list[dict[Type, list[_Body]]] = [{}]
        self.seen: set = set()
        self.lams: dict[int, list[tuple[Type, list[LamEntry]]]] = {}

    def lambdas(self, body_size: int) -> list[tuple[Type, list[LamEntry]]]:
        if body_size > LAM_BODY_MAX:
            return []
        got = self.lams.get(body_size)
        if got is None:
            while len(self.bank) <= body_size:
                self._grow(len(self.bank))
            got = []
            for typ, bodies in self.bank[body_size].items():
                lams = [LamEntry(("lam", self.n, b.prog), self.lib) for b in bodies]
                got.append((typ, lams))
            if body_size == 1:
                got += self._fn_blocks()
            self.lams[body_size] = got
        return got

    def _fn_blocks(self) -> list[tuple[Type, list[LamEntry]]]:
        out = []
        for b in self.lib.blocks:
            sig = b.sig
            if b.holes == 0 and isinstance(sig, FnT) and sig.args == self.arg_types:
                out.append((sig.ret, [LamEntry(("blk", b.name), self.lib)]))
        return out

    def _add(self, size: int, prog: Program, typ: Type, vals: tuple, d: int) -> None:
        if self.probes:
            if all(v is ERR for v in vals):
                return
            key = (typ, vals)
        else:
            key = (typ, prog)
        if key in self.seen:
            return
        self.seen.add(key)
        self.bank[size].setdefault(typ, []).append(
            _Body(prog, typ, vals, d, len(self.seen))
        )

    def _grow(self, size: int) -> None:
        self.bank.append({})
        pr = self.probes
        if size == 1:
            for k in range(self.n):
                self._add(
                    1, (f"${k}",), self.arg_types[k], tuple(a[k] for _, a in pr), 0
                )
            if self.in_type is not None:
                self._add(1, ("$in",), self.in_type, tuple(x for x, _ in pr), 0)
            for c in self.consts:
                self._add(1, c, INT, (c,) * len(pr), 0)
            return
        for op in self.ops:
            for comp in splits(size - 1, op.arity):
                if op.comm and comp[0] > comp[1]:
                    continue
                for subst, chosen in self._choose(op, comp, 0, {}, []):
                    if op.comm and comp[0] == comp[1] and chosen[0].seq > chosen[1].seq:
                        continue
                    d = 1 + max(c.depth for c in chosen)
                    progs = tuple(c.prog for c in chosen)
                    if op.block is None:
                        prog = (op.name, *progs)
                        vals = self._eval(op.fn, chosen)
                    else:
                        prog = ("blk", op.name, *progs)
                        vals = self._eval_block(prog)
                    self._add(size, prog, resolve(op.ret, subst), vals, d)

    def _choose(
        self, op: Op, comp: tuple[int, ...], i: int, subst: dict, chosen: list
    ) -> Iterator[tuple[dict, list]]:
        if i == op.arity:
            yield subst, chosen
            return
        want = resolve(op.args[i], subst)
        for typ, bodies in self.bank[comp[i]].items():
            s2 = unify(want, typ, subst)
            if s2 is None:
                continue
            for b in bodies:
                if b.depth >= LAM_DEPTH:
                    continue
                yield from self._choose(op, comp, i + 1, s2, [*chosen, b])

    def _eval(self, fn: Callable, chosen: list) -> tuple:
        out = []
        for j in range(len(self.probes)):
            args = [c.vals[j] for c in chosen]
            if any(a is ERR for a in args):
                out.append(ERR)
                continue
            try:
                out.append(fn(*args))
            except Exception:
                out.append(ERR)
        return tuple(out)

    def _eval_block(self, prog: Program) -> tuple:
        try:
            node = compile_prog(expand(prog, self.lib))
        except Exception:
            return (ERR,) * len(self.probes)
        out = []
        for x, a in self.probes:
            try:
                out.append(node([x, MAX_STEPS], a))
            except Exception:
                out.append(ERR)
        return tuple(out)


def splits(total: int, k: int) -> Iterator[tuple[int, ...]]:
    """Ordered ways to split ``total`` among ``k`` arguments, each at least 1."""
    if k <= 0:
        return
    if k == 1:
        if total >= 1:
            yield (total,)
        return
    for s in range(1, total - k + 2):
        for tail in splits(total - s, k - 1):
            yield (s, *tail)
