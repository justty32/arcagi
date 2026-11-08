"""S1 extension primitives: rays, connecting lines, compression, crop by color, periods.

Every function mirrors ``native/src/prims_ext.cpp`` exactly (checked by
``tests/dsl/ext/test_parity.py``). Background is ``background.of(grid)``, the
same task-level context the object primitives use.
"""

from collections.abc import Sequence

from arcagi.dsl import background
from arcagi.dsl import grid as g
from arcagi.dsl.primitives import Params
from arcagi.tasks import Grid

RAY_DIRS: dict[str, tuple[tuple[int, int], ...]] = {
    "u": ((-1, 0),),
    "d": ((1, 0),),
    "l": ((0, -1),),
    "r": ((0, 1),),
    "h": ((0, -1), (0, 1)),
    "v": ((-1, 0), (1, 0)),
    "hv": ((-1, 0), (1, 0), (0, -1), (0, 1)),
    "ul": ((-1, -1),),
    "ur": ((-1, 1),),
    "dl": ((1, -1),),
    "dr": ((1, 1),),
    "x": ((-1, -1), (-1, 1), (1, -1), (1, 1)),
    "all": ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)),
}
CONNECT_AXES: dict[str, tuple[tuple[int, int], ...]] = {
    "h": ((0, 1),),
    "v": ((1, 0),),
    "hv": ((0, 1), (1, 0)),
    "vh": ((1, 0), (0, 1)),
    "d": ((1, 1), (1, -1)),
    "all": ((0, 1), (1, 0), (1, 1), (1, -1)),
}
COMPRESS_MODES = ("dup", "dup_rows", "dup_cols", "bg", "bg_rows", "bg_cols")
CROP_MODES = ("bbox", "inner", "only")
PERIOD_MODES = ("fill", "extend")


def _freeze(rows: list[list[int]]) -> Grid:
    return tuple(tuple(row) for row in rows)


def ray(grid: Grid, dirs: str, mode: str, color: int) -> Grid:
    """Shoot rays of each source color until the border.

    Sources are non-background cells (only ``color`` unless it is -1), in raster
    order; a source shoots along a direction only when its next cell is
    background, and a diagonal one also needs both orthogonal neighbours toward
    it to be background or off-grid. Rays paint background cells of the input
    (later rays overwrite earlier ones); ``pass`` crosses other cells, ``stop``
    ends at the first one.
    """
    if dirs not in RAY_DIRS or mode not in ("pass", "stop"):
        raise ValueError(f"bad ray {dirs!r} {mode!r}")
    bg = background.of(grid)
    h, w = g.shape(grid)
    out = [list(row) for row in grid]

    def open_(y: int, x: int) -> bool:
        return not (0 <= y < h and 0 <= x < w) or grid[y][x] == bg

    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c == bg or (color >= 0 and c != color):
                continue
            for dy, dx in RAY_DIRS[dirs]:
                ny, nx = y + dy, x + dx
                if not (0 <= ny < h and 0 <= nx < w) or grid[ny][nx] != bg:
                    continue
                if dy and dx and not (open_(y + dy, x) and open_(y, x + dx)):
                    continue
                while 0 <= ny < h and 0 <= nx < w:
                    if grid[ny][nx] != bg:
                        if mode == "stop":
                            break
                    else:
                        out[ny][nx] = c
                    ny, nx = ny + dy, nx + dx
    return _freeze(out)


def _line_starts(h: int, w: int, dy: int, dx: int) -> list[tuple[int, int]]:
    if dy == 0:
        return [(y, 0) for y in range(h)]
    if dx == 0:
        return [(0, x) for x in range(w)]
    if dx == 1:
        return [(0, x) for x in range(w - 1, -1, -1)] + [(y, 0) for y in range(1, h)]
    return [(0, x) for x in range(w)] + [(y, w - 1) for y in range(1, h)]


