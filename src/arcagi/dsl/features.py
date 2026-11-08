"""Integer features of one grid, shared by formula and extract blocks.

``compute(grid)`` returns a dict ``name -> int``: size (``h``, ``w``), color
statistics (``n_color`` = distinct non-background colors, ``n_fg``, ``n_bg``,
``cnt_0`` .. ``cnt_9``) and object statistics from ``objects_props.extract``
(``n_obj`` under 4-connected single-color objects, ``n_obj8`` under 8-connected
multi-color objects, ``n_shape`` distinct shapes, max/min object h, w, size; 0
when there is no object). The background is whatever ``extract`` uses
(``arcagi.dsl.background``).
"""

from collections import Counter
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


def compute(grid: Grid) -> dict[str, int]:
    """Feature dict of ``grid`` (cached per grid)."""
    return dict(zip(NAMES, _compute(grid, bgc.of(grid)), strict=True))


def fg_color(grid: Grid) -> int | None:
    """Most frequent non-background color (ties toward the smaller color)."""
    bg = bgc.of(grid)
    counts = g.color_counts(grid)
    rest = [c for c in counts if c != bg]
    return min(rest, key=lambda c: (-counts[c], c)) if rest else None


__all__ = ["NAMES", "compute", "fg_color"]
