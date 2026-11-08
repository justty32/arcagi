"""Second batch of primitives: self tiling, symmetry completion, gravity."""

from collections.abc import Sequence

from arcagi.tasks import Grid

from . import grid as g
from .primitives import Params, Primitive


def _self_tile(grid: Grid, mode: str) -> Grid:
    """Place a copy of the grid at every (non-)background cell of itself."""
    bg = g.background(grid)
    height, width = g.shape(grid)
    blank = tuple(bg for _ in range(width))
    rows = []
    for cell_row in grid:
        for y in range(height):
            row: list[int] = []
            for value in cell_row:
                filled = value != bg if mode == "pos" else value == bg
                row.extend(grid[y] if filled else blank)
            rows.append(tuple(row))
    return tuple(rows)


def _self_tile_candidates(
    states: Sequence[Grid], targets: Sequence[Grid]
) -> list[Params]:
    for state, target in zip(states, targets, strict=True):
        h, w = g.shape(state)
        if g.shape(target) != (h * h, w * w):
            return []
    return [("pos",), ("neg",)]


_MIRRORS = {
    "lr": (g.flip_lr,),
    "ud": (g.flip_ud,),
    "both": (g.flip_lr, g.flip_ud, g.rot180),
    "transpose": (g.transpose,),
    "rot": (g.rot90, g.rot180, g.rot270),
}


def _symmetrize(grid: Grid, mode: str, hole: int) -> Grid:
    """Fill ``hole`` cells from their mirror images under the chosen symmetry."""
    images = [fn(grid) for fn in _MIRRORS[mode]]
    if any(g.shape(image) != g.shape(grid) for image in images):
        raise ValueError("symmetry needs a matching shape")
    out = []
    for r, row in enumerate(grid):
        new = []
        for c, value in enumerate(row):
            if value == hole:
                for image in images:
                    if image[r][c] != hole:
                        value = image[r][c]
                        break
            new.append(value)
        out.append(tuple(new))
    return tuple(out)


def _symmetrize_candidates(
    states: Sequence[Grid], targets: Sequence[Grid]
) -> list[Params]:
    if any(g.shape(s) != g.shape(t) for s, t in zip(states, targets, strict=True)):
        return []
    holes = None
    for state, target in zip(states, targets, strict=True):
        gone = set(g.color_counts(state)) - set(g.color_counts(target))
        holes = gone if holes is None else holes & gone
    choices = sorted(holes or ()) or sorted({g.background(s) for s in states})
    if len(choices) > 1:
        return []
    return [(mode, choices[0]) for mode in _MIRRORS]


def _gravity(grid: Grid, direction: str) -> Grid:
    """Slide every non-background cell toward ``direction`` until blocked."""
    bg = g.background(grid)
    turn = {"down": 0, "left": 1, "up": 2, "right": 3}[direction]
    work = grid
    for _ in range(turn):
        work = g.rot90(work)
    cols = []
    for col in zip(*work, strict=True):
        filled = [v for v in col if v != bg]
        cols.append((bg,) * (len(col) - len(filled)) + tuple(filled))
    work = tuple(zip(*cols, strict=True))
    for _ in range(turn):
        work = g.rot270(work)
    return work


def _same_shape_dirs(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if any(g.shape(s) != g.shape(t) for s, t in zip(states, targets, strict=True)):
        return []
    return [("down",), ("up",), ("left",), ("right",)]


MORE: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("self_tile", _self_tile, _self_tile_candidates),
        Primitive("symmetrize", _symmetrize, _symmetrize_candidates),
        Primitive("gravity", _gravity, _same_shape_dirs),
    )
}
