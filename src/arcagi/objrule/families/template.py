"""Templates: copy an in-grid multi-colored template onto marker objects.

``template_paste(grid, mode)``: templates are the ``8multi`` objects with >= 2
colors; markers are the ``4same`` objects lying outside every template.

- ``fill``: a single-colored marker whose box has a template's height and
  width is overwritten by that template (the first such template);
- ``anchor``: a one-cell marker of color ``c`` receives the template holding
  exactly one cell of ``c``, placed with that cell on the marker;
- ``center``: a one-cell marker receives the single template, its box
  centered on the marker (odd height and width only).

Pasting writes the template's cells (``anchor`` / ``center``: onto background
cells only, off-grid cells dropped). A grid without templates or markers is
unchanged.

Fitting: tries each mode; >= 3 markers pasted over the train pairs and the
candidate must reproduce every train pair.
"""

from collections.abc import Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import Obj, extract
from arcagi.dsl.primitives import Params, Primitive
from arcagi.tasks import Grid

from . import keyed

MODES = ("fill", "anchor", "center")


def _parts(grid: Grid) -> tuple[list[Obj], list[Obj]]:
    templates = [o for o in extract(grid, "8multi") if len(set(o.colors)) >= 2]
    used = {c for t in templates for c in t.cells}
    markers = [o for o in extract(grid, "4same") if not used & set(o.cells)]
    return templates, markers


def _pastes(grid: Grid, mode: str):
    """``(template, dy, dx, overwrite)`` per pasted marker."""
    templates, markers = _parts(grid)
    out = []
    for m in markers:
        top, left, h, w = g.cells_bbox(list(m.cells))
        if mode == "fill":
            for t in templates:
                tt, tl, th, tw = g.cells_bbox(list(t.cells))
                if (th, tw) == (h, w) and len(set(m.colors)) == 1:
                    out.append((t, top - tt, left - tl, True))
                    break
            continue
        if len(m.cells) != 1:
            continue
        (y, x), c = m.cells[0], m.colors[0]
        if mode == "anchor":
            hits = [t for t in templates if t.colors.count(c) == 1]
            if len(hits) == 1:
                ty, tx = hits[0].cells[hits[0].colors.index(c)]
                out.append((hits[0], y - ty, x - tx, False))
        elif len(templates) == 1:
            tt, tl, th, tw = g.cells_bbox(list(templates[0].cells))
            if th % 2 and tw % 2:
                out.append((templates[0], y - tt - th // 2, x - tl - tw // 2, False))
    return out


def template_paste(grid: Grid, mode: str) -> Grid:
    grid = tuple(tuple(row) for row in grid)
    if mode not in MODES:
        raise ValueError(f"bad template mode {mode!r}")
    bg = bgc.of(grid)
    height, width = g.shape(grid)
    rows = [list(row) for row in grid]
    for t, dy, dx, overwrite in _pastes(grid, mode):
        for (y, x), c in zip(t.cells, t.colors, strict=True):
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                if overwrite or grid[ny][nx] == bg:
                    rows[ny][nx] = c
    return tuple(tuple(row) for row in rows)


def candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not keyed.same_shapes(states, targets) or all(
        s == t for s, t in zip(states, targets, strict=True)
    ):
        return []
    for mode in MODES:
        if sum(len(_pastes(s, mode)) for s in states) < keyed.MIN_OBJECTS:
            continue
        if all(
            template_paste(s, mode) == t for s, t in zip(states, targets, strict=True)
        ):
            return [(mode,)]
    return []


TEMPLATE_PRIMS = {
    "template_paste": Primitive("template_paste", template_paste, candidates)
}
