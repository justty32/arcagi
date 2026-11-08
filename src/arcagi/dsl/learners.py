"""Terminal learners: fit a lookup table from (intermediate, target) train pairs.

A learner returns ``None`` on any conflict, or when a test grid needs a key never
seen in training, so a fitted table is always a deterministic, checkable rule.
Fitted steps are JSON-friendly so they serialize into programs and traces.
"""

from collections import Counter
from collections.abc import Sequence

from arcagi.tasks import Grid

from . import grid as g

type Table = list[list[int]]
OUTSIDE = -1
MIN_SUPPORT = 1


def apply_colormap(grid: Grid, table: Table) -> Grid:
    return g.recolor(grid, {src: dst for src, dst in table})


def fit_colormap(
    states: Sequence[Grid], targets: Sequence[Grid], tests: Sequence[Grid]
) -> Table | None:
    """One-to-one cell color table; unseen test colors 0-9 stay unchanged."""
    mapping: dict[int, int] = {}
    for state, target in zip(states, targets, strict=True):
        if g.shape(state) != g.shape(target):
            return None
        for row_s, row_t in zip(state, target, strict=True):
            for src, dst in zip(row_s, row_t, strict=True):
                if mapping.setdefault(src, dst) != dst:
                    return None
    for test in tests:
        for row in test:
            for value in row:
                if value not in mapping and value > 9:
                    return None
    if all(src == dst for src, dst in mapping.items()):
        return None
    return sorted([src, dst] for src, dst in mapping.items() if src != dst)


_NEIGHBORS = {
    "n4": ((-1, 0), (1, 0), (0, -1), (0, 1)),
    "n8": ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)),
}


def _key(grid: Grid, r: int, c: int, steps) -> tuple[int, ...]:
    height, width = g.shape(grid)
    key = [grid[r][c]]
    for dy, dx in steps:
        y, x = r + dy, c + dx
        key.append(grid[y][x] if 0 <= y < height and 0 <= x < width else OUTSIDE)
    return tuple(key)


def apply_local_rule(grid: Grid, features: str, table: Table) -> Grid:
    lookup = {tuple(row[:-1]): row[-1] for row in table}
    steps = _NEIGHBORS[features]
    height, width = g.shape(grid)
    out = []
    for r in range(height):
        row = []
        for c in range(width):
            key = _key(grid, r, c, steps)
            row.append(lookup.get(key, key[0]) if key[0] <= 9 else lookup[key])
        out.append(tuple(row))
    return tuple(out)


def fit_local_rule(
    states: Sequence[Grid],
    targets: Sequence[Grid],
    tests: Sequence[Grid],
    features: str,
) -> Table | None:
    """Cell color = f(center + neighborhood); every test key must be known."""
    steps = _NEIGHBORS[features]
    lookup: dict[tuple[int, ...], int] = {}
    support: Counter[tuple[int, ...]] = Counter()
    for state, target in zip(states, targets, strict=True):
        if g.shape(state) != g.shape(target):
            return None
        for r, row in enumerate(target):
            for c, dst in enumerate(row):
                key = _key(state, r, c, steps)
                support[key] += 1
                if lookup.setdefault(key, dst) != dst:
                    return None
    changing = {key for key, dst in lookup.items() if key[0] != dst}
    # A changing key seen only once is memorized, not learned: refuse the rule.
    if not changing or any(support[key] < MIN_SUPPORT for key in changing):
        return None
    for test in tests:
        height, width = g.shape(test)
        for r in range(height):
            for c in range(width):
                if _key(test, r, c, steps) not in lookup:
                    return None
    return sorted([*key, dst] for key, dst in lookup.items() if key[0] != dst)
