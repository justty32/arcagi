"""Conditional witness: after a direct search fails, combine banked terms into
``if c t e`` where ``e`` is right on some examples, ``t`` right on all the
others, and the banked boolean ``c`` is true exactly where ``t`` is needed and
false wherever ``t`` is wrong. Pure list/int/bool semantics.
"""

from __future__ import annotations

from .enum import Enumerator
from .interp import Program
from .types import BOOL

MAX_ELSE = 12


def _hits(vals: tuple, want: tuple) -> int:
    m = 0
    for j, (a, b) in enumerate(zip(vals, want, strict=True)):
        if a == b:
            m |= 1 << j
    return m


def cond_witness(en: Enumerator, limit: int) -> tuple[Program | None, int]:
    """Return (program or None, nodes used); one node per (c, t, e) built."""
    n = len(en.outs)
    full = (1 << n) - 1
    outs = []
    bools: list[tuple[int, Program]] = []
    for level in en.bank:
        for e in level.get(en.out_type, ()):
            m = _hits(e.vals, en.outs)
            if m:
                outs.append((m, e.prog))
        for e in level.get(BOOL, ()):
            bm = 0
            for j, v in enumerate(e.vals):
                if v is True:
                    bm |= 1 << j
            if 0 < bm < full:
                bools.append((bm, e.prog))
    # else-branch candidates: highest coverage first, then smallest (bank order)
    elses = sorted(range(len(outs)), key=lambda i: (-bin(outs[i][0]).count("1"), i))
    used = 0
    for i in elses[:MAX_ELSE]:
        me, pe = outs[i]
        need = full & ~me
        for mt, pt in outs:
            if mt & need != need or pt == pe:
                continue
            wrong_t = full & ~mt
            used += 1
            if used > limit:
                return None, limit
            for bm, pc in bools:
                if bm & need == need and bm & wrong_t == 0:
                    return ("if", pc, pt, pe), used
    return None, used
