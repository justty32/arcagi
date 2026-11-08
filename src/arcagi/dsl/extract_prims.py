"""Primitives whose parameter is an extraction (a live block name or a body).

``crop_extract(e)`` returns the extracted subgrid / object, ``fill_extract(e)``
paints the whole grid with the extracted color, ``recolor_extract(e)`` paints
every foreground cell with it, ``keep_extract(e)`` keeps only the selected
objects and ``paint_count(e, color, mode)`` draws the extracted number as a
``row`` (1 x n), ``col`` (n x 1) or ``square`` (n x n) of ``color``.

``candidates`` first tries the live extract blocks (``install``), and only when
none fits enumerates a few direct bodies (``DIRECT_*``). Each starts with a cheap
shape test and returns ``[]`` at once when the primitive cannot apply.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence

from arcagi.tasks import Grid

from . import extract as ex
from . import grid as g
from .primitives import Params, Primitive

MAX_HITS = 2  # parameters returned per primitive
DIRECT_CONNS = ("4same", "8same", "4multi", "8multi")
DIRECT_SINGLE = ("largest", "smallest", "unique_color", "unique_shape")
MODES = ("row", "col", "square")


def install(rules: Mapping[str, object]) -> None:
    ex.install(rules)


def _color(value: object) -> int:
    if not isinstance(value, int) or not 0 <= value <= 9:
        raise ValueError("extracted value is not a color")
    return value


def _crop_extract(grid: Grid, body: object) -> Grid:
    if ex.unwrap(body)[0] not in ex.GRID_PROPS:
        raise ValueError("crop_extract needs a grid-valued extraction")
    return ex.as_grid(ex.run(body, grid))


def _fill_extract(grid: Grid, body: object) -> Grid:
    color = _color(ex.run(body, grid))
    height, width = g.shape(grid)
    return tuple((color,) * width for _ in range(height))


def _recolor_extract(grid: Grid, body: object) -> Grid:
    color, bg = _color(ex.run(body, grid)), g.background(grid)
    return tuple(tuple(v if v == bg else color for v in row) for row in grid)


def _keep_extract(grid: Grid, body: object) -> Grid:
    _, sel = ex.unwrap(body)
    keep = {c for o in ex.select(grid, sel) for c in o.cells}  # type: ignore[arg-type]
    bg = g.background(grid)
    return tuple(
        tuple(v if (y, x) in keep else bg for x, v in enumerate(row))
        for y, row in enumerate(grid)
    )


def _paint_count(grid: Grid, body: object, color: object, mode: str) -> Grid:
    """``color`` is a fixed color or a color extraction (block name / body)."""
    n = ex.run(body, grid)
    if not isinstance(color, int):
        color = _color(ex.run(color, grid))
    if not isinstance(n, int) or not 0 < n <= 30 or mode not in MODES:
        raise ValueError("count out of range")
    height, width = (1, n) if mode == "row" else (n, 1) if mode == "col" else (n, n)
    return tuple((color,) * width for _ in range(height))


def _direct(props: Sequence[str], extra: Iterable[list] = ()) -> list[list]:
    sels = [[op, conn] for conn in DIRECT_CONNS for op in DIRECT_SINGLE]
    sels += list(extra)
    return [[p, s] for p in props for s in sels]


def _find(
    props: Sequence[str],
    fits: Callable[[object], bool],
    direct: Callable[[], list[list]],
) -> list[Params]:
    """Live block names whose body fits, else direct bodies that fit."""
    hits: list[Params] = []
    for name, body in ex.LIVE.items():
        if body[0] in props and fits(body):
            hits.append((name,))
            if len(hits) >= MAX_HITS:
                return hits
    if hits:
        return hits
    for body in direct():
        if fits(body):
            hits.append((body,))
            if len(hits) >= MAX_HITS:
                break
    return hits


def _all(fn: Callable[[Grid, Grid], bool], pairs) -> bool:
    try:
        return all(fn(s, t) for s, t in pairs)
    except (ValueError, IndexError, KeyError, TypeError):
        return False


def _uniform(grid: Grid) -> int | None:
    colors = {v for row in grid for v in row}
    return next(iter(colors)) if len(colors) == 1 else None


def _crop_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    pairs = list(zip(states, targets, strict=True))
    shapes = [(g.shape(s), g.shape(t)) for s, t in pairs]
    if all(a == b for a, b in shapes) or any(
        b[0] > a[0] or b[1] > a[1] for a, b in shapes
    ):
        return []

    def fits(body: object) -> bool:
        return _all(lambda s, t: _crop_extract(s, body) == t, pairs)

    return _find(ex.GRID_PROPS, fits, lambda: _direct(ex.GRID_PROPS))


def _fill_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    colors = [_uniform(t) for t in targets]
    if None in colors or len(set(colors)) < 2:
        return []
    pairs = list(zip(states, colors, strict=True))

    def fits(body: object) -> bool:
        return _all(lambda s, c: ex.run(body, s) == c, pairs)

    return _find(("color",), fits, lambda: _direct(("color",)))


def _recolor_candidates(
    states: Sequence[Grid], targets: Sequence[Grid]
) -> list[Params]:
    pairs = list(zip(states, targets, strict=True))
    if any(g.shape(s) != g.shape(t) for s, t in pairs):
        return []
    fgs = [set(g.color_counts(t)) - {g.background(s)} for s, t in pairs]
    if any(len(fg) != 1 for fg in fgs) or len(set.union(*fgs)) < 2:
        return []

    def fits(body: object) -> bool:
        return _all(lambda s, t: _recolor_extract(s, body) == t, pairs)

    return _find(("color",), fits, lambda: _direct(("color",)))


def _keep_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    pairs = list(zip(states, targets, strict=True))
    if any(g.shape(s) != g.shape(t) or s == t for s, t in pairs):
        return []

    def fits(body: object) -> bool:
        return _all(lambda s, t: _keep_extract(s, body) == t, pairs)

    return _find(("cells",), fits, lambda: _direct(("cells",)))


def _count_mode(targets: Sequence[Grid]) -> str | None:
    shapes = [g.shape(t) for t in targets]
    for mode, ok in (
        ("row", lambda h, w: h == 1),
        ("col", lambda h, w: w == 1),
        ("square", lambda h, w: h == w),
    ):
        if all(ok(h, w) for h, w in shapes):
            return mode
    return None


def _count_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    colors = [_uniform(t) for t in targets]
    mode = _count_mode(targets)
    if None in colors or mode is None or len({g.shape(t) for t in targets}) < 2:
        return []
    color: object = colors[0]
    if len(set(colors)) > 1:  # the color itself is extracted
        cpairs = list(zip(states, colors, strict=True))
        extra = [["all", c] for c in DIRECT_CONNS]
        found = _find(
            ("color",),
            lambda b: _all(lambda s, c: ex.run(b, s) == c, cpairs),
            lambda: _direct(("color",), extra),
        )
        if not found:
            return []
        color = found[0][0]
    pairs = list(zip(states, targets, strict=True))

    def fits(body: object) -> bool:
        return _all(lambda s, t: _paint_count(s, body, color, mode) == t, pairs)  # type: ignore[arg-type]

    def direct() -> list[list]:
        seen = sorted({v for s in states for v in g.color_counts(s)})
        extra = [["all", c] for c in DIRECT_CONNS]
        extra += [["color", c, v] for c in ("4same", "8same") for v in seen]
        return _direct(("count", "size"), extra)

    found = _find(("count", "size"), fits, direct)
    return [(*p, color, mode) for p in found]


EXTRACT_PRIMS: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("crop_extract", _crop_extract, _crop_candidates),
        Primitive("fill_extract", _fill_extract, _fill_candidates),
        Primitive("recolor_extract", _recolor_extract, _recolor_candidates),
        Primitive("keep_extract", _keep_extract, _keep_candidates),
        Primitive("paint_count", _paint_count, _count_candidates),
    )
}

__all__ = ["EXTRACT_PRIMS", "install"]
