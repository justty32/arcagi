"""Keyed region families: paint a region around or inside each object, the color
looked up in a table keyed by an object property.

``<family>(grid, conn, key, table)``: for every object of ``grid`` under
``conn`` whose ``key`` value appears in ``table`` (pairs ``(key_value,
color)``), paint the family's region with that color; objects whose key is not
in the table are left alone. ``conn`` is a ``scope`` (``"4same"``, or
``"4same@5"``: objects re-extracted on background color 5). ``key == "const"``
gives every object the same key ``0``. Regions (computed on the input grid,
all objects read before any paint):

- ``halo4`` / ``halo8``: background cells 4- / 8-adjacent to the object;
- ``bbox_fill``: background cells inside the object's bounding box;
- ``holes_fill``: non-object cells enclosed by the object (``hole_cells``);
- ``inner``: object cells whose 8 neighbours all belong to the object;
- ``outline``: the object's other cells (its border).

Fitting (``candidates``): each object's observed value is the single target
color over its region, or ``skip`` when the region is unchanged (a partly
changed region also reads as ``skip``: a neighbour may paint it). A key's table
entry is the value all its objects agree on. Anti-memorization: >= 3 painted
objects, every table entry backed by >= 2 objects, and a non-``const`` key
needs >= 2 distinct values (``skip`` counts) over the train objects. A
candidate must reproduce every train pair, or with ``partial`` only change
cells to their target value (the search may finish the rest).
"""

from collections.abc import Callable, Sequence

from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import Obj, hole_cells, same_shapes
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import scope

type Cell = tuple[int, int]
type Region = Callable[[Grid, Obj, int], list[Cell]]
SKIP = "skip"
KEYS = ("const", "color", "size", "shape", "is_largest", "is_smallest")
KEYS += ("touches_border", "has_hole", "size_rank", "h", "w", "h_odd")
MIN_OBJECTS = 3
MIN_SUPPORT = 2
MAX_CANDIDATES = 2
N4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
N8 = N4 + ((-1, -1), (-1, 1), (1, -1), (1, 1))


def key_of(o: Obj, key: str) -> object:
    if key == "const":
        return 0
    if key == "h_odd":
        return int(o.props["h"]) % 2
    if key not in KEYS:
        raise ValueError(f"bad key {key!r}")
    return o.props[key]


def _ring(grid: Grid, o: Obj, bg: int, nbrs) -> list[Cell]:
    height, width = g.shape(grid)
    own = set(o.cells)
    out = set()
    for y, x in o.cells:
        for dy, dx in nbrs:
            ny, nx = y + dy, x + dx
            if (ny, nx) not in own and 0 <= ny < height and 0 <= nx < width:
                if grid[ny][nx] == bg:
                    out.add((ny, nx))
    return sorted(out)


def _bbox(grid: Grid, o: Obj, bg: int) -> list[Cell]:
    top, left, h, w = g.cells_bbox(list(o.cells))
    return [
        (y, x)
        for y in range(top, top + h)
        for x in range(left, left + w)
        if grid[y][x] == bg
    ]


def _inner_mask(o: Obj) -> list[bool]:
    own = set(o.cells)
    return [all((y + a, x + b) in own for a, b in N8) for y, x in o.cells]


REGIONS: dict[str, Region] = {
    "halo4": lambda grid, o, bg: _ring(grid, o, bg, N4),
    "halo8": lambda grid, o, bg: _ring(grid, o, bg, N8),
    "bbox_fill": _bbox,
    "holes_fill": lambda grid, o, bg: hole_cells(grid, o.cells),
    "inner": lambda grid, o, bg: [
        c for c, m in zip(o.cells, _inner_mask(o), strict=True) if m
    ],
    "outline": lambda grid, o, bg: [
        c for c, m in zip(o.cells, _inner_mask(o), strict=True) if not m
    ],
}


