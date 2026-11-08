"""Object-view selectors and properties: values computed relative to one object.

An object-scope extraction body is ``{"scope": "object", "sel": [op, conn],
"prop": name}``. ``op`` picks objects (extracted under ``conn``) relative to the
anchor object ``this``: ``this`` (objects covering the anchor's cells),
``nearest`` / ``nearest_same_color`` / ``nearest_other_color`` (the unique
closest other object, by bounding-box gap), ``nearest_aligned`` (the unique
closest other object sharing rows or columns with the anchor; ``_same_color``
/ ``_other_color`` suffixes filter it further), ``touching`` (other objects
8-adjacent to the anchor), ``largest`` (the grid's unique largest object) and
``same_shape_other_color`` (other-colored objects with the anchor's normalized
mask: an in-grid legend; ``color`` then needs them to agree).

Properties: ``color`` (shared color), ``size`` / ``size_rank`` (unique among the
selection), ``dir_to`` / ``dist_to`` (direction and background gap from the
anchor to the single selected object; they must share rows or columns),
``dir8_to`` (like ``dir_to`` but a diagonal such as ``down_right`` when the two
boxes share neither rows nor columns) and ``wall_dir`` (direction of the
anchor's nearest border, ``this`` only).
Ambiguity raises ValueError.
"""

from collections.abc import Mapping, Sequence

from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import CONNS, Obj, extract
from arcagi.tasks import Grid

OSELS = (
    "this",
    "nearest",
    "nearest_same_color",
    "nearest_other_color",
    "nearest_aligned",
    "nearest_aligned_same_color",
    "nearest_aligned_other_color",
    "touching",
    "largest",
    "same_shape_other_color",
)
OPROPS = ("color", "dir_to", "dir8_to", "dist_to", "size", "size_rank", "wall_dir")
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
DIAGONALS = {"up_left": (-1, -1), "up_right": (-1, 1)}
DIAGONALS.update(down_left=(1, -1), down_right=(1, 1))
DIRS8 = DIRS | DIAGONALS


def validate(body: object) -> bool:
    if not isinstance(body, Mapping) or body.get("scope") != "object":
        return False
    sel, prop = body.get("sel"), body.get("prop")
    if not isinstance(sel, list) or len(sel) != 2 or prop not in OPROPS:
        return False
    if sel[0] not in OSELS or sel[1] not in CONNS:
        return False
    if prop in ("dir_to", "dir8_to", "dist_to") and sel[0] == "this":
        return False
    return prop != "wall_dir" or sel[0] == "this"


def make(op: str, conn: str, prop: str) -> dict:
    return {"scope": "object", "sel": [op, conn], "prop": prop}


def _box(cells: Sequence[tuple[int, int]]) -> tuple[int, int, int, int]:
    """Inclusive ``(top, left, bottom, right)``."""
    top, left, h, w = g.cells_bbox(list(cells))
    return top, left, top + h - 1, left + w - 1


def gap(a: Sequence[tuple[int, int]], b: Sequence[tuple[int, int]]) -> int:
    """Chebyshev gap between bounding boxes (0 when they touch or overlap)."""
    at, al, ab, ar = _box(a)
    bt, bl, bb, br = _box(b)
    dy = max(bt - ab, at - bb, 0)
    dx = max(bl - ar, al - br, 0)
    return max(dy, dx)


def _single(objs: Sequence[Obj], what: str) -> list[Obj]:
    if len(objs) != 1:
        raise ValueError(f"no single {what} object")
    return list(objs)


