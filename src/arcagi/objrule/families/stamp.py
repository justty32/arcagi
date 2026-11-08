"""Keyed stamps: paint a fixed pattern around each object, chosen by a key.

``stamp_key(grid, conn, key, table)``: ``table`` pairs ``(key_value,
pattern)``; a pattern is a tuple of ``(dy, dx, color)`` offsets from the
object's bounding-box top-left. Every object whose key is in the table paints
its pattern onto background cells (off-grid offsets are dropped); other objects
are left alone. Keys are ``keyed.KEYS``.

Fitting: objects are grouped by key; an offset (within ``RADIUS`` of the box)
joins the group's pattern when every member that sees it on a background input
cell has the same non-background target color there, and at least
``SUPPORT`` (3) members see it. Anti-memorization is stricter than ``keyed``
(a pattern is a big table: r06 saw stamp_key fits pass train and miss test):
>= 3 stamping objects, >= ``SUPPORT`` per entry, >= 2 distinct values for a
non-``const`` key; candidates must reproduce every train pair.
"""

from collections.abc import Sequence

from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import Obj
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import keyed, scope

RADIUS = 2
SUPPORT = 3
MAX_PATTERN = 40


def stamp_key(grid: Grid, conn: str, key: str, table) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    lookup = {k: tuple(p) for k, p in table}
    bg = scope.background(grid, conn)
    height, width = g.shape(grid)
    cells: dict[tuple[int, int], int] = {}
    for o in scope.objects(grid, conn):
        pattern = lookup.get(keyed.key_of(o, key))
        if pattern is None:
            continue
        top, left, _, _ = g.cells_bbox(list(o.cells))
        for dy, dx, c in pattern:
            y, x = top + dy, left + dx
            if 0 <= y < height and 0 <= x < width and grid[y][x] == bg:
                cells[(y, x)] = c
    if not cells:
        return grid
    rows = [list(row) for row in grid]
    for (y, x), c in cells.items():
        rows[y][x] = c
    return tuple(tuple(row) for row in rows)


def _views(o: Obj, state: Grid, target: Grid, bg: int) -> dict:
    """``(dy, dx) -> target color`` on background input cells near ``o``."""
    top, left, h, w = g.cells_bbox(list(o.cells))
    height, width = g.shape(state)
    out = {}
    for dy in range(-RADIUS, h + RADIUS):
        for dx in range(-RADIUS, w + RADIUS):
            y, x = top + dy, left + dx
            if 0 <= y < height and 0 <= x < width and state[y][x] == bg:
                out[(dy, dx)] = target[y][x]
    return out


def _pattern(views: Sequence[dict], bg: int) -> tuple | None:
    seen: dict[tuple[int, int], list[int]] = {}
    for v in views:
        for off, c in v.items():
            seen.setdefault(off, []).append(c)
    pattern = []
    for (dy, dx), cs in sorted(seen.items()):
        if len(set(cs)) == 1 and cs[0] != bg and len(cs) >= SUPPORT:
            pattern.append((dy, dx, cs[0]))
    if len(pattern) > MAX_PATTERN:
        return None
    return tuple(pattern)


def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not keyed.adds_only(states, targets):
        return []
    found: list[Params] = []
    for conn in scope.scopes(states, targets):
        if not scope.paints_background(states, targets, conn):
            continue
        objs = []
        for s, t in zip(states, targets, strict=True):
            bg = scope.background(s, conn)
            objs += [(o, _views(o, s, t, bg), bg) for o in scope.objects(s, conn)]
        if len(objs) < keyed.MIN_OBJECTS:
            continue
        for key in keyed.KEYS:
            groups: dict[object, list] = {}
            for o, v, bg in objs:
                groups.setdefault(keyed.key_of(o, key), []).append((v, bg))
            table, painted, kinds = [], 0, set()
            for k, members in groups.items():
                p = _pattern([v for v, _ in members], members[0][1])
                if p is None:
                    break
                kinds.add(p)
                if p:
                    if len(members) < SUPPORT:
                        break
                    table.append((k, p))
                    painted += len(members)
            else:
                if painted < keyed.MIN_OBJECTS:
                    continue
                if key != "const" and len(kinds) < 2:
                    continue
                params = (conn, key, tuple(sorted(table, key=repr)))
                if all(
                    stamp_key(s, *params) == t
                    for s, t in zip(states, targets, strict=True)
                ):
                    found.append(params)
                    break
        if len(found) >= keyed.MAX_CANDIDATES:
            break
    return found


STAMP_PRIMS = {"stamp_key": Primitive("stamp_key", stamp_key, candidates)}
