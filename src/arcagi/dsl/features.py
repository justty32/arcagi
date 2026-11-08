"""Integer features of one grid, shared by formula and extract blocks.

``compute(grid)`` returns a dict ``name -> int``: size (``h``, ``w``), color
statistics (``n_color`` = distinct non-background colors, ``n_fg``, ``n_bg``,
``cnt_0`` .. ``cnt_9``) and object statistics from ``objects_props.extract``
(``n_obj`` under 4-connected single-color objects, ``n_obj8`` under 8-connected
multi-color objects, ``n_shape`` distinct shapes, max/min object h, w, size; 0
when there is no object). The background is whatever ``extract`` uses
(``arcagi.dsl.background``).

Extract features: ``compute(grid, extracts)`` also evaluates extraction blocks
(``name -> body``, default the installed ``EXTRA``) and adds integer values as
``<name>`` (``size`` / ``count`` / ``color``) or ``<name>.top|left|h|w``
(``bbox``); a failed or non-integer extraction adds nothing.
"""

import json
from collections import Counter
from collections.abc import Mapping
from functools import lru_cache

from arcagi.tasks import Grid

from . import background as bgc
from . import grid as g
from .objects_props import extract

NAMES: tuple[str, ...] = (
    "h",
    "w",
    "n_color",
    "n_fg",
    "n_bg",
    "n_obj",
    "n_obj8",
    "n_shape",
    "max_obj_h",
    "max_obj_w",
    "min_obj_h",
    "min_obj_w",
    "max_obj_size",
    "min_obj_size",
    *(f"cnt_{c}" for c in range(10)),
)


@lru_cache(maxsize=16384)
def _compute(grid: Grid, _bg: int) -> tuple[int, ...]:
    height, width = g.shape(grid)
    counts: Counter[int] = g.color_counts(grid)
    objs = extract(grid, "4same")
    objs8 = extract(grid, "8multi")
    bg_cells = height * width - sum(len(o.cells) for o in objs)
    fg_colors = {c for o in objs for c in o.colors}
    hs = [int(o.props["h"]) for o in objs] or [0]
    ws = [int(o.props["w"]) for o in objs] or [0]
    sizes = [len(o.cells) for o in objs] or [0]
    values = (
        height,
        width,
        len(fg_colors),
        height * width - bg_cells,
        bg_cells,
        len(objs),
        len(objs8),
        len({o.props["shape"] for o in objs}),
        max(hs),
        max(ws),
        min(hs),
        min(ws),
        max(sizes),
        min(sizes),
        *(counts.get(c, 0) for c in range(10)),
    )
    return tuple(values)


EXTRA: dict[str, list] = {}  # extract block name -> body (install)
BBOX = ("top", "left", "h", "w")
NUMERIC_PROPS = ("size", "count", "bbox")  # quantities, not colors


def _values(name: str, value: object) -> dict[str, int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return {name: value}
    if isinstance(value, list) and len(value) == 4:
        if all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            return {f"{name}.{k}": v for k, v in zip(BBOX, value, strict=True)}
    return {}


@lru_cache(maxsize=65536)
def _extract(grid: Grid, _bg: int, name: str, text: str) -> tuple:
    from . import extract as ex  # lazy: extract-side modules may use features

    try:
        value = ex.run(json.loads(text), grid)
    except (ValueError, KeyError, IndexError, TypeError):
        return ()
    return tuple(_values(name, value).items())


def compute(grid: Grid, extracts: Mapping[str, object] | None = None) -> dict[str, int]:
    """Feature dict of ``grid`` (cached per grid), plus extract features."""
    bg = bgc.of(grid)
    out = dict(zip(NAMES, _compute(grid, bg), strict=True))
    for name, body in (EXTRA if extracts is None else extracts).items():
        out.update(_extract(grid, bg, name, json.dumps(body)))
    return out


def source(feature: str) -> str | None:
    """Extract block name behind an extract feature name, else None."""
    head = feature.split(".", 1)[0]
    return head if head.startswith("extract_") and feature not in NAMES else None


def known(feature: object) -> bool:
    """A base feature or one of an installed extract block."""
    if not isinstance(feature, str):
        return False
    return feature in NAMES or (source(feature) or "") in EXTRA


def names_of(extracts: Mapping[str, object]) -> list[str]:
    """Every feature name the extracts can yield (bbox gives four)."""
    out = []
    for name, body in extracts.items():
        prop = body[0] if isinstance(body, list) and body else None
        out += [f"{name}.{k}" for k in BBOX] if prop == "bbox" else [name]
    return out


def install(extracts: Mapping[str, object]) -> None:
    """Set the default extract features (numeric-property bodies only)."""
    EXTRA.clear()
    for name, body in extracts.items():
        if isinstance(body, list) and body and body[0] in NUMERIC_PROPS:
            EXTRA[name] = body


def fg_color(grid: Grid) -> int | None:
    """Most frequent non-background color (ties toward the smaller color)."""
    bg = bgc.of(grid)
    counts = g.color_counts(grid)
    rest = [c for c in counts if c != bg]
    return min(rest, key=lambda c: (-counts[c], c)) if rest else None


__all__ = ["EXTRA", "NAMES", "compute", "fg_color", "install", "known"]