def select(grid: Grid, sel: Sequence[object], anchor: Obj) -> list[Obj]:
    op, conn = sel
    if op not in OSELS or conn not in CONNS:
        raise ValueError(f"bad object selector {sel!r}")
    objs = extract(grid, conn)  # type: ignore[arg-type]
    own = set(anchor.cells)
    if op == "this":
        return _single([o for o in objs if own & set(o.cells)], op)
    if op == "largest":
        best = max(o.props["size"] for o in objs)  # type: ignore[type-var]
        return _single([o for o in objs if o.props["size"] == best], op)
    others = [o for o in objs if not own & set(o.cells)]
    color = anchor.props["color"]
    if op.endswith("_same_color"):
        others = [o for o in others if o.props["color"] == color]
    elif op.endswith("_other_color"):
        others = [o for o in others if o.props["color"] != color]
    if op == "same_shape_other_color":  # in-grid legend / template objects
        found = [o for o in others if o.props["shape"] == anchor.props["shape"]]
        if not found:
            raise ValueError("no same-shape object")
        return found
    if op == "touching":
        ring = {(y + a, x + b) for y, x in own for a in (-1, 0, 1) for b in (-1, 0, 1)}
        found = [o for o in others if ring & set(o.cells)]
        if not found:
            raise ValueError("nothing touching")
        return found
    if op.startswith("nearest_aligned"):
        others = [o for o in others if _aligned(anchor.cells, o.cells)]
    if not others:
        raise ValueError("no other object")
    dists = [gap(anchor.cells, o.cells) for o in others]
    best = min(dists)
    return _single([o for o, d in zip(others, dists, strict=True) if d == best], op)


def _aligned(a, b) -> bool:
    try:
        direction(a, b)
    except ValueError:
        return False
    return True


def direction(a: Sequence[tuple[int, int]], b: Sequence[tuple[int, int]]):
    """``(dir, gap)`` from cells ``a`` to cells ``b`` sharing rows or columns."""
    at, al, ab, ar = _box(a)
    bt, bl, bb, br = _box(b)
    cols = al <= br and bl <= ar
    rows = at <= bb and bt <= ab
    if cols and not rows:
        return ("down", bt - ab - 1) if bt > ab else ("up", at - bb - 1)
    if rows and not cols:
        return ("right", bl - ar - 1) if bl > ar else ("left", al - br - 1)
    raise ValueError("objects are not aligned")


def direction8(a: Sequence[tuple[int, int]], b: Sequence[tuple[int, int]]) -> str:
    """``direction`` name, or the diagonal from ``a`` to a box-disjoint ``b``."""
    try:
        return direction(a, b)[0]
    except ValueError:
        pass
    at, al, ab, ar = _box(a)
    bt, bl, bb, br = _box(b)
    vert = "down" if bt > ab else "up" if bb < at else None
    horiz = "right" if bl > ar else "left" if br < al else None
    if vert is None or horiz is None:
        raise ValueError("objects overlap")
    return f"{vert}_{horiz}"


def prop(grid: Grid, name: str, objs: Sequence[Obj], anchor: Obj) -> object:
    if name == "color":
        colors = {o.props["color"] for o in objs}
        if len(colors) != 1:
            raise ValueError("selected objects differ in color")
        return colors.pop()
    if name in ("size", "size_rank"):
        values = {o.props[name] for o in objs}
        if len(values) != 1:
            raise ValueError(f"selected objects differ in {name}")
        return values.pop()
    if name in ("dir_to", "dist_to"):
        (target,) = _single(objs, name)
        d, k = direction(anchor.cells, target.cells)
        return d if name == "dir_to" else k
    if name == "dir8_to":
        (target,) = _single(objs, name)
        return direction8(anchor.cells, target.cells)
    if name == "wall_dir":
        height, width = g.shape(grid)
        top, left, bottom, right = _box(anchor.cells)
        gaps = {"up": top, "down": height - 1 - bottom}
        gaps.update(left=left, right=width - 1 - right)
        best = min(gaps.values())
        near = [d for d, v in gaps.items() if v == best]
        if len(near) != 1:
            raise ValueError("no single nearest wall")
        return near[0]
    raise ValueError(f"unknown object property {name!r}")


def run(body: Mapping, grid: Grid, anchor: Obj) -> object:
    if not validate(body):
        raise ValueError(f"bad object extraction {body!r}")
    return prop(grid, body["prop"], select(grid, body["sel"], anchor), anchor)


def bodies(props: Sequence[str], conns: Sequence[str] = CONNS) -> list[dict]:
    """Every valid object-scope body with ``prop`` in ``props`` (canonical order)."""
    out = [make(op, c, p) for c in conns for op in OSELS for p in props]
    return [b for b in out if validate(b)]


def length(body: Mapping) -> int:
    return 3 if body["sel"][0] in ("this", "largest") else 4
