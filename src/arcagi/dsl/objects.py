"""Object-level primitives: a single-attribute selector plus an action.

Parameters are ``(conn, attr, value, ...)``; the selector is re-evaluated on
every grid the program runs on, so ``("is_largest", 1)`` picks the largest
object of the test input. Candidates are inferred by labeling each train object
as changed / unchanged and keeping only selectors that separate the two sets.
All primitives apply only to same-size tasks.
"""

from collections.abc import Sequence

from arcagi.tasks import Grid

from . import grid as g
from .objects_learner import apply_object_colormap, fit_object_colormap
from .objects_props import (
    CONNS,
    Labeled,
    Obj,
    changed,
    extract,
    hole_cells,
    same_shapes,
    selected,
    separate,
)
from .primitives import Params, Primitive

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
MAX_CANDIDATES = 8


def _paint(grid: Grid, cells: dict[tuple[int, int], int]) -> Grid:
    if not cells:
        return grid
    rows = [list(row) for row in grid]
    for (y, x), value in cells.items():
        rows[y][x] = value
    return tuple(tuple(row) for row in rows)


def _recolor_sel(grid: Grid, conn: str, attr: str, value: object, color: int) -> Grid:
    objs = selected(grid, conn, attr, value)
    return _paint(grid, {cell: color for o in objs for cell in o.cells})


def _delete_sel(grid: Grid, conn: str, attr: str, value: object) -> Grid:
    bg = g.background(grid)
    objs = selected(grid, conn, attr, value)
    return _paint(grid, {cell: bg for o in objs for cell in o.cells})


def _keep_sel(grid: Grid, conn: str, attr: str, value: object) -> Grid:
    bg = g.background(grid)
    keep = {o.cells for o in selected(grid, conn, attr, value)}
    drop = [o for o in extract(grid, conn) if o.cells not in keep]
    return _paint(grid, {cell: bg for o in drop for cell in o.cells})


def _fill_holes(grid: Grid, color: int) -> Grid:
    """Paint background cells enclosed by a single (8-connected) object."""
    bg = g.background(grid)
    paint = {}
    for o in extract(grid, "8multi"):
        for y, x in hole_cells(grid, o.cells):
            if grid[y][x] == bg:
                paint[(y, x)] = color
    return _paint(grid, paint)


def _move_sel(grid: Grid, conn: str, attr: str, value: object, direction: str) -> Grid:
    """Slide each selected object in ``direction`` until the border or a cell."""
    dy, dx = DIRS[direction]
    bg = g.background(grid)
    height, width = g.shape(grid)
    objs = selected(grid, conn, attr, value)
    rows = [list(row) for row in grid]
    for o in objs:
        for y, x in o.cells:
            rows[y][x] = bg
    # Objects nearest the destination wall settle first.
    objs.sort(key=lambda o: -max(y * dy + x * dx for y, x in o.cells))
    for o in objs:
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


def _extend_sel(
    grid: Grid, conn: str, attr: str, value: object, direction: str
) -> Grid:
    """Draw a ray from each selected object's cells to the border over background."""
    dy, dx = DIRS[direction]
    bg = g.background(grid)
    height, width = g.shape(grid)
    paint = {}
    for o in selected(grid, conn, attr, value):
        own = set(o.cells)
        for (y, x), c in zip(o.cells, o.colors, strict=True):
            if (y + dy, x + dx) in own:
                continue
            y, x = y + dy, x + dx
            while 0 <= y < height and 0 <= x < width and grid[y][x] == bg:
                paint[(y, x)] = c
                y, x = y + dy, x + dx
    return _paint(grid, paint)


# --- candidate inference -------------------------------------------------------


def _selectors(
    states: Sequence[Grid], label, extra: Sequence[object] = (), conns=CONNS
) -> list[Params]:
    """Run ``label(obj, state, target_index) -> bool|None`` per conn and separate."""
    out: list[Params] = []
    for conn in conns:
        examples: list[Labeled] = []
        for i, state in enumerate(states):
            examples.append([(o, label(o, state, i)) for o in extract(state, conn)])
        for attr, value in separate(examples):
            out.append((conn, attr, value, *extra))
    return out[:MAX_CANDIDATES]


def _uniform(obj: Obj, target: Grid) -> int | None:
    values = {target[y][x] for y, x in obj.cells}
    return values.pop() if len(values) == 1 else None


