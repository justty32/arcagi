"""Per-object rule primitives: a selector plus an action whose parameter comes
from an object-scope extraction evaluated on each selected object.

Parameters are ``(conn, attr, value, source)``: ``(conn, attr, value)`` selects
objects like ``recolor_sel`` (``attr == "pred"`` names a predicate), ``source``
is a live object-extract block name (``extract_<hash>``) or an inline body.
``recolor_from`` paints each object with its source color, ``move_from`` slides
it in its source direction until blocked, ``extend_from`` draws rays from it in
its source direction over the background. Values are read on the input grid;
an object whose source value is undefined is left unchanged.
"""

from collections.abc import Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import extract as ex
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import CONNS, Obj, same_shapes, selected
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import fit
from . import view as ov

MAX_CANDIDATES = 6


def _paint(grid: Grid, cells: dict[tuple[int, int], int]) -> Grid:
    if not cells:
        return grid
    rows = [list(row) for row in grid]
    for (y, x), value in cells.items():
        rows[y][x] = value
    return tuple(tuple(row) for row in rows)


def _values(grid: Grid, conn: str, attr: str, value: object, source: object):
    """Selected objects with their source values; objects whose source is
    undefined (ambiguous, no neighbor, not aligned) are left unchanged."""
    grid = tuple(tuple(row) for row in grid)
    ex.unwrap_object(source)  # a bad source is an error, not a skip
    out = []
    for o in selected(grid, conn, attr, value):
        try:
            out.append((o, ex.run_on_object(source, grid, o)))
        except fit.ERRORS:
            continue
    return grid, out


def _direction(value: object) -> tuple[int, int]:
    if value not in ov.DIRS:
        raise ValueError(f"not a direction: {value!r}")
    return ov.DIRS[value]  # type: ignore[index]


def recolor_from(grid: Grid, conn: str, attr: str, value: object, source) -> Grid:
    grid, pairs = _values(grid, conn, attr, value, source)
    paint = {}
    for o, color in pairs:
        if not isinstance(color, int) or not 0 <= color <= 9:
            raise ValueError("source is not a color")
        paint.update({cell: color for cell in o.cells})
    return _paint(grid, paint)


def move_from(grid: Grid, conn: str, attr: str, value: object, source) -> Grid:
    """Slide each selected object toward its source direction until blocked."""
    grid, pairs = _values(grid, conn, attr, value, source)
    moves = [(o, _direction(d)) for o, d in pairs]
    bg = bgc.of(grid)
    height, width = g.shape(grid)
    rows = [list(row) for row in grid]
    for o, _ in moves:
        for y, x in o.cells:
            rows[y][x] = bg

    def lead(item: tuple[Obj, tuple[int, int]]) -> int:
        o, (dy, dx) = item
        return -max(y * dy + x * dx for y, x in o.cells)

    for o, (dy, dx) in sorted(moves, key=lead):
        shift = 0
        while True:
            k = shift + 1
            nxt = [(y + dy * k, x + dx * k) for y, x in o.cells]
            if not all(
                0 <= y < height and 0 <= x < width and rows[y][x] == bg for y, x in nxt
            ):
                break
            shift = k
        for (y, x), c in zip(o.cells, o.colors, strict=True):
            rows[y + dy * shift][x + dx * shift] = c
    return tuple(tuple(row) for row in rows)


def extend_from(grid: Grid, conn: str, attr: str, value: object, source) -> Grid:
    """Ray from each selected object's cells in its source direction."""
    grid, pairs = _values(grid, conn, attr, value, source)
    bg = bgc.of(grid)
    height, width = g.shape(grid)
    paint = {}
    for o, d in pairs:
        dy, dx = _direction(d)
        own = set(o.cells)
        for (y, x), c in zip(o.cells, o.colors, strict=True):
            if (y + dy, x + dx) in own:
                continue
            y, x = y + dy, x + dx
            while 0 <= y < height and 0 <= x < width and grid[y][x] == bg:
                paint[(y, x)] = c
                y, x = y + dy, x + dx
    return _paint(grid, paint)


def _cheap_reject(states: Sequence[Grid], outs: Sequence[Grid]) -> bool:
    return not same_shapes(states, outs) or all(
        s == t for s, t in zip(states, outs, strict=True)
    )


def _candidates(kind: str):
    def candidates(states: Sequence[Grid], outs: Sequence[Grid]) -> list[Params]:
        if _cheap_reject(states, outs):
            return []
        found: list[Params] = []
        for conn in CONNS:
            try:
                rows = fit.targets(kind, conn, states, outs)
            except fit.ERRORS:
                continue
            if rows is None:
                continue
            for source in fit.sources(kind, states, rows):
                for attr, value in fit.selectors(kind, conn, states, rows, source):
                    found.append((conn, attr, value, source))
            if len(found) >= MAX_CANDIDATES:
                break
        return found[:MAX_CANDIDATES]

    return candidates


OBJRULE_PRIMS: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("recolor_from", recolor_from, _candidates("recolor")),
        Primitive("move_from", move_from, _candidates("move")),
        Primitive("extend_from", extend_from, _candidates("extend")),
    )
}