def connect(grid: Grid, axes: str) -> Grid:
    """Fill the background run between consecutive same-colored cells on each line.

    Lines are scanned per axis in the listed order (``hv``: rows then columns, so
    columns win at crossings). Only input cells decide the pairs.
    """
    if axes not in CONNECT_AXES:
        raise ValueError(f"bad connect axes {axes!r}")
    bg = background.of(grid)
    h, w = g.shape(grid)
    out = [list(row) for row in grid]
    for dy, dx in CONNECT_AXES[axes]:
        for sy, sx in _line_starts(h, w, dy, dx):
            last = None
            y, x = sy, sx
            while 0 <= y < h and 0 <= x < w:
                c = grid[y][x]
                if c != bg:
                    if last is not None and grid[last[0]][last[1]] == c:
                        py, px = last[0] + dy, last[1] + dx
                        while (py, px) != (y, x):
                            out[py][px] = c
                            py, px = py + dy, px + dx
                    last = (y, x)
                y, x = y + dy, x + dx
    return _freeze(out)


def _compress_rows(grid: Grid, dup: bool, bg: int) -> Grid:
    rows = [
        row
        for y, row in enumerate(grid)
        if not all(
            c == ((grid[y - 1][x] if y else -1) if dup else bg)
            for x, c in enumerate(row)
        )
    ]
    if not rows:
        raise ValueError("compress removed everything")
    return tuple(rows)


def compress(grid: Grid, mode: str) -> Grid:
    """Drop rows/columns equal to the previous one (``dup*``) or all bg (``bg*``)."""
    if mode not in COMPRESS_MODES:
        raise ValueError(f"bad compress mode {mode!r}")
    dup = mode.startswith("dup")
    axes = mode[3:] if dup else mode[2:]
    bg = background.of(grid)
    out = grid
    if axes != "_cols":
        out = _compress_rows(out, dup, bg)
    if axes != "_rows":
        out = g.transpose(_compress_rows(g.transpose(out), dup, bg))
    return out


def crop_color(grid: Grid, color: int, mode: str) -> Grid:
    """Crop to the bbox of ``color``: whole (``bbox``), inside its frame (``inner``),
    or with every other color turned to background (``only``)."""
    if mode not in CROP_MODES:
        raise ValueError(f"bad crop mode {mode!r}")
    cells = [
        (y, x) for y, row in enumerate(grid) for x, c in enumerate(row) if c == color
    ]
    if not cells:
        raise ValueError("color absent")
    top, left = min(y for y, _ in cells), min(x for _, x in cells)
    bottom, right = max(y for y, _ in cells), max(x for _, x in cells)
    if mode == "inner":
        if bottom - top < 2 or right - left < 2:
            raise ValueError("frame too small")
        return tuple(row[left + 1 : right] for row in grid[top + 1 : bottom])
    out = tuple(row[left : right + 1] for row in grid[top : bottom + 1])
    if mode == "only":
        bg = background.of(grid)
        out = tuple(tuple(c if c == color else bg for c in row) for row in out)
    return out


def _lattices(h: int, w: int) -> list[tuple[int, int, int]]:
    """(kind, p, q): rect (p, q), anti (x+y)%p, main (x-y)%p; by classes, kind, p, q."""
    out = [
        (0, py, px)
        for py in range(1, h + 1)
        for px in range(1, w + 1)
        if py < h or px < w
    ]
    out += [(kind, p, 0) for kind in (1, 2) for p in range(2, h + w - 1)]

    def classes(lat: tuple[int, int, int]) -> int:
        return lat[1] if lat[0] else lat[1] * lat[2]

    return sorted(out, key=lambda lat: (classes(lat), lat))


def _class_of(lat: tuple[int, int, int], y: int, x: int) -> tuple[int, int]:
    kind, p, q = lat
    if kind == 0:
        return y % p, x % q
    return ((y + x) % p if kind == 1 else (y - x) % p), 0


