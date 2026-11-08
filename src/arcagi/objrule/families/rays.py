"""Keyed rays: each object shoots rays in its own color, directions by key.

``rays_key(grid, conn, key, table)``: ``table`` pairs ``(key_value, dirs)``,
``dirs`` a ``+``-joined, sorted list of ``view.DIRS8`` names (``"down+up"``).
Every object whose key is in the table shoots, from each of its cells whose
next cell along a direction is not its own (for a diagonal, neither
orthogonal step is its own either), a ray in its color over background cells
up to the border or the first non-background cell. Rays are traced on the
input grid. Keys are ``keyed.KEYS``; ``conn`` is a ``scope``.

Fitting: an object's value is the set of directions whose every ray is fully
painted in its color in the target (``skip`` when none and the object's rays
are untouched); tables and anti-memorization as in ``keyed``; candidates must
reproduce every train pair.
"""

from collections.abc import Sequence

from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import Obj
from arcagi.dsl.primitives import Params, Primitive
from arcagi.objrule import view as ov
from arcagi.tasks import Grid

from . import keyed, scope


def _origins(o: Obj, d: tuple[int, int]) -> list[tuple[tuple[int, int], int]]:
    own = set(o.cells)
    dy, dx = d
    out = []
    for (y, x), c in zip(o.cells, o.colors, strict=True):
        if (y + dy, x + dx) in own:
            continue
        if dy and dx and ((y + dy, x) in own or (y, x + dx) in own):
            continue
        out.append(((y, x), c))
    return out


def ray_cells(grid: Grid, o: Obj, d: tuple[int, int], bg: int):
    """``[(cells, color)]`` per ray of ``o`` along ``d``."""
    height, width = g.shape(grid)
    dy, dx = d
    out = []
    for (y, x), c in _origins(o, d):
        cells = []
        y, x = y + dy, x + dx
        while 0 <= y < height and 0 <= x < width and grid[y][x] == bg:
            cells.append((y, x))
            y, x = y + dy, x + dx
        out.append((cells, c))
    return out


def _dirs(value: object) -> list[tuple[int, int]]:
    if not isinstance(value, str) or not value:
        raise ValueError(f"bad ray directions {value!r}")
    names = value.split("+")
    if any(n not in ov.DIRS8 for n in names):
        raise ValueError(f"bad ray directions {value!r}")
    return [ov.DIRS8[n] for n in names]


def rays_key(grid: Grid, conn: str, key: str, table) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    lookup = {k: _dirs(v) for k, v in table}
    bg = scope.background(grid, conn)
    cells: dict[tuple[int, int], int] = {}
    for o in scope.objects(grid, conn):
        for d in lookup.get(keyed.key_of(o, key), ()):
            for ray, c in ray_cells(grid, o, d, bg):
                cells.update(dict.fromkeys(ray, c))
    if not cells:
        return grid
    rows = [list(row) for row in grid]
    for (y, x), c in cells.items():
        rows[y][x] = c
    return tuple(tuple(row) for row in rows)


def observe(o: Obj, state: Grid, target: Grid, bg: int) -> object:
    names, touched = [], False
    for name, d in ov.DIRS8.items():
        rays = [(cs, c) for cs, c in ray_cells(state, o, d, bg) if cs]
        if not rays:
            continue
        hits = [all(target[y][x] == c for y, x in cs) for cs, c in rays]
        if all(hits):
            names.append(name)
        touched = touched or any(target[y][x] != bg for cs, _ in rays for y, x in cs)
    if names:
        return "+".join(sorted(names))
    return keyed.SKIP if not touched else None


def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not keyed.adds_only(states, targets):
        return []
    found: list[Params] = []
    for conn in scope.scopes(states, targets):
        if not scope.paints_background(states, targets, conn):
            continue
        obs = []
        for s, t in zip(states, targets, strict=True):
            bg = scope.background(s, conn)
            for o in scope.objects(s, conn):
                v = observe(o, s, t, bg)
                if v is not None:
                    obs.append((o, v))
        for key in keyed.KEYS:
            table = keyed.fit_table(obs, key)
            if table is None:
                continue
            params = (conn, key, table)
            if all(
                rays_key(s, *params) == t for s, t in zip(states, targets, strict=True)
            ):
                found.append(params)
                break
        if len(found) >= keyed.MAX_CANDIDATES:
            break
    return found


RAYS_PRIMS = {"rays_key": Primitive("rays_key", rays_key, candidates)}
