"""Per-object rule primitives: a selector plus an action whose parameter comes
from an object-scope extraction evaluated on each selected object.

Parameters are ``(conn, attr, value, source)``: ``(conn, attr, value)`` selects
objects like ``recolor_sel`` (``attr == "pred"`` names a predicate), ``source``
is a live object-extract block name (``extract_<hash>``) or an inline body.
``recolor_from`` paints each object with its source color, ``move_from`` slides
it in its source direction until blocked, ``extend_from`` draws rays from it in
its source direction over the background. Values are read on the input grid;
an object whose source value is undefined is left unchanged. Directions cover
the diagonals too (``view.DIRS8``); the 8-direction fit runs only when the
4-direction one finds nothing. Round 5 adds ``recolor_move`` / ``move_extend``
(``two_step``) and ``move_by``
(``param_source``: distance = formula of object features).
"""

from collections.abc import Sequence

from arcagi.dsl.objects_props import CONNS, same_shapes
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import act, fit, param_source, two_step

MAX_CANDIDATES = 6


def recolor_from(grid: Grid, conn: str, attr: str, value: object, source) -> Grid:
    grid, pairs = act.values(grid, conn, attr, value, source)
    cells = {}
    for o, c in pairs:
        cells.update({cell: act.color(c) for cell in o.cells})
    return act.paint(grid, cells)


def move_from(grid: Grid, conn: str, attr: str, value: object, source) -> Grid:
    """Slide each selected object toward its source direction until blocked."""
    grid, pairs = act.values(grid, conn, attr, value, source)
    moves = [(o.cells, o.colors, act.direction(d)) for o, d in pairs]
    return act.slide(grid, moves)[0]


def extend_from(grid: Grid, conn: str, attr: str, value: object, source) -> Grid:
    """Ray from each selected object's cells in its source direction."""
    grid, pairs = act.values(grid, conn, attr, value, source)
    cells = {}
    for o, d in pairs:
        cells.update(act.rays(grid, o.cells, o.colors, act.direction(d)))
    return act.paint(grid, cells)


def _cheap_reject(states: Sequence[Grid], outs: Sequence[Grid]) -> bool:
    return not same_shapes(states, outs) or all(
        s == t for s, t in zip(states, outs, strict=True)
    )


def _fit(kind: str, states: Sequence[Grid], outs: Sequence[Grid]) -> list[Params]:
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


def _candidates(kind: str, fallback: str | None = None):
    """Fit ``kind``; when nothing fits, the 8-direction ``fallback`` kind."""

    def candidates(states: Sequence[Grid], outs: Sequence[Grid]) -> list[Params]:
        if _cheap_reject(states, outs):
            return []
        found = _fit(kind, states, outs)
        if not found and fallback is not None:
            found = _fit(fallback, states, outs)
        return found

    return candidates


OBJRULE_PRIMS: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("recolor_from", recolor_from, _candidates("recolor")),
        Primitive("move_from", move_from, _candidates("move", "move8")),
        Primitive("extend_from", extend_from, _candidates("extend", "extend8")),
        Primitive("recolor_move", two_step.recolor_move, two_step.recolor_move_cands),
        Primitive("move_extend", two_step.move_extend, two_step.move_extend_cands),
        Primitive("move_by", param_source.move_by, param_source.candidates),
    )
}
# Side line S3 registration point (objrule/families/); built-ins take priority.
from .families import FAMILY_PRIMS  # noqa: E402

OBJRULE_PRIMS.update({k: v for k, v in FAMILY_PRIMS.items() if k not in OBJRULE_PRIMS})
