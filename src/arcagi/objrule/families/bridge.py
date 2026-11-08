"""Bridges: join same-colored aligned objects with a band of color.

``bridge(grid, conn, axes, mode, fill)``: for every object ``a`` and each
direction of ``axes`` (``h``: right, ``v``: down, ``hv`` / ``vh``: both, the
second axis painted last), the nearest other object ``b`` of ``a``'s color
whose box shares rows (``h``) or columns (``v``) with ``a`` is joined: the band
of shared rows / columns strictly between the two boxes is painted on its
background cells with ``fill`` (``-1``: ``a``'s color). ``mode == "stop"``
skips a pair whose band holds any non-background cell; ``"pass"`` paints
around such cells (grid lines, other objects).

Fitting: ``fill`` is the target color of the band cells of the first joined
pair; anti-memorization needs >= ``keyed.MIN_OBJECTS`` joined pairs over the
train pairs, and the candidate must reproduce every train pair.
"""

from collections.abc import Sequence

from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import Obj
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import keyed, scope

AXES = {"h": ("h",), "v": ("v",), "hv": ("h", "v"), "vh": ("v", "h")}
MODES = ("stop", "pass")
MAX_OBJECTS = 40


def _box(o: Obj) -> tuple[int, int, int, int]:
    top, left, h, w = g.cells_bbox(list(o.cells))
    return top, left, top + h - 1, left + w - 1


def _band(a: Obj, b: Obj, axis: str) -> list[tuple[int, int]] | None:
    """Cells strictly between ``a`` and a later ``b`` along ``axis``, or None."""
    at, al, ab, ar = _box(a)
    bt, bl, bb, br = _box(b)
    if axis == "h":
        lo, hi = max(at, bt), min(ab, bb)
        if lo > hi or bl <= ar:
            return None
        return [(y, x) for y in range(lo, hi + 1) for x in range(ar + 1, bl)]
    lo, hi = max(al, bl), min(ar, br)
    if lo > hi or bt <= ab:
        return None
    return [(y, x) for y in range(ab + 1, bt) for x in range(lo, hi + 1)]


def pairs(grid: Grid, conn: str, axis: str, mode: str):
    """``(a, band)`` per joined pair along ``axis``."""
    bg = scope.background(grid, conn)
    objs = scope.objects(grid, conn)
    out = []
    for a in objs:
        best = None
        for b in objs:
            if b is a or b.props["color"] != a.props["color"]:
                continue
            band = _band(a, b, axis)
            if band is None:
                continue
            gap = _box(b)[1] - _box(a)[3] if axis == "h" else _box(b)[0] - _box(a)[2]
            if best is None or gap < best[0]:
                best = (gap, band)
        if best is None or not best[1]:
            continue
        band = best[1]
        if mode == "stop" and any(grid[y][x] != bg for y, x in band):
            continue
        out.append((a, [(y, x) for y, x in band if grid[y][x] == bg]))
    return out


def bridge(grid: Grid, conn: str, axes: str, mode: str, fill: int) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    scope.parse(conn)
    if axes not in AXES or mode not in MODES:
        raise ValueError("bad bridge parameters")
    if not isinstance(fill, int) or not -1 <= fill <= 9:
        raise ValueError("bad bridge fill")
    rows = [list(row) for row in grid]
    for axis in AXES[axes]:
        for a, band in pairs(grid, conn, axis, mode):
            c = a.props["color"] if fill == -1 else fill
            for y, x in band:
                rows[y][x] = c
    return tuple(tuple(row) for row in rows)


def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not keyed.adds_only(states, targets):
        return []
    found: list[Params] = []
    for conn in scope.scopes(states, targets):
        if not scope.paints_background(states, targets, conn):
            continue
        if any(len(scope.objects(s, conn)) > MAX_OBJECTS for s in states):
            continue
        memo: dict = {}

        def joined_pairs(i: int, axis: str, mode: str, conn=conn, memo=memo):
            if (i, axis, mode) not in memo:
                memo[(i, axis, mode)] = pairs(states[i], conn, axis, mode)
            return memo[(i, axis, mode)]

        for mode in MODES:
            for axes in AXES:
                joined = [
                    (i, a, band)
                    for i in range(len(states))
                    for axis in AXES[axes]
                    for a, band in joined_pairs(i, axis, mode)
                ]
                if len(joined) < keyed.MIN_OBJECTS:
                    continue
                hit = next(((i, a, b) for i, a, b in joined if b), None)
                if hit is None:
                    continue
                i, a, band = hit
                fill_c = targets[i][band[0][0]][band[0][1]]
                fills = [-1] if fill_c == a.props["color"] else []
                fills.append(fill_c)
                for fill in fills:
                    params = (conn, axes, mode, fill)
                    if all(
                        bridge(s, *params) == t2
                        for s, t2 in zip(states, targets, strict=True)
                    ):
                        found.append(params)
                        break
                if found:
                    return found
    return found


BRIDGE_PRIMS = {"bridge": Primitive("bridge", bridge, candidates)}
