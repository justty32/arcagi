"""Shared per-object actions: painting, source values, sliding and rays.

Directions are names of ``view.DIRS8`` (the four sides plus the diagonals).
Each ``Move`` is ``(cells, colors, (dy, dx))``; ``slide`` lifts every moved
object first, then slides them leading-edge first until blocked by a border or
a non-background cell.
"""

from collections.abc import Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import extract as ex
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import Obj, selected
from arcagi.tasks import Grid

from . import fit
from . import view as ov

type Cells = Sequence[tuple[int, int]]
type Move = tuple[Cells, Sequence[int], tuple[int, int]]


def paint(grid: Grid, cells: dict[tuple[int, int], int]) -> Grid:
    if not cells:
        return grid
    rows = [list(row) for row in grid]
    for (y, x), value in cells.items():
        rows[y][x] = value
    return tuple(tuple(row) for row in rows)


def values(grid: Grid, conn: str, attr: str, value: object, *sources: object):
    """Selected objects with each source's value; objects where some source is
    undefined (ambiguous, no neighbor, not aligned) are left unchanged."""
    grid = tuple(tuple(row) for row in grid)
    for source in sources:
        ex.unwrap_object(source)  # a bad source is an error, not a skip
    out = []
    for o in selected(grid, conn, attr, value):
        try:
            vals = tuple(ex.run_on_object(s, grid, o) for s in sources)
        except fit.ERRORS:
            continue
        out.append((o, *vals))
    return grid, out


def direction(value: object) -> tuple[int, int]:
    if value not in ov.DIRS8:
        raise ValueError(f"not a direction: {value!r}")
    return ov.DIRS8[value]  # type: ignore[index]


def color(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 9:
        raise ValueError("source is not a color")
    return value


def slide(grid: Grid, moves: Sequence[Move]) -> tuple[Grid, list[list]]:
    """Grid after the slides and each object's final cells (in move order)."""
    bg = bgc.of(grid)
    height, width = g.shape(grid)
    rows = [list(row) for row in grid]
    for cells, _, _ in moves:
        for y, x in cells:
            rows[y][x] = bg

    def lead(i: int) -> int:
        cells, _, (dy, dx) = moves[i]
        return -max(y * dy + x * dx for y, x in cells)

    final: list[list] = [[] for _ in moves]
    for i in sorted(range(len(moves)), key=lead):
        cells, colors, (dy, dx) = moves[i]
        shift = 0
        while True:
            k = shift + 1
            nxt = [(y + dy * k, x + dx * k) for y, x in cells]
            if not all(
                0 <= y < height and 0 <= x < width and rows[y][x] == bg for y, x in nxt
            ):
                break
            shift = k
        for (y, x), c in zip(cells, colors, strict=True):
            rows[y + dy * shift][x + dx * shift] = c
        final[i] = [(y + dy * shift, x + dx * shift) for y, x in cells]
    return tuple(tuple(row) for row in rows), final


def rays(grid: Grid, cells: Cells, colors: Sequence[int], d: tuple[int, int]):
    """Cells painted by rays from ``cells`` in direction ``d`` over background."""
    bg = bgc.of(grid)
    height, width = g.shape(grid)
    dy, dx = d
    own = set(cells)
    out = {}
    for (y, x), c in zip(cells, colors, strict=True):
        if (y + dy, x + dx) in own:
            continue
        y, x = y + dy, x + dx
        while 0 <= y < height and 0 <= x < width and grid[y][x] == bg:
            out[(y, x)] = c
            y, x = y + dy, x + dx
    return out


def all_hold(prim, params, states: Sequence[Grid], outs: Sequence[Grid]) -> bool:
    try:
        return all(prim(s, *params) == t for s, t in zip(states, outs, strict=True))
    except fit.ERRORS:
        return False


def obj_feats(o: Obj) -> dict[str, int]:
    return {"o_size": len(o.cells), "o_h": int(o.props["h"]), "o_w": int(o.props["w"])}
