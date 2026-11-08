"""Primitives whose size parameters are formulas over the current grid's features.

Each dimension parameter is a live formula block name (str), an inline body
(list, see ``arcagi.dsl.formula``) or ``["const", k]``. ``candidates`` only
fire when the target size differs from the current grid's and the size
relation is not one constant ratio (fixed ratios belong to ``tile`` /
``upscale``); they fit the live library first, then a small direct search.

- ``tile_n(ny, nx)``      repeat the grid ny x nx times
- ``upscale_n(fy, fx)``   scale every cell by fy x fx
- ``resize_crop(h, w)``   crop / pad (background) from the top-left corner
- ``canvas(h, w, color)`` a new single-color canvas; color is 0-9, ``"fg"``
  (most frequent non-background color) or ``"bg"``
"""

from collections.abc import Sequence

from arcagi.tasks import Grid

from . import background as bgc
from . import formula as fm
from . import grid as g
from .features import compute, fg_color
from .primitives import Params, Primitive

MAX_SIDE = 30


def _dim(ref: object, grid: Grid) -> int:
    value = fm.evaluate(fm.resolve(ref), compute(grid))
    if not 0 < value <= MAX_SIDE:
        raise ValueError("formula size out of range")
    return value


def _ref(body: list | None) -> object:
    """Prefer the live block name over the inline body (cheaper to describe)."""
    if body is None:
        return None
    for name, live in fm.LIVE.items():
        if live == body:
            return name
    return body


def _fit_dims(
    states: Sequence[Grid], ys_h: list[int], ys_w: list[int]
) -> Params | None:
    """Two dimension refs; None if a dimension has no formula or both constant."""
    if len(set(ys_h)) == 1 and len(set(ys_w)) == 1:
        return None
    xs = [compute(s) for s in states]
    refs = []
    for ys in (ys_h, ys_w):
        body = fm.fit_dim(xs, ys, fm.LIVE)
        if body is None:
            return None
        refs.append(body if body[0] == "const" else _ref(body))
    return tuple(refs)


def _differs(states: Sequence[Grid], targets: Sequence[Grid]) -> bool:
    return len(states) >= 2 and any(
        g.shape(s) != g.shape(t) for s, t in zip(states, targets, strict=True)
    )


def _ratio_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not _differs(states, targets):
        return []
    ny, nx = [], []
    for s, t in zip(states, targets, strict=True):
        (sh, sw), (th, tw) = g.shape(s), g.shape(t)
        if th % sh or tw % sw:
            return []
        ny.append(th // sh)
        nx.append(tw // sw)
    refs = _fit_dims(states, ny, nx)
    return [refs] if refs else []


def _size_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not _differs(states, targets):
        return []
    hs = [g.shape(t)[0] for t in targets]
    ws = [g.shape(t)[1] for t in targets]
    refs = _fit_dims(states, hs, ws)
    return [refs] if refs else []


def _canvas_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not _differs(states, targets):
        return []
    colors = []
    for t in targets:
        seen = set(g.color_counts(t))
        if len(seen) != 1:
            return []
        colors.append(next(iter(seen)))
    if len(set(colors)) == 1:
        color: object = colors[0]
    elif all(fg_color(s) == c for s, c in zip(states, colors, strict=True)):
        color = "fg"
    elif all(bgc.of(s) == c for s, c in zip(states, colors, strict=True)):
        color = "bg"
    else:
        return []
    return [(*refs, color) for refs in _size_candidates(states, targets)]


def tile_n(grid: Grid, ny: object, nx: object) -> Grid:
    return g.tile(grid, _dim(ny, grid), _dim(nx, grid))


def upscale_n(grid: Grid, fy: object, fx: object) -> Grid:
    return g.upscale(grid, _dim(fy, grid), _dim(fx, grid))


def resize_crop(grid: Grid, h: object, w: object) -> Grid:
    height, width = _dim(h, grid), _dim(w, grid)
    bg = bgc.of(grid)
    rows = [list(row[:width]) + [bg] * (width - len(row)) for row in grid[:height]]
    rows += [[bg] * width for _ in range(height - len(rows))]
    return tuple(tuple(row) for row in rows)


def canvas(grid: Grid, h: object, w: object, color: object) -> Grid:
    height, width = _dim(h, grid), _dim(w, grid)
    if color == "fg":
        color = fg_color(grid)
    elif color == "bg":
        color = bgc.of(grid)
    if not isinstance(color, int) or not 0 <= color <= 9:
        raise ValueError("bad canvas color")
    return tuple(tuple([color] * width) for _ in range(height))


FORMULA_PRIMS: dict[str, Primitive] = {
    "tile_n": Primitive("tile_n", tile_n, _ratio_candidates),
    "upscale_n": Primitive("upscale_n", upscale_n, _ratio_candidates),
    "resize_crop": Primitive("resize_crop", resize_crop, _size_candidates),
    "canvas": Primitive("canvas", canvas, _canvas_candidates),
}


def install(rules: dict[str, object]) -> None:
    """Register live formula blocks (name -> ``_rule.json``) as the library.

    Extract features a rule reads (its ``extracts``) join ``features.EXTRA``.
    """
    bodies, scores = {}, {}
    for name, rule in rules.items():
        fm.adopt(rule)  # its extract features, before validating the body
        body = rule.get("body") if isinstance(rule, dict) else None
        if fm.validate(body):
            bodies[name] = body
            score = rule.get("score", 0)  # type: ignore[union-attr]
            scores[name] = score if isinstance(score, (int, float)) else 0
    fm.install(bodies, scores)  # type: ignore[arg-type]


__all__ = ["FORMULA_PRIMS", "install"]
