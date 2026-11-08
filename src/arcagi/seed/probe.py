"""Probe environments for lambda body pools: argument values drawn from the
enumerator's own bank of small terms (so from the task's data), plus the base
integer and boolean constants."""

from __future__ import annotations

from typing import Any

from .prims import CONSTS
from .types import BOOL, INT, ListT, Type


def probes(
    bank: list, xs: tuple, arg_types: tuple[Type, ...]
) -> list[tuple[Any, tuple]]:
    """(input, argument tuple) environments for lambdas of ``arg_types``."""
    per = [_values(bank, xs, t) for t in arg_types]
    if any(not p for p in per):
        return []
    if len(per) == 1:
        return [(x, (v,)) for v, x in per[0]]
    a, b = per
    n = max(len(a), len(b))
    out = [(a[i % len(a)][1], (a[i % len(a)][0], b[i % len(b)][0])) for i in range(n)]
    out += [(x, (u, v)) for u, x in a[:3] for v, _ in b[:3]]
    return out


def _values(bank: list, xs: tuple, t: Type, cap: int = 10) -> list[tuple[Any, Any]]:
    seen: set = set()
    out: list[tuple[Any, Any]] = []

    def add(v: Any, x: Any) -> None:
        k = (type(v), v)
        if k not in seen and len(out) < cap:
            seen.add(k)
            out.append((v, x))

    for size in range(1, min(4, len(bank))):
        for e in bank[size].get(t, ()):
            for v, x in zip(e.vals, xs, strict=True):
                add(v, x)
        for e in bank[size].get(ListT(t), ()):
            for vs, x in zip(e.vals, xs, strict=True):
                for v in vs[:6]:
                    add(v, x)
    extra: tuple = CONSTS if t == INT else ((True, False) if t == BOOL else ())
    for v in extra:
        add(v, xs[0])
    return out
