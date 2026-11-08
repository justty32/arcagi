"""Extraction expressions: grid -> JSON value (a selector plus a property).

An extraction body is the S-expression ``[prop, [sel, conn, *args]]``; its block
form is ``{"kind": "extract", "in": "grid", "out": "json", "body": body}``.

Selectors (objects from ``objects_props.extract`` under ``conn``):
``largest`` / ``smallest`` (the unique max / min size object), ``unique_color``
/ ``unique_shape`` (the only object whose color / shape occurs once), ``all``,
``color c`` (objects of color ``c``) and ``pred p`` (``p`` a predicate block name
or an inline predicate AST, see ``arcagi.dsl.predicates``).

Properties of the selected objects: ``bbox`` ``[top, left, h, w]`` (union),
``color`` (the shared color), ``size`` (cells), ``count`` (objects), ``cells``
(``[[y, x], ...]``), ``subgrid`` (grid cropped to the bbox) and ``object`` (the
crop with unselected cells set to the background). Ambiguity raises ValueError.

CLI: ``python -m arcagi.dsl.extract RULE.json`` reads a grid (or ``{"grid":..}``)
on stdin and prints the JSON value.
"""

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from arcagi.tasks import Grid

from . import grid as g
from .objects_props import CONNS, Obj, extract, pred_mask

type Body = list[object]

SINGLE = ("largest", "smallest", "unique_color", "unique_shape")
SELECTORS = (*SINGLE, "all", "color", "pred")
PROPS = ("bbox", "color", "size", "count", "cells", "subgrid", "object")
GRID_PROPS = ("subgrid", "object")
LIVE: dict[str, Body] = {}


def _only(objs: Sequence[Obj], what: str) -> list[Obj]:
    if len(objs) != 1:
        raise ValueError(f"no single {what} object")
    return list(objs)


def select(grid: Grid, sel: Sequence[object]) -> list[Obj]:
    """Objects picked by selector ``sel`` (``[op, conn, *args]``)."""
    op, conn, *args = sel
    if op not in SELECTORS or conn not in CONNS:
        raise ValueError(f"bad selector {sel!r}")
    objs = extract(grid, conn)  # type: ignore[arg-type]
    if not objs:
        raise ValueError("no objects")
    if op in ("largest", "smallest"):
        best = (max if op == "largest" else min)(o.props["size"] for o in objs)  # type: ignore[type-var]
        return _only([o for o in objs if o.props["size"] == best], op)
    if op == "unique_color":
        return _only([o for o in objs if o.props["color_count"] == 1], op)
    if op == "unique_shape":
        return _only([o for o in objs if o.props["shape_count"] == 1], op)
    if op == "all":
        return list(objs)
    if op == "color":
        return [o for o in objs if o.props["color"] == args[0]]
    name = args[0] if isinstance(args[0], str) else None
    mask = pred_mask(grid, conn, name, args[0])  # type: ignore[arg-type]
    return [o for o, keep in zip(objs, mask, strict=True) if keep]


def _cells(objs: Sequence[Obj]) -> list[tuple[int, int]]:
    return sorted({c for o in objs for c in o.cells})


def prop(grid: Grid, name: str, objs: Sequence[Obj]) -> object:
    """Property ``name`` of the selected objects as a JSON-ready value."""
    if name == "count":
        return len(objs)
    if not objs:
        raise ValueError("nothing selected")
    cells = _cells(objs)
    if name == "size":
        return len(cells)
    if name == "cells":
        return [list(c) for c in cells]
    if name == "color":
        colors = {o.props["color"] for o in objs}
        if len(colors) != 1:
            raise ValueError("selected objects differ in color")
        return next(iter(colors))
    top, left, h, w = g.cells_bbox(cells)
    if name == "bbox":
        return [top, left, h, w]
    crop = g.crop(grid, top, left, h, w)
    if name == "subgrid":
        return [list(row) for row in crop]
    if name == "object":
        bg, own = g.background(grid), set(cells)
        return [
            [v if (top + y, left + x) in own else bg for x, v in enumerate(row)]
            for y, row in enumerate(crop)
        ]
    raise ValueError(f"unknown property {name!r}")


def unwrap(body: object) -> Body:
    """The body of a block dict or a body itself; resolves block names."""
    if isinstance(body, str):
        return resolve(body)
    if isinstance(body, Mapping):
        body = body.get("body")
    if not validate(body):
        raise ValueError(f"bad extract body {body!r}")
    return body  # type: ignore[return-value]


def run(body: object, grid: Grid) -> object:
    """Value of extraction ``body`` (body, block dict or block name) on ``grid``."""
    name, sel = unwrap(body)
    grid = tuple(tuple(row) for row in grid)
    return prop(grid, name, select(grid, sel))  # type: ignore[arg-type]


def as_grid(value: object) -> Grid:
    if not isinstance(value, list) or not value:
        raise ValueError("extracted value is not a grid")
    return tuple(tuple(row) for row in value)


def validate(body: object) -> bool:
    if not isinstance(body, list) or len(body) != 2 or body[0] not in PROPS:
        return False
    sel = body[1]
    if not isinstance(sel, list) or len(sel) < 2 or sel[0] not in SELECTORS:
        return False
    if sel[1] not in CONNS:
        return False
    if sel[0] in ("color", "pred"):
        return len(sel) == 3
    return len(sel) == 2


def length(body: Sequence[object]) -> int:
    """Description length: selector op + args + property (pred names count 2)."""
    sel = body[1]
    extra = len(sel) - 2  # type: ignore[arg-type]
    if sel[0] == "pred":  # type: ignore[index]
        extra += 1 if isinstance(sel[2], str) else len(json.dumps(sel[2])) // 10  # type: ignore[index]
    return 2 + extra


def read_rule(folder: Path) -> Body | None:
    try:
        rule = json.loads((folder / "_rule.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    body = rule.get("body") if isinstance(rule, dict) else None
    return body if validate(body) else None


def install(rules: Mapping[str, object]) -> None:
    """Live extract blocks: name -> ``_rule.json`` dict (or bare body)."""
    LIVE.clear()
    for name, rule in rules.items():
        body = rule.get("body") if isinstance(rule, Mapping) else rule
        if validate(body):
            LIVE[name] = body  # type: ignore[assignment]


def resolve(name: str) -> Body:
    if name in LIVE:
        return LIVE[name]
    from arcagi.blocks import default_blocks_root

    body = read_rule(default_blocks_root() / name)
    if body is None:
        raise ValueError(f"unknown extract block {name!r}")
    return body


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(
            "usage: python -m arcagi.dsl.extract RULE.json < grid.json", file=sys.stderr
        )
        return 2
    try:
        body = read_rule(Path(argv[0]).parent)
        if body is None:
            raise ValueError(f"bad rule file {argv[0]}")
        data = json.loads(sys.stdin.read())
        grid = data["grid"] if isinstance(data, dict) else data
        print(json.dumps(run(body, grid)))
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        print(f"arcagi.dsl.extract: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
