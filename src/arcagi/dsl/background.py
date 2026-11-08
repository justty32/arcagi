"""Task-level background color shared by object extraction.

``Primitive.apply`` sees one grid at a time, so the search computes one
background for the whole task (``task_background``) and installs it here with
``set_task_background``; object code reads it through ``of(grid)``. With no
context set every grid falls back to its own most frequent color (round 2).
A grid where the task background covers less than ``MIN_SHARE`` of the cells
also falls back (dense mosaics, or test inputs with another palette): there the
task color is just another object color.
"""

from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from arcagi.tasks import Grid

from . import grid as g

MIN_SHARE = 0.4
_current: int | None = None


def task_background(grids: Iterable[Grid]) -> int | None:
    """Most frequent color over all ``grids``; ties go to the commonest border color.

    Remaining ties prefer 0, then the smaller color. ``None`` for no cells.
    """
    total: Counter[int] = Counter()
    border: Counter[int] = Counter()
    for grid in grids:
        if not grid or not grid[0]:
            continue
        for row in grid:
            total.update(row)
        height, width = len(grid), len(grid[0])
        for y in range(height):
            for x in range(width):
                if y in (0, height - 1) or x in (0, width - 1):
                    border[grid[y][x]] += 1
    if not total:
        return None
    top = max(total.values())
    tied = [c for c, n in total.items() if n == top]
    return max(tied, key=lambda c: (border[c], c == 0, -c))


def set_task_background(color: int | None) -> None:
    """Install (or clear with ``None``) the task background for object code."""
    global _current
    if color is not None and not 0 <= color <= 9:
        raise ValueError(f"bad background color {color!r}")
    _current = color


def current() -> int | None:
    return _current


def of(grid: Grid) -> int:
    """Background for ``grid``: the task context if set and common, else r02."""
    if _current is not None:
        cells = sum(len(row) for row in grid)
        if sum(row.count(_current) for row in grid) >= MIN_SHARE * cells:
            return _current
    return g.background(grid)


@contextmanager
def task_context(color: int | None) -> Iterator[None]:
    """Temporarily set the task background, restoring the previous value."""
    previous = _current
    set_task_background(color)
    try:
        yield
    finally:
        set_task_background(previous)