def _recolor_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list:
    if not same_shapes(states, targets):
        return []
    out = []
    for conn in CONNS:
        colors = set()
        for state, target in zip(states, targets, strict=True):
            for o in extract(state, conn):
                if changed(o, target) and (c := _uniform(o, target)) is not None:
                    colors.add(c)
        if len(colors) != 1:
            continue
        color = colors.pop()

        def label(o: Obj, _s: Grid, i: int, color: int = color) -> bool | None:
            if not changed(o, targets[i]):
                return None if set(o.colors) == {color} else False
            return True if _uniform(o, targets[i]) == color else None

        out.extend(_selectors(states, label, (color,), (conn,)))
    return out[:MAX_CANDIDATES]


def _delete_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list:
    if not same_shapes(states, targets):
        return []

    def label(o: Obj, s: Grid, i: int) -> bool | None:
        if not changed(o, targets[i]):
            return False
        return True if _uniform(o, targets[i]) == g.background(s) else None

    return _selectors(states, label)


def _keep_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list:
    if not same_shapes(states, targets):
        return []

    def label(o: Obj, s: Grid, i: int) -> bool | None:
        if not changed(o, targets[i]):
            return True
        return False if _uniform(o, targets[i]) == g.background(s) else None

    return [p for p in _selectors(states, label) if p[1] != "all"]


def _fill_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list:
    if not same_shapes(states, targets):
        return []
    colors = set()
    for state, target in zip(states, targets, strict=True):
        bg = g.background(state)
        for rs, rt in zip(state, target, strict=True):
            for a, b in zip(rs, rt, strict=True):
                if a != b:
                    if a != bg:
                        return []
                    colors.add(b)
    return [(colors.pop(),)] if len(colors) == 1 else []


def _shift_dirs(o: Obj, target: Grid) -> set[str]:
    """Directions in which a shifted copy of ``o`` appears intact in ``target``."""
    height, width = g.shape(target)
    found = set()
    for name, (dy, dx) in DIRS.items():
        for k in range(1, max(height, width)):
            moved = [(y + dy * k, x + dx * k) for y, x in o.cells]
            if not all(0 <= y < height and 0 <= x < width for y, x in moved):
                break
            if all(
                target[y][x] == c for (y, x), c in zip(moved, o.colors, strict=True)
            ):
                found.add(name)
                break
    return found


def _move_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list:
    if not same_shapes(states, targets):
        return []
    out = []
    for direction in _common_dirs(states, targets, _shift_dirs):

        def label(o: Obj, _s: Grid, i: int, d: str = direction) -> bool | None:
            if not changed(o, targets[i]):
                return False
            return True if d in _shift_dirs(o, targets[i]) else None

        out.extend(_selectors(states, label, (direction,)))
    return out[:MAX_CANDIDATES]


def _grow_dirs(o: Obj, target: Grid, state: Grid) -> set[str]:
    """Directions where the background cell just past ``o`` took its color."""
    height, width = g.shape(target)
    bg = g.background(state)
    own = set(o.cells)
    found = set()
    for name, (dy, dx) in DIRS.items():
        for (y, x), c in zip(o.cells, o.colors, strict=True):
            ny, nx = y + dy, x + dx
            if (ny, nx) in own or not (0 <= ny < height and 0 <= nx < width):
                continue
            if state[ny][nx] == bg and target[ny][nx] == c:
                found.add(name)
                break
    return found


def _common_dirs(states, targets, dirs_of) -> list[str]:
    common: set[str] | None = None
    for state, target in zip(states, targets, strict=True):
        for o in extract(state, "8multi"):
            if dirs_of is _shift_dirs:
                if not changed(o, target):
                    continue
                dirs = _shift_dirs(o, target)
            else:
                dirs = _grow_dirs(o, target, state)
                if not dirs:
                    continue
            common = dirs if common is None else common & dirs
    return sorted(common or ())


def _extend_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list:
    if not same_shapes(states, targets):
        return []
    out = []
    for direction in _common_dirs(states, targets, _grow_dirs):

        def label(o: Obj, s: Grid, i: int, d: str = direction) -> bool:
            return d in _grow_dirs(o, targets[i], s)

        out.extend(_selectors(states, label, (direction,)))
    return out[:MAX_CANDIDATES]


OBJECTS: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("recolor_sel", _recolor_sel, _recolor_candidates),
        Primitive("delete_sel", _delete_sel, _delete_candidates),
        Primitive("keep_sel", _keep_sel, _keep_candidates),
        Primitive("fill_holes", _fill_holes, _fill_candidates),
        Primitive("move_sel", _move_sel, _move_candidates),
        Primitive("extend_sel", _extend_sel, _extend_candidates),
    )
}

__all__ = ["OBJECTS", "apply_object_colormap", "fit_object_colormap"]
