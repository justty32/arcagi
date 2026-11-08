"""Symmetry about an object: complete the grid's symmetry around a center object.

``mirror_about(grid, conn, attr, value, mode)``: the center is the bounding-box
center of the single object selected by ``(conn, attr, value)`` (as in
``objects_props.selected``; zero or several selected is an error). Every
non-background cell is copied to its images about that center (``lr``: left /
right, ``ud``: up / down, ``both``: the two mirrors and their product,
``rot4``: the three quarter turns); images land only on background cells
inside the grid, earlier sources first in raster order.

Fitting: the selector must pick exactly one object on every train input and
the center must move between train pairs (>= 2 distinct centers, so it is read
from the grid rather than fixed); the candidate must reproduce every train
pair.
"""

from collections.abc import Sequence

from arcagi.dsl.objects_props import ATTRS, selected
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import keyed, scope

MODES = ("lr", "ud", "both", "rot4")
CENTER_ATTRS = tuple(a for a in ATTRS if a not in ("size_rank",))
MAX_CANDIDATES = 2


def _center(grid: Grid, conn: str, attr: str, value: object) -> tuple[int, int]:
    base, bg = scope.parse(conn)
    if bg is not None:
        raise ValueError("mirror_about uses plain conns")
    objs = selected(grid, base, attr, value)
    if len(objs) != 1:
        raise ValueError("no single center object")
    ys = [y for y, _ in objs[0].cells]
    xs = [x for _, x in objs[0].cells]
    return min(ys) + max(ys), min(xs) + max(xs)


def _images(y: int, x: int, cy2: int, cx2: int, mode: str) -> list[tuple[int, int]]:
    if mode == "lr":
        return [(y, cx2 - x)]
    if mode == "ud":
        return [(cy2 - y, x)]
    if mode == "both":
        return [(y, cx2 - x), (cy2 - y, x), (cy2 - y, cx2 - x)]
    if mode != "rot4":
        raise ValueError(f"bad mirror mode {mode!r}")
    dy, dx = 2 * y - cy2, 2 * x - cx2
    out = []
    for ry, rx in ((dx, -dy), (-dy, -dx), (-dx, dy)):
        if (cy2 + ry) % 2 or (cx2 + rx) % 2:
            continue
        out.append(((cy2 + ry) // 2, (cx2 + rx) // 2))
    return out


def mirror_about(grid: Grid, conn: str, attr: str, value: object, mode: str) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    cy2, cx2 = _center(grid, conn, attr, value)
    bg = scope.background(grid, conn)
    height, width = len(grid), len(grid[0])
    rows = [list(row) for row in grid]
    for y in range(height):
        for x in range(width):
            c = grid[y][x]
            if c == bg:
                continue
            for ny, nx in _images(y, x, cy2, cx2, mode):
                if 0 <= ny < height and 0 <= nx < width and rows[ny][nx] == bg:
                    rows[ny][nx] = c
    return tuple(tuple(row) for row in rows)


def _selectors(states: Sequence[Grid], conn: str):
    first = scope.objects(states[0], conn)
    for attr in CENTER_ATTRS:
        for value in sorted({o.props[attr] for o in first}, key=repr):
            if all(len(selected(s, conn, attr, value)) == 1 for s in states):
                yield attr, value


def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if len(states) < 2 or not keyed.adds_only(states, targets):
        return []
    found: list[Params] = []
    for conn in ("4same", "8same", "4multi", "8multi"):
        if not scope.paints_background(states, targets, conn):
            continue
        for attr, value in _selectors(states, conn):
            centers = {_center(s, conn, attr, value) for s in states}
            if len(centers) < 2:
                continue
            for mode in MODES:
                params = (conn, attr, value, mode)
                try:
                    ok = all(
                        mirror_about(s, *params) == t
                        for s, t in zip(states, targets, strict=True)
                    )
                except ValueError:
                    ok = False
                if ok:
                    found.append(params)
                    break
            if len(found) >= MAX_CANDIDATES:
                return found
    return found


MIRROR_PRIMS = {"mirror_about": Primitive("mirror_about", mirror_about, candidates)}
