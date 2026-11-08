"""Formula parameter source: shift each object by a distance computed from it.

``move_by(grid, conn, attr, value, direction, formula)`` lifts every selected
object and pastes it ``formula(object)`` cells toward ``direction`` (a name of
``view.DIRS8`` or an object-scope source giving one); cells pushed off the grid
are an error. ``formula`` uses the formula-block grammar of
``arcagi.dsl.formula`` (``["lin", x, a, b]`` / ``["div", x, k]``, evaluated by
``formula.evaluate``) over object features ``o_size`` / ``o_h`` / ``o_w``.
The live ``formula_*`` blocks read grid features, so they are not offered here.

Fitting: every changed object must reappear intact at some shift; the distance
must take >= 2 values over >= ``fit.MIN_OBJECTS`` objects (a constant shift is
a plain ``shift``), and the rule must reproduce every train pair.
"""

from collections.abc import Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import extract as ex
from arcagi.dsl import formula as fm
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import CONNS, Obj, changed, extract, same_shapes
from arcagi.dsl.primitives import Params
from arcagi.tasks import Grid

from . import act, fit
from . import view as ov

FEATS = ("o_size", "o_h", "o_w")
MAX_CANDIDATES = 3


def _check(formula: object) -> list:
    if not isinstance(formula, list) or len(formula) < 3 or formula[1] not in FEATS:
        raise ValueError(f"bad object formula {formula!r}")
    if formula[0] == "lin" and len(formula) == 4:
        if formula[2] in fm.A_RANGE and formula[3] in fm.B_RANGE:
            return formula
    if formula[0] == "div" and len(formula) == 3 and formula[2] in fm.K_RANGE:
        return formula
    raise ValueError(f"bad object formula {formula!r}")


def _dir_of(direction: object, grid: Grid, o: Obj) -> tuple[int, int]:
    if isinstance(direction, str) and direction in ov.DIRS8:
        return ov.DIRS8[direction]
    return act.direction(ex.run_on_object(direction, grid, o))


def move_by(grid: Grid, conn, attr, value, direction, formula) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    body = _check(formula)
    if not (isinstance(direction, str) and direction in ov.DIRS8):
        ex.unwrap_object(direction)
    bg = bgc.of(grid)
    height, width = g.shape(grid)
    moves = []
    for (o,) in act.values(grid, conn, attr, value)[1]:
        try:
            dy, dx = _dir_of(direction, grid, o)
        except fit.ERRORS:
            continue
        k = fm.evaluate(body, act.obj_feats(o))
        moves.append((o, dy * k, dx * k))
    cells = {cell: bg for o, _, _ in moves for cell in o.cells}
    for o, sy, sx in moves:
        for (y, x), c in zip(o.cells, o.colors, strict=True):
            if not (0 <= y + sy < height and 0 <= x + sx < width):
                raise ValueError("object pushed off the grid")
            cells[(y + sy, x + sx)] = c
    return act.paint(grid, cells)


def _shifts(o: Obj, target: Grid) -> dict[str, set[int]]:
    """Every ``dir -> {k}`` with ``o`` intact ``k`` cells away in ``target``."""
    height, width = g.shape(target)
    out: dict[str, set[int]] = {}
    for name, (dy, dx) in ov.DIRS8.items():
        for k in range(1, max(height, width)):
            moved = [(y + dy * k, x + dx * k) for y, x in o.cells]
            if not all(0 <= y < height and 0 <= x < width for y, x in moved):
                break
            if all(
                target[y][x] == c for (y, x), c in zip(moved, o.colors, strict=True)
            ):
                out.setdefault(name, set()).add(k)
    return out


def _bodies() -> list[list]:
    lin = [["lin", f, a, b] for f in FEATS for a in fm.A_RANGE for b in fm.B_RANGE]
    return lin + [["div", f, k] for f in FEATS for k in fm.K_RANGE]


BODIES = _bodies()


def _formula(objs: Sequence[tuple[Obj, set[int]]]) -> list | None:
    """Simplest body hitting every object's distance set; >= 2 distances."""
    best = None
    for body in BODIES:
        try:
            ks = [fm.evaluate(body, act.obj_feats(o)) for o, _ in objs]
        except fit.ERRORS:
            continue
        if all(k in want for k, (_, want) in zip(ks, objs)) and len(set(ks)) >= 2:
            if best is None or fm.length(body) < fm.length(best):
                best = body
    return best


def candidates(states: Sequence[Grid], outs: Sequence[Grid]) -> list[Params]:
    if not same_shapes(states, outs) or all(
        s == t for s, t in zip(states, outs, strict=True)
    ):
        return []
    found: list[Params] = []
    for conn in CONNS:
        try:
            moved = [
                (o, _shifts(o, t))
                for s, t in zip(states, outs, strict=True)
                for o in extract(s, conn)
                if changed(o, t)
            ]
        except fit.ERRORS:
            continue
        if len(moved) < fit.MIN_OBJECTS or not all(r for _, r in moved):
            continue
        for d in ov.DIRS8:
            if not all(d in r for _, r in moved):
                continue
            body = _formula([(o, r[d]) for o, r in moved])
            if body is None:
                continue
            for attr, value in (("all", 1),) + _attr_selectors(states, outs, conn):
                params = (conn, attr, value, d, body)
                if act.all_hold(move_by, params, states, outs):
                    found.append(params)
                    break
        if len(found) >= MAX_CANDIDATES:
            break
    return found[:MAX_CANDIDATES]


def _attr_selectors(states, outs, conn: str) -> tuple:
    from arcagi.dsl.objects_props import separate

    examples = [
        [(o, changed(o, t)) for o in extract(s, conn)]
        for s, t in zip(states, outs, strict=True)
    ]
    return tuple(separate(examples))
