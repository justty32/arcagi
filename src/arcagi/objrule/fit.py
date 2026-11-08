"""Per-object targets on train pairs and the parameter sources that explain them.

A *target* maps each changed train object to the set of parameter values that
reproduce it (new color, slide direction, ray direction). A *source* is an
object-scope extraction whose value on every targeted object lies in its set;
live blocks (``extract.LIVE_OBJ``) are tried before inline bodies. Anti-
memorization: at least ``MIN_OBJECTS`` targeted objects and ``MIN_VALUES``
distinct source values over the train pairs, else no source is returned.
"""

from collections.abc import Callable, Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import extract as ex
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import (
    Labeled,
    Obj,
    changed,
    extract,
    pred_selectors,
    separate,
)
from arcagi.tasks import Grid

from . import view as ov

MIN_OBJECTS = 3
MIN_VALUES = 2
MAX_SOURCES = 2
MAX_SELECTORS = 3
ERRORS = (ValueError, KeyError, IndexError, TypeError)
type Targets = list[list[tuple[Obj, set | None]]]  # per pair: (obj, values|None)
KIND_PROPS = {"recolor": ("color",), "move": ("dir_to", "wall_dir")}
KIND_PROPS["extend"] = KIND_PROPS["move"]


def uniform(obj: Obj, target: Grid) -> int | None:
    values = {target[y][x] for y, x in obj.cells}
    return values.pop() if len(values) == 1 else None


def shift_dirs(o: Obj, target: Grid) -> set[str]:
    """Directions in which a shifted copy of ``o`` appears intact in ``target``."""
    height, width = g.shape(target)
    found = set()
    for name, (dy, dx) in ov.DIRS.items():
        for k in range(1, max(height, width)):
            moved = [(y + dy * k, x + dx * k) for y, x in o.cells]
            if not all(0 <= y < height and 0 <= x < width for y, x in moved):
                break
            if all(
                target[y][x] == c for (y, x), c in zip(moved, o.colors, strict=True)
            ):
                found.add(name)
                break
    return found


def grow_dirs(o: Obj, target: Grid, state: Grid) -> set[str]:
    """Directions where the background cell just past ``o`` took its color."""
    height, width = g.shape(target)
    bg = bgc.of(state)
    own = set(o.cells)
    found = set()
    for name, (dy, dx) in ov.DIRS.items():
        for (y, x), c in zip(o.cells, o.colors, strict=True):
            ny, nx = y + dy, x + dx
            if (ny, nx) in own or not (0 <= ny < height and 0 <= nx < width):
                continue
            if state[ny][nx] == bg and target[ny][nx] == c:
                found.add(name)
                break
    return found


def _recolor_value(o: Obj, state: Grid, target: Grid) -> set | None:
    if not changed(o, target):
        return None
    c = uniform(o, target)
    return {c} if c is not None and c != bgc.of(state) else set()


def _move_value(o: Obj, state: Grid, target: Grid) -> set | None:
    """Slide directions; an erased object is don't-care (a later step)."""
    if not changed(o, target):
        return None
    dirs = shift_dirs(o, target)
    return dirs or (None if uniform(o, target) == bgc.of(state) else dirs)


def _extend_value(o: Obj, state: Grid, target: Grid) -> set | None:
    return grow_dirs(o, target, state) or None


VALUE_OF: dict[str, Callable[[Obj, Grid, Grid], set | None]] = {
    "recolor": _recolor_value,
    "move": _move_value,
    "extend": _extend_value,
}


def targets(
    kind: str, conn: str, states: Sequence[Grid], outs: Sequence[Grid]
) -> Targets | None:
    """Per-object targets, or None when some changed object has no value."""
    value_of = VALUE_OF[kind]
    rows: Targets = []
    n = 0
    for state, target in zip(states, outs, strict=True):
        row = [(o, value_of(o, state, target)) for o in extract(state, conn)]
        if any(v is not None and not v for _, v in row):
            return None
        n += sum(v is not None for _, v in row)
        rows.append(row)
    return rows if n >= MIN_OBJECTS else None


def explains(body: object, states: Sequence[Grid], rows: Targets) -> bool:
    """Source value lies in every targeted object's set; enough variety."""
    seen: set = set()
    count = 0
    for state, row in zip(states, rows, strict=True):
        for o, want in row:
            if want is None:
                continue
            try:
                value = ex.run_on_object(body, state, o)
            except ERRORS:
                return False
            if value not in want:
                return False
            seen.add(value)
            count += 1
    return count >= MIN_OBJECTS and len(seen) >= MIN_VALUES


def sources(kind: str, states: Sequence[Grid], rows: Targets) -> list[object]:
    """Live object-extract names that explain ``rows``, else inline bodies."""
    props = KIND_PROPS[kind]
    hits: list[object] = []
    for name, body in ex.LIVE_OBJ.items():
        if body["prop"] in props and explains(body, states, rows):
            hits.append(name)
            if len(hits) >= MAX_SOURCES:
                return hits
    if hits:
        return hits
    for body in ov.bodies(props):
        if explains(body, states, rows):
            hits.append(body)
            if len(hits) >= MAX_SOURCES:
                break
    return hits


def noop(kind: str, o: Obj, value: object, state: Grid) -> bool:
    """True when applying ``value`` to ``o`` would change nothing."""
    if kind == "recolor":
        return {value} == set(o.colors)
    if value not in ov.DIRS:
        return False
    dy, dx = ov.DIRS[value]  # type: ignore[index]
    height, width = g.shape(state)
    bg, own = bgc.of(state), set(o.cells)
    for y, x in o.cells:
        ny, nx = y + dy, x + dx
        if (ny, nx) not in own and 0 <= ny < height and 0 <= nx < width:
            if state[ny][nx] == bg:
                return False
    return True


def selectors(
    kind: str, conn: str, states: Sequence[Grid], rows: Targets, source: object
) -> list[tuple[str, object]]:
    """``(attr, value)`` selectors picking the targeted objects."""

    def label(o: Obj, want: set | None, state: Grid) -> bool | None:
        if want is not None:
            return True
        try:
            value = ex.run_on_object(source, state, o)
        except ERRORS:
            return None  # the action skips objects without a source value
        return None if noop(kind, o, value, state) else False

    examples: list[Labeled] = [
        [(o, label(o, want, s)) for o, want in row]
        for s, row in zip(states, rows, strict=True)
    ]
    found: list[tuple[str, object]] = list(separate(examples))
    labels = [[lab for _, lab in e] for e in examples]
    found += [("pred", n) for n in pred_selectors(states, conn, labels)]
    return found[:MAX_SELECTORS]
