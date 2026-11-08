"""The whitelist of seed primitives: generic integer, boolean, sequence and
higher-order functions. Nothing here knows about any task domain.

Values: ``int``, ``bool`` and ``tuple`` (lists). Integer literals are program
leaves, not primitives: {0, 1, -1} plus every integer occurring in the task's
train inputs and outputs (``task_consts``). Generic resource caps keep
enumeration bounded:
lists longer than ``MAX_LEN`` or integers beyond ``MAX_INT`` raise
``OverflowLimitError``.
Partial functions (head of an empty list, nth out of range, mod by zero) raise
ordinary Python errors that the interpreter maps to ``EvalError``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from .types import BOOL, INT, FnT, parse

MAX_LEN = 1024
MAX_INT = 10**9
# Base integer literals; each task adds the integers seen in its train data
# (see ``task_consts``).
CONSTS: tuple[int, ...] = (0, 1, -1)


class OverflowLimitError(ArithmeticError):
    """A value exceeded the generic size caps."""


@dataclass(frozen=True)
class Prim:
    name: str
    sig: FnT
    fn: Callable[..., Any]

    @property
    def arity(self) -> int:
        return len(self.sig.args)


def _i(v: int) -> int:
    if -MAX_INT <= v <= MAX_INT:
        return v
    raise OverflowLimitError(v)


def _seq(v: tuple) -> tuple:
    if len(v) > MAX_LEN:
        raise OverflowLimitError(len(v))
    return v


def _nth(xs: tuple, i: int) -> Any:
    if i < 0:
        raise IndexError(i)
    return xs[i]


def _head(xs: tuple) -> Any:
    return xs[0]


def _last(xs: tuple) -> Any:
    return xs[-1]


def _take(n: int, xs: tuple) -> tuple:
    return xs[: max(n, 0)]


def _drop(n: int, xs: tuple) -> tuple:
    return xs[max(n, 0) :]


def _range(n: int) -> tuple:
    if n > MAX_LEN:
        raise OverflowLimitError(n)
    return tuple(range(max(n, 0)))


def _repeat(n: int, x: Any) -> tuple:
    if n > MAX_LEN:
        raise OverflowLimitError(n)
    return (x,) * max(n, 0)


def _concat(xss: tuple) -> tuple:
    if sum(len(xs) for xs in xss) > MAX_LEN:
        raise OverflowLimitError("concat")
    return tuple(x for xs in xss for x in xs)


def _transpose(xss: tuple) -> tuple:
    # List transposition that tolerates ragged input (as Haskell's Data.List).
    width = max((len(xs) for xs in xss), default=0)
    return tuple(tuple(xs[j] for xs in xss if j < len(xs)) for j in range(width))


def _fold(f: Callable, z: Any, xs: tuple) -> Any:
    acc = z
    for x in xs:
        acc = f(acc, x)
    return acc


def _if(c: bool, a: Any, b: Any) -> Any:
    return a if c else b


def _p(name: str, sig: str, fn: Callable[..., Any]) -> Prim:
    t = parse(sig)
    assert isinstance(t, FnT), name
    return Prim(name, t, fn)


_TABLE: list[Prim] = [
    # integers
    _p("add", "(int, int) -> int", lambda a, b: _i(a + b)),
    _p("sub", "(int, int) -> int", lambda a, b: _i(a - b)),
    _p("mul", "(int, int) -> int", lambda a, b: _i(a * b)),
    _p("neg", "(int) -> int", lambda a: -a),
    _p("mod", "(int, int) -> int", lambda a, b: a % b),
    _p("eq", "(a, a) -> bool", lambda a, b: a == b),
    _p("lt", "(int, int) -> bool", lambda a, b: a < b),
    _p("max", "(int, int) -> int", max),
    _p("min", "(int, int) -> int", min),
    # booleans
    _p("and", "(bool, bool) -> bool", lambda a, b: a and b),
    _p("or", "(bool, bool) -> bool", lambda a, b: a or b),
    _p("not", "(bool) -> bool", lambda a: not a),
    _p("if", "(bool, a, a) -> a", _if),
    # sequences
    _p("len", "(list[a]) -> int", len),
    _p("nth", "(list[a], int) -> a", _nth),
    _p("head", "(list[a]) -> a", _head),
    _p("last", "(list[a]) -> a", _last),
    _p("take", "(int, list[a]) -> list[a]", _take),
    _p("drop", "(int, list[a]) -> list[a]", _drop),
    _p("reverse", "(list[a]) -> list[a]", lambda xs: xs[::-1]),
    _p("cons", "(a, list[a]) -> list[a]", lambda x, xs: _seq((x, *xs))),
    _p("append", "(list[a], list[a]) -> list[a]", lambda xs, ys: _seq(xs + ys)),
    _p("concat", "(list[list[a]]) -> list[a]", _concat),
    _p("range", "(int) -> list[int]", _range),
    _p("repeat", "(int, a) -> list[a]", _repeat),
    _p("count", "(a, list[a]) -> int", lambda x, xs: xs.count(x)),
    _p("sort", "(list[a]) -> list[a]", lambda xs: tuple(sorted(xs))),
    # higher order
    _p("map", "((a) -> b, list[a]) -> list[b]", lambda f, xs: tuple(map(f, xs))),
    _p(
        "filter",
        "((a) -> bool, list[a]) -> list[a]",
        lambda f, xs: tuple(x for x in xs if f(x)),
    ),
    _p(
        "zipwith",
        "((a, b) -> c, list[a], list[b]) -> list[c]",
        lambda f, xs, ys: tuple(map(f, xs, ys)),
    ),
    _p("fold", "((b, a) -> b, b, list[a]) -> b", _fold),
    _p("transpose", "(list[list[a]]) -> list[list[a]]", _transpose),
]

PRIMS: dict[str, Prim] = {p.name: p for p in _TABLE}
assert len(PRIMS) <= 40


@contextmanager
def without(*names: str) -> Iterator[None]:
    """Temporarily remove primitives (ablation), e.g.::

        with seed.prims.without("transpose"):
            seed.enumerate(lib, tasks, budget, workers=4)

    Removal is global for the process (forked workers inherit it); programs
    using a removed primitive fail with ``EvalError`` meanwhile. Restored on exit.
    """
    unknown = [n for n in names if n not in PRIMS]
    if unknown:
        raise KeyError(f"unknown primitives: {unknown}")
    saved = dict(PRIMS)
    for n in names:
        del PRIMS[n]
    try:
        yield
    finally:
        PRIMS.clear()
        PRIMS.update(saved)


def task_consts(values: Iterable) -> tuple[int, ...]:
    """Sorted distinct integers of ``CONSTS`` and all ints nested in ``values``."""
    seen = set(CONSTS)
    stack = list(values)
    while stack:
        v = stack.pop()
        if isinstance(v, (tuple, list)):
            stack.extend(v)
        elif isinstance(v, int) and not isinstance(v, bool):
            seen.add(v)
    return tuple(sorted(seen))


__all__ = [
    "BOOL",
    "CONSTS",
    "task_consts",
    "without",
    "INT",
    "MAX_INT",
    "MAX_LEN",
    "PRIMS",
    "OverflowLimitError",
    "Prim",
]
