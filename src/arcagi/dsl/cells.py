"""Grid-cell primitives: split a board along full single-color separator lines.

A board is split only when full rows and/or columns of one non-background color
cut it into at least two equally sized cells (an outer frame is allowed). Each
primitive splits internally; ``candidates`` returns ``[]`` immediately when any
train state has no such split, so these primitives cost almost nothing on other
tasks. Marker color 10 is left for a terminal ``colormap`` step to resolve.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from functools import lru_cache

from arcagi.tasks import Grid

from . import grid as g
from .primitives import MARK, Params, Primitive

type Layout = tuple[int, tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]


def _runs(length: int, lines: set[int]) -> list[tuple[int, int]]:
    """Maximal (start, size) stretches of indices not in ``lines``."""
    runs, start = [], None
    for i in range(length + 1):
        if i < length and i not in lines:
            start = i if start is None else start
        elif start is not None:
            runs.append((start, i - start))
            start = None
    return runs


@lru_cache(maxsize=8192)
def split(grid: Grid) -> Layout | None:
    """(separator color, row runs, column runs) of an equal-cell split, or None.

    The separator color must differ from the dominant color inside the cells, so
    empty background rows in a sparse board do not count as separators.
    """
    height, width = g.shape(grid)
    full_rows = {r: row[0] for r, row in enumerate(grid) if len(set(row)) == 1}
    full_cols = {
        c: grid[0][c] for c in range(width) if len({row[c] for row in grid}) == 1
    }
    bg = g.background(grid)
    colors = set(full_rows.values()) | set(full_cols.values())
    for color in sorted(colors, key=lambda c: (c == bg, c)):
        rows = {r for r, v in full_rows.items() if v == color}
        cols = {c for c, v in full_cols.items() if v == color}
        if len(rows) == height or len(cols) == width:
            continue
        row_runs, col_runs = _runs(height, rows), _runs(width, cols)
        if len(row_runs) * len(col_runs) < 2:
            continue
        if len({n for _, n in row_runs}) != 1 or len({n for _, n in col_runs}) != 1:
            continue
        layout = (color, tuple(row_runs), tuple(col_runs))
        if _cell_bg(_cut(grid, layout)) != color:
            return layout
    return None


def _layout(grid: Grid) -> Layout:
    layout = split(grid)
    if layout is None:
        raise ValueError("no separator grid")
    return layout


def _cut(grid: Grid, layout: Layout) -> tuple[Grid, ...]:
    _, row_runs, col_runs = layout
    return tuple(
        tuple(row[c : c + w] for row in grid[r : r + h])
        for r, h in row_runs
        for c, w in col_runs
    )


@lru_cache(maxsize=8192)
def cells(grid: Grid) -> tuple[Grid, ...]:
    """Cells in row-major order; raises ValueError without a separator grid."""
    return _cut(grid, _layout(grid))


def _cell_bg(parts: Sequence[Grid]) -> int:
    counts: Counter[int] = Counter()
    for part in parts:
        counts.update(g.color_counts(part))
    return max(counts, key=lambda color: (counts[color], color == 0, -color))


def _colors(cell: Grid, bg: int) -> set[int]:
    return {v for row in cell for v in row if v != bg}


def _pixels(cell: Grid, bg: int) -> int:
    return sum(v != bg for row in cell for v in row)


def _mask(cell: Grid, bg: int) -> Grid:
    return tuple(tuple(v != bg for v in row) for row in cell)


def _argext(scores: list[int], pick: Callable[[list[int]], int]) -> int:
    best = pick(scores)
    if scores.count(best) != 1:
        raise ValueError("ambiguous cell")
    return scores.index(best)


def _unique(keys: list[object]) -> int:
    counts = Counter(keys)
    lone = [i for i, key in enumerate(keys) if counts[key] == 1]
    if len(lone) != 1:
        raise ValueError("no unique cell")
    return lone[0]


PICKS = (
    "unique",
    "unique_mask",
    "most_colors",
    "least_colors",
    "most_pixels",
    "least_pixels",
)


def _pick_cell(grid: Grid, how: str, color: int = -1) -> Grid:
    parts = cells(grid)
    bg = _cell_bg(parts)
    if how == "unique":
        return parts[_unique(list(parts))]
    if how == "unique_mask":
        return parts[_unique([_mask(p, bg) for p in parts])]
    if how == "has_color":
        hits = [i for i, p in enumerate(parts) if color in _colors(p, bg)]
        if len(hits) != 1:
            raise ValueError("color not in exactly one cell")
        return parts[hits[0]]
    if how in ("most_colors", "least_colors"):
        scores = [len(_colors(p, bg)) for p in parts]
    elif how in ("most_pixels", "least_pixels"):
        scores = [_pixels(p, bg) for p in parts]
    else:
        raise ValueError(how)
    return parts[_argext(scores, max if how.startswith("most") else min)]


def _layouts(states: Sequence[Grid]) -> list[Layout] | None:
    out = []
    for state in states:
        layout = split(state)
        if layout is None:
            return None
        out.append(layout)
    return out


def _cell_shape(layout: Layout) -> tuple[int, int]:
    return layout[1][0][1], layout[2][0][1]


def _pick_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    layouts = _layouts(states)
    if layouts is None or any(
        _cell_shape(lay) != g.shape(t) for lay, t in zip(layouts, targets, strict=True)
    ):
        return []
    out: list[Params] = [(how,) for how in PICKS]
    shared: set[int] | None = None
    for state, lay in zip(states, layouts, strict=True):
        parts = cells(state)
        bg = _cell_bg(parts)
        seen = Counter(c for p in parts for c in _colors(p, bg))
        lone = {c for c, n in seen.items() if n == 1 and c != lay[0]}
        shared = lone if shared is None else shared & lone
    out.extend(("has_color", c) for c in sorted(shared or ()))
    return out


_OPS: dict[str, Callable[[int, int], bool]] = {
    "and": lambda hits, n: hits == n,
    "or": lambda hits, n: hits > 0,
    "xor": lambda hits, n: hits == 1,
    "nor": lambda hits, n: hits == 0,
}


def _overlay_cells(grid: Grid, op: str) -> Grid:
    """MARK where ``op`` holds over the cells' non-background masks, else 0.

    ``stack``/``stack_rev`` keep colors: first non-background value in cell order.
    """
    parts = cells(grid)
    bg = _cell_bg(parts)
    if op in ("stack", "stack_rev"):
        order = parts if op == "stack" else parts[::-1]
        return tuple(
            tuple(next((v for v in pix if v != bg), bg) for pix in zip(*rows))
            for rows in zip(*order)
        )
    fn, n = _OPS[op], len(parts)
    height, width = g.shape(parts[0])
    return tuple(
        tuple(
            MARK if fn(sum(p[r][c] != bg for p in parts), n) else 0
            for c in range(width)
        )
        for r in range(height)
    )


def _overlay_candidates(
    states: Sequence[Grid], targets: Sequence[Grid]
) -> list[Params]:
    layouts = _layouts(states)
    if layouts is None or any(
        _cell_shape(lay) != g.shape(t) for lay, t in zip(layouts, targets, strict=True)
    ):
        return []
    return [(op,) for op in (*_OPS, "stack", "stack_rev")]


def _summary(cell: Grid, bg: int, mode: str) -> int:
    counts = g.color_counts(cell)
    del counts[bg]
    if mode == "any":
        return MARK if counts else 0
    if mode == "uniform":
        full = len(counts) == 1 and sum(counts.values()) == len(cell) * len(cell[0])
        return next(iter(counts)) if full else bg
    if not counts:
        return bg
    return max(counts, key=lambda color: (counts[color], -color))


SUMMARIES = ("majority", "any", "uniform", "max_pixels")


def _summaries(parts: Sequence[Grid], mode: str) -> list[int]:
    bg = _cell_bg(parts)
    if mode == "max_pixels":
        counts = [_pixels(p, bg) for p in parts]
        return [MARK if n == max(counts) else 0 for n in counts]
    return [_summary(p, bg, mode) for p in parts]


def _cells_to_pixels(grid: Grid, mode: str) -> Grid:
    """One pixel per cell: majority color, any-content / max-pixels marker, uniform."""
    _, row_runs, col_runs = _layout(grid)
    flat = _summaries(cells(grid), mode)
    width = len(col_runs)
    return tuple(tuple(flat[i * width : (i + 1) * width]) for i in range(len(row_runs)))


def _pixels_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    layouts = _layouts(states)
    if layouts is None or any(
        (len(lay[1]), len(lay[2])) != g.shape(t)
        for lay, t in zip(layouts, targets, strict=True)
    ):
        return []
    return [(mode,) for mode in SUMMARIES]


def _fill_cells(grid: Grid, mode: str) -> Grid:
    """Same-size board with every cell painted by its summary (separators kept)."""
    _, row_runs, col_runs = _layout(grid)
    flat = _summaries(cells(grid), mode)
    out = [list(row) for row in grid]
    for i, (r, h) in enumerate(row_runs):
        for j, (c, w) in enumerate(col_runs):
            value = flat[i * len(col_runs) + j]
            for y in range(r, r + h):
                out[y][c : c + w] = [value] * w
    return tuple(tuple(row) for row in out)


def _fill_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    layouts = _layouts(states)
    if layouts is None or any(
        g.shape(s) != g.shape(t) for s, t in zip(states, targets, strict=True)
    ):
        return []
    return [(mode,) for mode in SUMMARIES]


CELLS: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("pick_cell", _pick_cell, _pick_candidates),
        Primitive("overlay_cells", _overlay_cells, _overlay_candidates),
        Primitive("cells_to_pixels", _cells_to_pixels, _pixels_candidates),
        Primitive("fill_cells", _fill_cells, _fill_candidates),
    )
}

__all__ = ["CELLS", "cells", "split"]