def period(grid: Grid, mode: str, color: int) -> Grid:
    """Periodic repair (``fill``: cells of ``color`` are unknown) or continuation.

    ``fill`` takes the first lattice consistent with the known cells that gives
    every unknown cell a value. ``extend`` takes the bbox of non-``color`` cells,
    finds its smallest rect period (area, then py, px) and tiles it everywhere.
    """
    h, w = g.shape(grid)
    if mode == "fill":
        if not any(c == color for row in grid for c in row):
            raise ValueError("nothing to fill")
        for lat in _lattices(h, w):
            values: dict[tuple[int, int], int] = {}
            ok = True
            for y in range(h):
                for x in range(w):
                    c = grid[y][x]
                    if c == color:
                        continue
                    key = _class_of(lat, y, x)
                    if values.setdefault(key, c) != c:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            try:
                return tuple(
                    tuple(
                        values[_class_of(lat, y, x)] if c == color else c
                        for x, c in enumerate(row)
                    )
                    for y, row in enumerate(grid)
                )
            except KeyError:
                continue
        raise ValueError("no period")
    if mode != "extend":
        raise ValueError(f"bad period mode {mode!r}")
    cells = [
        (y, x) for y, row in enumerate(grid) for x, c in enumerate(row) if c != color
    ]
    if not cells:
        raise ValueError("empty")
    top, left = min(y for y, _ in cells), min(x for _, x in cells)
    bh = max(y for y, _ in cells) - top + 1
    bw = max(x for _, x in cells) - left + 1
    if bh == h and bw == w:
        raise ValueError("nothing outside")
    for py, px in sorted(
        ((py, px) for py in range(1, bh + 1) for px in range(1, bw + 1)),
        key=lambda p: (p[0] * p[1], p),
    ):
        if all(
            grid[top + y][left + x] == grid[top + y % py][left + x % px]
            for y in range(bh)
            for x in range(bw)
        ):
            return tuple(
                tuple(
                    grid[top + (y - top) % py][left + (x - left) % px] for x in range(w)
                )
                for y in range(h)
            )
    raise ValueError("no period")  # unreachable: (bh, bw) always fits


def _colors(grids: Sequence[Grid]) -> list[int]:
    return sorted({c for grid in grids for row in grid for c in row})


def _same_shapes(states: Sequence[Grid], targets: Sequence[Grid]) -> bool:
    return all(g.shape(s) == g.shape(t) for s, t in zip(states, targets, strict=True))


def _shrinks(states: Sequence[Grid], targets: Sequence[Grid]) -> bool:
    pairs = [(g.shape(s), g.shape(t)) for s, t in zip(states, targets, strict=True)]
    if any(th > sh or tw > sw for (sh, sw), (th, tw) in pairs):
        return False
    return any(th < sh or tw < sw for (sh, sw), (th, tw) in pairs)


def _common_colors(states: Sequence[Grid]) -> list[int]:
    return [c for c in range(11) if all(any(c in row for row in s) for s in states)]


def _count(grid: Grid, color: int) -> int:
    return sum(row.count(color) for row in grid)


def ray_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not _same_shapes(states, targets):
        return []
    sources, any_gain = [], False
    for c in _colors(states):
        deltas = [
            _count(t, c) - _count(s, c) for s, t in zip(states, targets, strict=True)
        ]
        gain = any(d > 0 for d in deltas)
        if gain and all(d >= 0 for d in deltas):
            sources.append(c)
        any_gain = any_gain or gain
    if not any_gain:
        return []
    if len(sources) != 1:
        sources.insert(0, -1)
    return [
        (dirs, mode, c)
        for c in sources
        for dirs in sorted(RAY_DIRS)
        for mode in ("pass", "stop")
    ]


def connect_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    return [(a,) for a in CONNECT_AXES] if _same_shapes(states, targets) else []


def compress_candidates(
    states: Sequence[Grid], targets: Sequence[Grid]
) -> list[Params]:
    return [(m,) for m in COMPRESS_MODES] if _shrinks(states, targets) else []


