"""Two-step per-object rules: two parameter sources on the same object.

Parameters ``(conn, attr, value, source_a, source_b)``; both sources are read
on the input grid. ``recolor_move`` paints each selected object with color
``source_a`` and slides it toward direction ``source_b`` until blocked;
``move_extend`` slides it toward ``source_a`` and then draws rays from its new
place toward ``source_b``.

Fitting: every changed train object gets a set of joint values ``(a, b)``; the
first source must explain the ``a`` part, the second the ``b`` part given the
first source's value, each over >= ``fit.MIN_OBJECTS`` objects with >=
``fit.MIN_VALUES`` distinct values (``fit.explains``). Candidates must
reproduce every train pair (``act.all_hold``), so a two-step rule only stands
when it is consistent on all train objects.
"""

from collections.abc import Callable, Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import extract as ex
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import (
    CONNS,
    Obj,
    changed,
    extract,
    pred_selectors,
    same_shapes,
    separate,
)
from arcagi.dsl.primitives import Params
from arcagi.tasks import Grid

from . import act, fit
from . import view as ov

MAX_CANDIDATES = 4
type Joint = Callable[[Obj, Grid, Grid], set | None]


def recolor_move(grid: Grid, conn: str, attr: str, value: object, csrc, dsrc) -> Grid:
    grid, rows = act.values(grid, conn, attr, value, csrc, dsrc)
    moves = [
        (o.cells, [act.color(c)] * len(o.cells), act.direction(d)) for o, c, d in rows
    ]
    return act.slide(grid, moves)[0]


def move_extend(grid: Grid, conn: str, attr: str, value: object, msrc, esrc) -> Grid:
    grid, rows = act.values(grid, conn, attr, value, msrc, esrc)
    moves = [(o.cells, o.colors, act.direction(d)) for o, d, _ in rows]
    moved, final = act.slide(grid, moves)
    cells = {}
    for (o, _, e), where in zip(rows, final, strict=True):
        cells.update(act.rays(moved, where, o.colors, act.direction(e)))
    return act.paint(moved, cells)


def _shifts(o: Obj, target: Grid, bg: int, dirs=ov.DIRS):
    """``(dir, cells)`` of the first shift per direction where ``o``'s shape
    lands fully on one non-background color in ``target``."""
    height, width = g.shape(target)
    for name, (dy, dx) in dirs.items():
        for k in range(1, max(height, width)):
            moved = [(y + dy * k, x + dx * k) for y, x in o.cells]
            if not all(0 <= y < height and 0 <= x < width for y, x in moved):
                break
            if {target[y][x] for y, x in moved} - {bg} and len(
                {target[y][x] for y, x in moved}
            ) == 1:
                yield name, moved
                break


def _recolor_move_joint(o: Obj, state: Grid, target: Grid) -> set | None:
    if not changed(o, target):
        return None
    bg = bgc.of(state)
    found = set()
    for d, moved in _shifts(o, target, bg):
        found.add((target[moved[0][0]][moved[0][1]], d))
    return found or (None if fit.uniform(o, target) == bg else found)


def _move_extend_joint(o: Obj, state: Grid, target: Grid) -> set | None:
    """An object may look unchanged (its ray crosses its old place)."""
    if state == target:
        return None
    bg = bgc.of(state)
    height, width = g.shape(state)
    own = set(o.cells)
    found = set()
    for d in fit.shift_dirs(o, target):
        dy, dx = ov.DIRS[d]
        for k in range(1, max(height, width)):
            moved = [(y + dy * k, x + dx * k) for y, x in o.cells]
            if all(
                0 <= y < height and 0 <= x < width and target[y][x] == c
                for (y, x), c in zip(moved, o.colors, strict=True)
            ):
                break
        here = set(moved)
        for e, (ey, ex_) in ov.DIRS.items():
            for (y, x), c in zip(moved, o.colors, strict=True):
                ny, nx = y + ey, x + ex_
                if (ny, nx) in here or not (0 <= ny < height and 0 <= nx < width):
                    continue
                free = state[ny][nx] == bg or (ny, nx) in own
                if free and target[ny][nx] == c:
                    found.add((d, e))
                    break
    if not changed(o, target):
        return found or None
    return found or (None if fit.uniform(o, target) == bg else found)


def _rows(joint: Joint, conn: str, states, outs) -> fit.Targets | None:
    rows: fit.Targets = []
    n = 0
    for state, target in zip(states, outs, strict=True):
        row = [(o, joint(o, state, target)) for o in extract(state, conn)]
        if any(v is not None and not v for _, v in row):
            return None
        n += sum(v is not None for _, v in row)
        rows.append(row)
    return rows if n >= fit.MIN_OBJECTS else None


def _project(states, rows: fit.Targets, part) -> fit.Targets:
    """``part(o, joint, state)`` per targeted object (None stays None)."""
    return [
        [(o, None if w is None else part(o, w, state)) for o, w in row]
        for state, row in zip(states, rows, strict=True)
    ]


def _source_value(source: object, o: Obj, state: Grid) -> object:
    try:
        return ex.run_on_object(source, state, o)
    except fit.ERRORS:
        return None


def _selectors(states, outs, conn: str, rows: fit.Targets):
    """Targeted objects True, unchanged ones False (erased: don't care)."""
    examples = [
        [
            (o, True if w is not None else None if changed(o, t) else False)
            for o, w in row
        ]
        for t, row in zip(outs, rows, strict=True)
    ]
    found: list[tuple[str, object]] = list(separate(examples))
    labels = [[lab for _, lab in e] for e in examples]
    found += [("pred", n) for n in pred_selectors(states, conn, labels)]
    return found[: fit.MAX_SELECTORS]


def _fit(prim, joint: Joint, kind_a: str, kind_b: str, states, outs) -> list[Params]:
    if not same_shapes(states, outs) or all(
        s == t for s, t in zip(states, outs, strict=True)
    ):
        return []
    found: list[Params] = []
    for conn in CONNS:
        try:
            rows = _rows(joint, conn, states, outs)
        except fit.ERRORS:
            continue
        if rows is None:
            continue
        a_rows = _project(states, rows, lambda _o, w, _s: {a for a, _ in w})
        for sa in fit.sources(kind_a, states, a_rows):

            def given(o: Obj, w: set, state: Grid, sa=sa) -> set:
                va = _source_value(sa, o, state)
                return {b for a, b in w if a == va}

            b_rows = _project(states, rows, given)
            for sb in fit.sources(kind_b, states, b_rows):
                for attr, value in _selectors(states, outs, conn, rows):
                    params = (conn, attr, value, sa, sb)
                    if act.all_hold(prim, params, states, outs):
                        found.append(params)
                        break
        if len(found) >= MAX_CANDIDATES:
            break
    return found[:MAX_CANDIDATES]


def recolor_move_cands(states: Sequence[Grid], outs: Sequence[Grid]) -> list[Params]:
    found = _fit(recolor_move, _recolor_move_joint, "recolor", "move", states, outs)
    # The object's own color makes this a plain move_from.
    return [p for p in found if ex.unwrap_object(p[3])["sel"][0] != "this"]


def move_extend_cands(states: Sequence[Grid], outs: Sequence[Grid]) -> list[Params]:
    return _fit(move_extend, _move_extend_joint, "move", "extend", states, outs)
