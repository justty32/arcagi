"""Object scopes for the families: a connectivity, optionally with its own background.

A scope is a ``CONNS`` name (``"4same"``: the task background, as everywhere
else) or ``"<conn>@<c>"`` (``"4same@5"``): objects are re-extracted treating
color ``c`` as background, and the families' "background cells" become the
cells of color ``c``. This handles objects drawn on a colored panel or a
grid whose task background is not the color the objects sit on. ``"group"``
(also ``"group@c"``) makes one object of all cells of each color, connected or
not (a pair of same-colored pixels, scattered marks).

``scopes(states, targets)`` lists the default conns, then ``@c`` variants for
the one color every changed train cell had before the change, when that color
is not already the background of every state and survives in every target
(a color recolored away entirely is a plain recolor; ``ALT_CONNS`` only).
"""

from collections.abc import Sequence
from functools import lru_cache

from arcagi.dsl import background as bgc
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import (
    CONNS,
    Obj,
    _extract,
    _shape_id,
    hole_cells,
    n_holes,
)
from arcagi.tasks import Grid

ALT_CONNS = ("4same", "8same")
GROUP = "group"


BASES = (*CONNS, GROUP)


def parse(conn: object) -> tuple[str, int | None]:
    if isinstance(conn, str):
        base, sep, color = conn.partition("@")
        if base in BASES and not sep:
            return base, None
        if base in BASES and color.isdigit() and 0 <= int(color) <= 9:
            return base, int(color)
    raise ValueError(f"bad object scope {conn!r}")


def background(grid: Grid, conn: str) -> int:
    bg = parse(conn)[1]
    return bgc.of(grid) if bg is None else bg


def objects(grid: Grid, conn: str) -> tuple[Obj, ...]:
    base, bg = parse(conn)
    bg = bgc.of(grid) if bg is None else bg
    return _groups(grid, bg) if base == GROUP else _extract(grid, base, bg)


@lru_cache(maxsize=4096)
def _groups(grid: Grid, bg: int) -> tuple[Obj, ...]:
    """One object per non-background color: all its cells, connected or not."""
    cells: dict[int, list[tuple[int, int]]] = {}
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c != bg:
                cells.setdefault(c, []).append((y, x))
    if not cells:
        return ()
    sizes = {c: len(v) for c, v in cells.items()}
    distinct = sorted(set(sizes.values()), reverse=True)
    height, width = len(grid), len(grid[0])
    shapes = {c: _shape_id(v) for c, v in cells.items()}
    out = []
    for c, cs in sorted(cells.items()):
        _, _, h, w = g.cells_bbox(cs)
        border = any(y in (0, height - 1) or x in (0, width - 1) for y, x in cs)
        props: dict[str, int | str] = {
            "color": c,
            "is_largest": int(sizes[c] == distinct[0]),
            "is_smallest": int(sizes[c] == distinct[-1]),
            "size_rank": distinct.index(sizes[c]) + 1,
            "size": sizes[c],
            "touches_border": int(border),
            "has_hole": int(bool(hole_cells(grid, cs))),
            "n_holes": n_holes(grid, cs),
            "color_count": 1,
            "shape_count": list(shapes.values()).count(shapes[c]),
            "h": h,
            "w": w,
            "shape": shapes[c],
        }
        out.append(Obj(tuple(cs), (c,) * len(cs), props))
    return tuple(out)


def sources(states: Sequence[Grid], targets: Sequence[Grid]) -> set[int]:
    """Colors of the input cells that change on some train pair."""
    return {
        a
        for s, t in zip(states, targets, strict=True)
        for rs, rt in zip(s, t, strict=True)
        for a, b in zip(rs, rt, strict=True)
        if a != b
    }


def scopes(states: Sequence[Grid], targets: Sequence[Grid]) -> list[str]:
    out = [*CONNS, GROUP]
    src = sources(states, targets)
    if len(src) == 1:
        (c,) = src
        kept = all(any(c in row for row in t) for t in targets)
        if kept and any(bgc.of(s) != c for s in states):
            out += [f"{base}@{c}" for base in ALT_CONNS]
    return out


def paints_background(
    states: Sequence[Grid], targets: Sequence[Grid], conn: str
) -> bool:
    """Every change turns a scope-background cell into another color."""
    changed = False
    for s, t in zip(states, targets, strict=True):
        bg = background(s, conn)
        for rs, rt in zip(s, t, strict=True):
            for a, b in zip(rs, rt, strict=True):
                if a != b:
                    if a != bg:
                        return False
                    changed = True
    return changed