def crop_color_candidates(
    states: Sequence[Grid], targets: Sequence[Grid]
) -> list[Params]:
    if not _shrinks(states, targets):
        return []
    return [(c, m) for c in _common_colors(states) for m in CROP_MODES]


def period_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    if not _same_shapes(states, targets):
        return []
    return [(m, c) for c in _common_colors(states) for m in PERIOD_MODES]


VRULE_NEIGHBORS: dict[str, tuple[tuple[int, int], ...]] = {
    "n4": ((-1, 0), (1, 0), (0, -1), (0, 1)),
    "n8": ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)),
}
type VTable = list[list[int]]


def _vkey(
    grid: Grid, y: int, x: int, steps, bg: int
) -> tuple[tuple[int, ...], list[int]]:
    """Abstract key: off-grid -1, bg 0, other colors 1.. by first appearance."""
    h, w = g.shape(grid)
    variables: list[int] = []
    key = []
    for dy, dx in ((0, 0), *steps):
        ny, nx = y + dy, x + dx
        if not (0 <= ny < h and 0 <= nx < w):
            key.append(-1)
            continue
        c = grid[ny][nx]
        if c == bg:
            key.append(0)
            continue
        if c not in variables:
            variables.append(c)
        key.append(variables.index(c) + 1)
    return tuple(key), variables


def _vencode(dst: int, bg: int, variables: list[int]) -> int:
    if dst == bg:
        return 0
    return variables.index(dst) + 1 if dst in variables else 10 + dst


def _vdecode(token: int, bg: int, variables: list[int]) -> int:
    if token == 0:
        return bg
    if token >= 10:
        return token - 10
    if not 0 < token <= len(variables):
        raise ValueError("unbound color variable")
    return variables[token - 1]


def vrule(grid: Grid, features: str, table: VTable) -> Grid:
    """Color-variable local rule: ``local_rule`` over abstracted keys.

    Output tokens: 0 = background, 1..9 = the color bound to that variable,
    10 + c = literal color c. Unknown keys keep the cell (MARK cells must match).
    """
    if features not in VRULE_NEIGHBORS:
        raise ValueError(f"bad features {features!r}")
    lookup = {tuple(row[:-1]): row[-1] for row in table}
    steps = VRULE_NEIGHBORS[features]
    bg = background.of(grid)
    out = []
    for y, row in enumerate(grid):
        new = []
        for x, c in enumerate(row):
            key, variables = _vkey(grid, y, x, steps, bg)
            if key in lookup:
                new.append(_vdecode(lookup[key], bg, variables))
            elif c > 9:
                raise KeyError("unresolved marker")
            else:
                new.append(c)
        out.append(tuple(new))
    return tuple(out)


def fit_vrule(
    states: Sequence[Grid],
    targets: Sequence[Grid],
    tests: Sequence[Grid],
    features: str,
) -> VTable | None:
    """Fit ``vrule``: consistent over train, some key changes, every test key known."""
    steps = VRULE_NEIGHBORS[features]
    lookup: dict[tuple[int, ...], int] = {}
    for state, target in zip(states, targets, strict=True):
        if g.shape(state) != g.shape(target):
            return None
        bg = background.of(state)
        for y, row in enumerate(target):
            for x, dst in enumerate(row):
                key, variables = _vkey(state, y, x, steps, bg)
                if lookup.setdefault(key, _vencode(dst, bg, variables)) != _vencode(
                    dst, bg, variables
                ):
                    return None
    table = sorted([*key, v] for key, v in lookup.items() if key[0] != v)
    if not table:
        return None
    for test in tests:
        bg = background.of(test)
        h, w = g.shape(test)
        if any(
            _vkey(test, y, x, steps, bg)[0] not in lookup
            for y in range(h)
            for x in range(w)
        ):
            return None
    return table


def vrule_candidates(states: Sequence[Grid], targets: Sequence[Grid]) -> list[Params]:
    for features in VRULE_NEIGHBORS:
        table = fit_vrule(states, targets, (), features)
        if table is not None:
            return [(features, table)]
    return []
