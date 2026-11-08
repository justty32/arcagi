"""Object scopes for the families: a connectivity, optionally with its own background.

A scope is a ``CONNS`` name (``"4same"``: the task background, as everywhere
else) or ``"<conn>@<c>"`` (``"4same@5"``): objects are re-extracted treating
color ``c`` as background, and the families' "background cells" become the
cells of color ``c``. This handles objects drawn on a colored panel or a
grid whose task background is not the color the objects sit on.

``scopes(states, targets)`` lists the default conns, then ``@c`` variants for
the one color every changed train cell had before the change, when that color
is not already the background of every state and survives in every target
(a color recolored away entirely is a plain recolor; ``ALT_CONNS`` only).
"""

from collections.abc import Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl.objects_props import CONNS, Obj, _extract
from arcagi.tasks import Grid

ALT_CONNS = ("4same", "8same")


def parse(conn: object) -> tuple[str, int | None]:
    if isinstance(conn, str):
        base, sep, color = conn.partition("@")
        if base in CONNS and not sep:
            return base, None
        if base in CONNS and color.isdigit() and 0 <= int(color) <= 9:
            return base, int(color)
    raise ValueError(f"bad object scope {conn!r}")


def background(grid: Grid, conn: str) -> int:
    bg = parse(conn)[1]
    return bgc.of(grid) if bg is None else bg


def objects(grid: Grid, conn: str) -> tuple[Obj, ...]:
    base, bg = parse(conn)
    return _extract(grid, base, bgc.of(grid) if bg is None else bg)


def sources(states: Sequence[Grid], targets: Sequence[Grid]) -> set[int]:
    """Colors of the input cells that change on some train pair."""
    return {
        a
        for s, t in zip(states, targets, strict=True)
        for rs, rt in zip(s, t, strict=True)
        for a, b in zip(rs, rt, strict=True)
        if a != b
    }


def scopes(states: Sequence[Grid], targets: Sequence[Grid]) -> list[str]:
    out = list(CONNS)
    src = sources(states, targets)
    if len(src) == 1:
        (c,) = src
        kept = all(any(c in row for row in t) for t in targets)
        if kept and any(bgc.of(s) != c for s in states):
            out += [f"{base}@{c}" for base in ALT_CONNS]
    return out


def paints_background(
    states: Sequence[Grid], targets: Sequence[Grid], conn: str
) -> bool:
    """Every change turns a scope-background cell into another color."""
    changed = False
    for s, t in zip(states, targets, strict=True):
        bg = background(s, conn)
        for rs, rt in zip(s, t, strict=True):
            for a, b in zip(rs, rt, strict=True):
                if a != b:
                    if a != bg:
                        return False
                    changed = True
    return changed
