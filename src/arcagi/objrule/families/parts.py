"""Keyed object parts: recolor one part of each object, color by key.

``part_key(grid, conn, part, key, table)``: like the ``keyed`` families, with
the region a part of the object's own cells: ``top_half`` / ``bottom_half`` /
``left_half`` / ``right_half`` (the ``floor(h / 2)`` rows or ``floor(w / 2)``
columns of its box on that side), ``alt_even`` / ``alt_odd`` (cells at even /
odd positions in raster order: every other cell of a line), ``inner_alt_even``
/ ``inner_alt_odd`` (the same over its ``inner`` cells). The color may be the
background (punching holes). Fitting and anti-memorization as in ``keyed``.
"""

from collections.abc import Sequence

from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import Obj
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import keyed


def _half(o: Obj, side: str) -> list[tuple[int, int]]:
    top, left, h, w = g.cells_bbox(list(o.cells))
    if side == "top":
        return [(y, x) for y, x in o.cells if y < top + h // 2]
    if side == "bottom":
        return [(y, x) for y, x in o.cells if y >= top + h - h // 2]
    if side == "left":
        return [(y, x) for y, x in o.cells if x < left + w // 2]
    return [(y, x) for y, x in o.cells if x >= left + w - w // 2]


def _alt(cells, parity: int) -> list[tuple[int, int]]:
    return [c for i, c in enumerate(sorted(cells)) if i % 2 == parity]


def _inner(o: Obj) -> list[tuple[int, int]]:
    return keyed.REGIONS["inner"]((), o, 0)


PARTS: dict[str, keyed.Region] = {
    "top_half": lambda grid, o, bg: _half(o, "top"),
    "bottom_half": lambda grid, o, bg: _half(o, "bottom"),
    "left_half": lambda grid, o, bg: _half(o, "left"),
    "right_half": lambda grid, o, bg: _half(o, "right"),
    "alt_even": lambda grid, o, bg: _alt(o.cells, 0),
    "alt_odd": lambda grid, o, bg: _alt(o.cells, 1),
    "inner_alt_even": lambda grid, o, bg: _alt(_inner(o), 0),
    "inner_alt_odd": lambda grid, o, bg: _alt(_inner(o), 1),
}


def part_key(grid: Grid, conn: str, part: str, key: str, table) -> Grid:
    if part not in PARTS:
        raise ValueError(f"bad part {part!r}")
    return keyed.paint_keyed(PARTS[part], grid, conn, key, table)


def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    found: list[Params] = []
    for part, region in PARTS.items():
        for conn, key, table in keyed.fit(region, states, targets, additive=False):
            found.append((conn, part, key, table))
        if len(found) >= keyed.MAX_CANDIDATES:
            break
    return found[: keyed.MAX_CANDIDATES]


PARTS_PRIMS = {"part_key": Primitive("part_key", part_key, candidates)}
