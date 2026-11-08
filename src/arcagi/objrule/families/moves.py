"""Moves with a twist: one step toward the source, and erasing unmatched objects.

``move_ex(grid, conn, attr, value, source, how, rest)``: every selected object
whose object-scope ``source`` (as in ``objrule.prims.move_from``) gives a
direction moves that way: ``how == "slide"`` until blocked (``act.slide``),
``"step"`` exactly one cell (lifted first; a step off the grid or onto a
non-background cell is an error). Selected objects without a source value are
kept (``rest == "keep"``) or erased (``"erase"``). The built-in ``move_from``
is ``("slide", "keep")``, so that pair is never offered.

Fitting reuses ``objrule.fit`` (``move``, then ``move8`` targets, sources,
selectors; >= 3 moved objects, >= 2 distinct directions); candidates must
reproduce every train pair.
"""

from collections.abc import Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import extract as ex
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import CONNS, same_shapes, selected
from arcagi.dsl.primitives import Params, Primitive
from arcagi.objrule import act, fit
from arcagi.tasks import Grid

HOWS = ("slide", "step")
RESTS = ("keep", "erase")
MAX_CANDIDATES = 2


def move_ex(grid: Grid, conn, attr, value, source, how: str, rest: str) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    if how not in HOWS or rest not in RESTS:
        raise ValueError("bad move_ex mode")
    ex.unwrap_object(source)
    bg = bgc.of(grid)
    moves, erased = [], []
    for o in selected(grid, conn, attr, value):
        try:
            d = act.direction(ex.run_on_object(source, grid, o))
        except fit.ERRORS:
            erased.append(o)
            continue
        moves.append((o.cells, o.colors, d))
    if rest == "erase" and erased:
        grid = act.paint(grid, {c: bg for o in erased for c in o.cells})
    if how == "slide":
        return act.slide(grid, moves)[0]
    height, width = g.shape(grid)
    cells = {c: bg for cs, _, _ in moves for c in cs}
    lifted = act.paint(grid, cells)
    for cs, colors, (dy, dx) in moves:
        for (y, x), c in zip(cs, colors, strict=True):
            ny, nx = y + dy, x + dx
            if not (0 <= ny < height and 0 <= nx < width):
                raise ValueError("step off the grid")
            if lifted[ny][nx] != bg:
                raise ValueError("step onto an object")
            cells[(ny, nx)] = c
    return act.paint(grid, cells)


def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not same_shapes(states, targets) or all(
        s == t for s, t in zip(states, targets, strict=True)
    ):
        return []
    found: list[Params] = []
    for kind, conn in [(k, c) for k in ("move", "move8") for c in CONNS]:
        try:
            rows = fit.targets(kind, conn, states, targets)
        except fit.ERRORS:
            continue
        if rows is None:
            continue
        for source in fit.sources(kind, states, rows):
            sels = [("all", 1)] + fit.selectors(kind, conn, states, rows, source)
            for attr, value in sels:
                for how in HOWS:
                    for rest in RESTS:
                        if (how, rest) == ("slide", "keep"):
                            continue
                        params = (conn, attr, value, source, how, rest)
                        if act.all_hold(move_ex, params, states, targets):
                            found.append(params)
                            break
                    if found:
                        return found[:MAX_CANDIDATES]
    return found


MOVES_PRIMS = {"move_ex": Primitive("move_ex", move_ex, candidates)}
