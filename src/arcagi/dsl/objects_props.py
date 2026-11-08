"""Object extraction, per-object attributes and single-attribute selectors.

Objects come from ``grid.objects`` under four connectivity modes; the background
is the grid's most frequent color. Every attribute value is an int or a str so
selectors ``(conn, attr, value)`` stay JSON-serializable program parameters.
``attr == "pred"`` makes ``value`` a predicate (a live block name or an inline
AST, see ``arcagi.dsl.predicates``); ``(attr, value)`` is its ``eq`` special case.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from arcagi.tasks import Grid

from . import grid as g
from . import predicates as pr

type Cell = tuple[int, int]
CONNS = ("4same", "8same", "4multi", "8multi")
# Attribute order doubles as the simplicity order when several selectors fit.
ATTRS = (
    "color",
    "shape_count",
    "color_count",
    "is_largest",
    "is_smallest",
    "size_rank",
    "size",
    "touches_border",
    "has_hole",
    "h",
    "w",
    "shape",
)
MAX_SELECTORS = 2
MAX_PRED_SELECTORS = 2


@dataclass(frozen=True)
class Obj:
    cells: tuple[Cell, ...]
    colors: tuple[int, ...]
    props: dict[str, int | str]


def _shape_id(cells: Sequence[Cell]) -> str:
    top, left, height, width = g.cells_bbox(list(cells))
    filled = {(y - top, x - left) for y, x in cells}
    bits = "".join(
        "1" if (y, x) in filled else "0" for y in range(height) for x in range(width)
    )
    return f"{height}x{width}:{bits}"


def hole_cells(grid: Grid, cells: Sequence[Cell]) -> list[Cell]:
    """Non-object cells inside the bbox that a 4-flood from outside cannot reach."""
    top, left, height, width = g.cells_bbox(list(cells))
    own = set(cells)
    h2, w2 = height + 2, width + 2
    seen = [[False] * w2 for _ in range(h2)]
    stack = [(0, 0)]
    seen[0][0] = True
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h2 and 0 <= nx < w2 and not seen[ny][nx]:
                if (ny - 1 + top, nx - 1 + left) not in own:
                    seen[ny][nx] = True
                    stack.append((ny, nx))
    return [
        (y - 1 + top, x - 1 + left)
        for y in range(1, h2 - 1)
        for x in range(1, w2 - 1)
        if not seen[y][x] and (y - 1 + top, x - 1 + left) not in own
    ]


@lru_cache(maxsize=8192)
def extract(grid: Grid, conn: str) -> tuple[Obj, ...]:
    """Objects of ``grid`` under ``conn`` with all attributes filled in."""
    bg = g.background(grid)
    raw = g.objects(grid, bg, diagonal=conn[0] == "8", by_color=conn.endswith("same"))
    if not raw:
        return ()
    height, width = g.shape(grid)
    sizes = [len(cells) for cells in raw]
    distinct = sorted(set(sizes), reverse=True)
    shapes = [_shape_id(cells) for cells in raw]
    colors = [
        Counter(grid[y][x] for y, x in cells).most_common(1)[0][0] for cells in raw
    ]
    shape_counts, color_counts = Counter(shapes), Counter(colors)
    out = []
    for i, cells in enumerate(raw):
        cells = sorted(cells)
        _, _, h, w = g.cells_bbox(cells)
        border = any(y in (0, height - 1) or x in (0, width - 1) for y, x in cells)
        props: dict[str, int | str] = {
            "color": colors[i],
            "is_largest": int(sizes[i] == max(sizes)),
            "is_smallest": int(sizes[i] == min(sizes)),
            "size_rank": distinct.index(sizes[i]) + 1,
            "size": sizes[i],
            "touches_border": int(border),
            "has_hole": int(bool(hole_cells(grid, cells))),
            "color_count": color_counts[colors[i]],
            "shape_count": shape_counts[shapes[i]],
            "h": h,
            "w": w,
            "shape": shapes[i],
        }
        out.append(Obj(tuple(cells), tuple(grid[y][x] for y, x in cells), props))
    return tuple(out)


def selected(grid: Grid, conn: str, attr: str, value: object) -> list[Obj]:
    if conn not in CONNS or (attr not in ATTRS and attr not in ("all", "pred")):
        raise ValueError(f"bad selector {conn}/{attr}")
    objs = extract(grid, conn)
    if attr == "all":
        return list(objs)
    if attr == "pred":
        mask = pred_mask(grid, conn, value if isinstance(value, str) else None, value)
        return [o for o, keep in zip(objs, mask, strict=True) if keep]
    return [o for o in objs if o.props[attr] == value]


@lru_cache(maxsize=32768)
def _named_mask(grid: Grid, conn: str, name: str) -> tuple[bool, ...]:
    return tuple(
        pr.evaluate_group(pr.resolve(name), [o.props for o in extract(grid, conn)])
    )


def pred_mask(
    grid: Grid, conn: str, name: str | None, body: object
) -> tuple[bool, ...]:
    """Per-object truth of a named (cached) or inline predicate."""
    if name is not None:
        return _named_mask(grid, conn, name)
    if not pr.validate(body):
        raise ValueError(f"bad predicate {body!r}")
    group = [o.props for o in extract(grid, conn)]
    return tuple(pr.evaluate_group(body, group))  # type: ignore[arg-type]


type Labeled = list[tuple[Obj, bool | None]]


def separate(examples: Sequence[Labeled]) -> list[tuple[str, int | str]]:
    """Single-attribute predicates that pick exactly the True-labeled objects.

    ``None`` labels are don't-care. Returns at most ``MAX_SELECTORS`` selectors in
    attribute order; ``("all", 1)`` when every labeled object is positive.
    """
    pos = [o for ex in examples for o, lab in ex if lab]
    neg = [o for ex in examples for o, lab in ex if lab is False]
    if not pos:
        return []
    if not neg:
        return [("all", 1)]
    found: list[tuple[str, int | str]] = []
    for attr in ATTRS:
        values = {o.props[attr] for o in pos}
        if len(values) != 1:
            continue
        value = next(iter(values))
        if all(o.props[attr] != value for o in neg):
            found.append((attr, value))
            if len(found) >= MAX_SELECTORS:
                break
    return found


def pred_selectors(
    grids: Sequence[Grid], conn: str, labels: Sequence[Sequence[bool | None]]
) -> list[str]:
    """Live predicate names consistent with per-object labels on every grid."""
    if not any(lab for labs in labels for lab in labs):
        return []
    found = []
    for name in pr.LIVE:
        ok = True
        for grid, labs in zip(grids, labels, strict=True):
            mask = _named_mask(grid, conn, name)
            if any(
                lab is not None and lab != m for lab, m in zip(labs, mask, strict=True)
            ):
                ok = False
                break
        if ok:
            found.append(name)
            if len(found) >= MAX_PRED_SELECTORS:
                break
    return found


def same_shapes(states: Sequence[Grid], targets: Sequence[Grid]) -> bool:
    return all(g.shape(s) == g.shape(t) for s, t in zip(states, targets, strict=True))


def changed(obj: Obj, target: Grid) -> bool:
    return any(
        target[y][x] != c for (y, x), c in zip(obj.cells, obj.colors, strict=True)
    )
