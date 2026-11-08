"""Primitive registry: name -> parameter inference + grid transform.

Every primitive maps one grid to one grid. ``candidates`` proposes parameter
tuples from the current intermediate train grids and their target outputs, so
parameters are inferred from the examples instead of blindly enumerated. Color
10 is an internal marker that a later ``colormap`` step must resolve to 0-9.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from arcagi.tasks import Grid

from . import grid as g

MARK = 10
type Params = tuple[object, ...]
type Candidates = Callable[[Sequence[Grid], Sequence[Grid]], Iterable[Params]]


@dataclass(frozen=True)
class Primitive:
    name: str
    apply: Callable[..., Grid]
    candidates: Candidates


def _no_params(_states: Sequence[Grid], _targets: Sequence[Grid]) -> list[Params]:
    return [()]


def _ratios(
    states: Sequence[Grid], targets: Sequence[Grid], *, grow: bool
) -> list[Params]:
    """Integer (fy, fx) with target = state * f (grow) or state / f, same for all."""
    found = None
    for state, target in zip(states, targets, strict=True):
        (sh, sw), (th, tw) = g.shape(state), g.shape(target)
        big, small = ((th, tw), (sh, sw)) if grow else ((sh, sw), (th, tw))
        if big[0] % small[0] or big[1] % small[1]:
            return []
        ratio = (big[0] // small[0], big[1] // small[1])
        if ratio == (1, 1) or (found is not None and ratio != found):
            return []
        found = ratio
    return [found] if found and max(found) <= 10 else []


def _mirror_tile(grid: Grid, mode: str) -> Grid:
    if mode == "lr":
        return tuple(row + row[::-1] for row in grid)
    if mode == "ud":
        return grid + grid[::-1]
    top = tuple(row + row[::-1] for row in grid)
    return top + top[::-1]


def _crop_bbox(grid: Grid) -> Grid:
    box = g.bbox(grid, g.background(grid))
    if box is None:
        raise ValueError("empty grid content")
    return g.crop(grid, *box)


def _halves(grid: Grid, axis: str) -> tuple[Grid, Grid]:
    """Split in two along ``axis``; a full single-color middle line is dropped."""
    work = grid if axis == "h" else g.transpose(grid)
    height = len(work)
    if height % 2 == 1:
        middle = work[height // 2]
        if len(set(middle)) != 1:
            raise ValueError("odd split without separator")
        a, b = work[: height // 2], work[height // 2 + 1 :]
    else:
        a, b = work[: height // 2], work[height // 2 :]
    if axis == "v":
        a, b = g.transpose(a), g.transpose(b)
    return a, b


_OPS: dict[str, Callable[[bool, bool], bool]] = {
    "and": lambda x, y: x and y,
    "or": lambda x, y: x or y,
    "xor": lambda x, y: x != y,
    "nor": lambda x, y: not (x or y),
    "left": lambda x, y: x and not y,
}


def _split_overlay(grid: Grid, axis: str, op: str) -> Grid:
    a, b = _halves(grid, axis)
    bg = 0 if any(0 in row for row in grid) else g.background(grid)
    fn = _OPS[op]
    return tuple(
        tuple(MARK if fn(x != bg, y != bg) else 0 for x, y in zip(ra, rb, strict=True))
        for ra, rb in zip(a, b, strict=True)
    )


def _split_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    out = []
    for axis in ("h", "v"):
        try:
            if all(
                g.shape(_halves(s, axis)[0]) == g.shape(t)
                for s, t in zip(states, targets, strict=True)
            ):
                out.extend((axis, op) for op in _OPS)
        except ValueError:
            continue
    return out


def _select(objs: list[list[tuple[int, int]]], grid: Grid, how: str):
    if how == "largest":
        return max(objs, key=len)
    if how == "smallest":
        return min(objs, key=len)
    if how == "top_left":
        return objs[0]
    colors = [frozenset(grid[y][x] for y, x in cells) for cells in objs]
    if how == "most_colors":
        return objs[max(range(len(objs)), key=lambda i: len(colors[i]))]
    if how == "unique_color":
        singles = [next(iter(c)) for c in colors if len(c) == 1]
        unique = [
            o
            for o, c in zip(objs, colors, strict=True)
            if len(c) == 1 and singles.count(next(iter(c))) == 1
        ]
        if len(unique) != 1:
            raise ValueError("no unique-color object")
        return unique[0]
    raise ValueError(how)


def _crop_object(grid: Grid, conn: str, how: str) -> Grid:
    bg = g.background(grid)
    objs = g.objects(grid, bg, diagonal=conn == "8multi", by_color=conn == "4same")
    if not objs:
        raise ValueError("no objects")
    return g.crop(grid, *g.cells_bbox(_select(objs, grid, how)))


def _object_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if any(g.shape(t) == g.shape(s) for s, t in zip(states, targets, strict=True)):
        return []
    return [
        (conn, how)
        for conn in ("4same", "8multi")
        for how in ("largest", "smallest", "unique_color", "most_colors", "top_left")
    ]


def _fill_enclosed(grid: Grid) -> Grid:
    """Paint background cells that cannot reach the border with the marker."""
    bg = g.background(grid)
    height, width = g.shape(grid)
    outside = [[False] * width for _ in range(height)]
    stack = [
        (r, c)
        for r in range(height)
        for c in range(width)
        if (r in (0, height - 1) or c in (0, width - 1)) and grid[r][c] == bg
    ]
    for r, c in stack:
        outside[r][c] = True
    while stack:
        r, c = stack.pop()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < height and 0 <= nc < width and not outside[nr][nc]:
                if grid[nr][nc] == bg:
                    outside[nr][nc] = True
                    stack.append((nr, nc))
    return tuple(
        tuple(MARK if v == bg and not outside[r][c] else v for c, v in enumerate(row))
        for r, row in enumerate(grid)
    )


def _same_shape(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    same = all(g.shape(s) == g.shape(t) for s, t in zip(states, targets, strict=True))
    return [()] if same else []


BASE: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("flip_lr", g.flip_lr, _no_params),
        Primitive("flip_ud", g.flip_ud, _no_params),
        Primitive("transpose", g.transpose, _no_params),
        Primitive("rot90", g.rot90, _no_params),
        Primitive("rot180", g.rot180, _no_params),
        Primitive("rot270", g.rot270, _no_params),
        Primitive("anti_transpose", g.anti_transpose, _no_params),
        Primitive("upscale", g.upscale, lambda s, t: _ratios(s, t, grow=True)),
        Primitive("tile", g.tile, lambda s, t: _ratios(s, t, grow=True)),
        Primitive("downscale", g.downscale, lambda s, t: _ratios(s, t, grow=False)),
        Primitive(
            "mirror_tile", _mirror_tile, lambda s, t: [("lr",), ("ud",), ("quad",)]
        ),
        Primitive("crop_bbox", _crop_bbox, _no_params),
        Primitive("split_overlay", _split_overlay, _split_candidates),
        Primitive("crop_object", _crop_object, _object_candidates),
        Primitive("fill_enclosed", _fill_enclosed, _same_shape),
    )
}