def paint_keyed(region: Region, grid: Grid, conn: str, key: str, table) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    lookup = {k: v for k, v in table}
    if any(not isinstance(v, int) or not 0 <= v <= 9 for v in lookup.values()):
        raise ValueError("table value is not a color")
    bg = scope.background(grid, conn)
    cells: dict[Cell, int] = {}
    for o in scope.objects(grid, conn):
        k = key_of(o, key)
        if k in lookup:
            for cell in region(grid, o, bg):
                cells[cell] = lookup[k]
    if not cells:
        return grid
    rows = [list(row) for row in grid]
    for (y, x), v in cells.items():
        rows[y][x] = v
    return tuple(tuple(row) for row in rows)


def observe(region: Region, state: Grid, target: Grid, o: Obj, bg: int) -> object:
    """The object's value: a color, ``SKIP``, or None (no region: don't care)."""
    cells = region(state, o, bg)
    if not cells:
        return None
    new = {target[y][x] for y, x in cells if target[y][x] != state[y][x]}
    if len(new) == 1 and all(target[y][x] in new for y, x in cells):
        return new.pop()
    return SKIP


def fit_table(obs: Sequence[tuple[Obj, object]], key: str) -> tuple | None:
    """``(key_value, color)`` pairs from ``(object, value)`` observations."""
    groups: dict[object, list[object]] = {}
    for o, v in obs:
        groups.setdefault(key_of(o, key), []).append(v)
    table, painted = [], 0
    for k, vs in groups.items():
        if len(set(vs)) != 1:
            return None
        if vs[0] != SKIP:
            if len(vs) < MIN_SUPPORT:
                return None
            table.append((k, vs[0]))
            painted += len(vs)
    if painted < MIN_OBJECTS:
        return None
    if key == "const":
        return tuple(table)
    if len({v for vs in groups.values() for v in vs}) < 2:
        return None
    return tuple(sorted(table, key=repr))


def adds_only(states: Sequence[Grid], targets: Sequence[Grid]) -> bool:
    """Same shapes and every change paints one source color (cheap pre-check)."""
    return same_shapes(states, targets) and len(scope.sources(states, targets)) == 1


def _consistent(state: Grid, out: Grid, target: Grid) -> bool:
    return out != state and all(
        o == t or o == s
        for rs, ro, rt in zip(state, out, target, strict=True)
        for s, o, t in zip(rs, ro, rt, strict=True)
        if o != s
    )


def fit(
    region: Region,
    states: Sequence[Grid],
    targets: Sequence[Grid],
    *,
    partial: bool = False,
    additive: bool = True,
) -> list[Params]:
    if additive and not adds_only(states, targets):
        return []
    if not same_shapes(states, targets) or all(
        s == t for s, t in zip(states, targets, strict=True)
    ):
        return []
    exact: list[Params] = []
    loose: list[Params] = []
    for conn in scope.scopes(states, targets):
        if additive and not scope.paints_background(states, targets, conn):
            continue
        obs = []
        for s, t in zip(states, targets, strict=True):
            bg = scope.background(s, conn)
            for o in scope.objects(s, conn):
                v = observe(region, s, t, o, bg)
                if v is not None:
                    obs.append((o, v))
        for key in KEYS:
            table = fit_table(obs, key)
            if table is None:
                continue
            params = (conn, key, table)
            outs = [paint_keyed(region, s, conn, key, table) for s in states]
            if all(o == t for o, t in zip(outs, targets, strict=True)):
                exact.append(params)
                break
            if partial and all(
                _consistent(s, o, t) for s, o, t in zip(states, outs, targets)
            ):
                loose.append(params)
        if len(exact) >= MAX_CANDIDATES:
            break
    return (exact + loose)[:MAX_CANDIDATES]


ADDITIVE = frozenset({"halo4", "halo8", "bbox_fill"})


def _primitive(name: str, region: Region) -> Primitive:
    def apply(grid: Grid, conn: str, key: str, table) -> Grid:
        return paint_keyed(region, grid, conn, key, table)

    def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
        return fit(region, states, targets, additive=additive)

    additive = name in ADDITIVE
    return Primitive(name, apply, candidates)


KEYED_PRIMS: dict[str, Primitive] = {
    f"{name}_key": _primitive(f"{name}_key", region) for name, region in REGIONS.items()
}
