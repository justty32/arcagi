"""Terminal learner ``object_colormap``: object attribute value -> new color.

Table format (JSON-friendly): ``[conn, attr, [[key, color], ...]]`` where
missing keys and ``color == KEEP`` leave the object unchanged. A key must be
seen on at least ``MIN_SUPPORT`` train objects and every test object's key must
be in the table, so the rule never memorizes a single example.

Split form ``[conn, attr, [[value, color]], other]``: objects whose ``attr``
equals ``value`` get ``color``, all others get ``other`` (or KEEP). Both sides
need ``MIN_SUPPORT`` train objects; test keys may then be unseen.
"""

from collections import Counter
from collections.abc import Sequence

from arcagi.tasks import Grid

from . import grid as g
from .objects_props import ATTRS, CONNS, extract

type ObjectTable = list[object]
KEEP = -1
MIN_SUPPORT = 2


def apply_object_colormap(grid: Grid, table: ObjectTable) -> Grid:
    conn, attr, rows, *rest = table
    other = rest[0] if rest else KEEP
    lookup = {key: color for key, color in rows}  # type: ignore[union-attr]
    out = [list(row) for row in grid]
    for o in extract(grid, conn):  # type: ignore[arg-type]
        color = lookup.get(o.props[attr], other)  # type: ignore[index]
        if color != KEEP:
            for y, x in o.cells:
                out[y][x] = color
    return tuple(tuple(row) for row in out)


def _bg_untouched(states: Sequence[Grid], targets: Sequence[Grid]) -> bool:
    """True when something changed and every changed cell was non-background."""
    any_change = False
    for state, target in zip(states, targets, strict=True):
        if g.shape(state) != g.shape(target):
            return False
        bg = g.background(state)
        for rs, rt in zip(state, target, strict=True):
            for a, b in zip(rs, rt, strict=True):
                if a != b:
                    if a == bg:
                        return False
                    any_change = True
    return any_change


def _labels(states: Sequence[Grid], targets: Sequence[Grid], conn: str):
    """Per train object (obj, label): target color if uniform, KEEP if unchanged."""
    out = []
    for state, target in zip(states, targets, strict=True):
        for o in extract(state, conn):
            values = {target[y][x] for y, x in o.cells}
            if len(values) == 1:
                out.append((o, values.pop()))
            elif all(
                target[y][x] == c for (y, x), c in zip(o.cells, o.colors, strict=True)
            ):
                out.append((o, KEEP))
            else:
                return None
    return out


def _fit_attr(labeled, tests: Sequence[Grid], conn: str, attr: str):
    options: dict[object, set[int]] = {}
    support: Counter[object] = Counter()
    for o, label in labeled:
        key = o.props[attr]
        # A uniform object already of the target color is compatible with KEEP.
        allowed = {label, KEEP} if set(o.colors) == {label} else {label}
        options[key] = options.get(key, allowed) & allowed
        if not options[key]:
            return None
        support[key] += 1
    lookup = {k: KEEP if KEEP in v else min(v) for k, v in options.items()}
    if any(n < MIN_SUPPORT for key, n in support.items() if lookup[key] != KEEP):
        return None
    if all(color == KEEP for color in lookup.values()):
        return None
    for test in tests:
        for o in extract(test, conn):
            key = o.props[attr]
            if key not in lookup or support[key] < MIN_SUPPORT:
                return None
    return sorted([key, color] for key, color in lookup.items() if color != KEEP)


def _options(labeled, attr: str) -> dict[object, list[set[int]]]:
    grouped: dict[object, list[set[int]]] = {}
    for o, label in labeled:
        # A uniform object already of the target color is compatible with KEEP.
        allowed = {label, KEEP} if set(o.colors) == {label} else {label}
        grouped.setdefault(o.props[attr], []).append(allowed)
    return grouped


def _pick(sets: list[set[int]], prefer_keep: bool) -> int | None:
    common = set.intersection(*sets) if sets else set()
    if not common:
        return None
    if prefer_keep and KEEP in common:
        return KEEP
    return min(common - {KEEP}, default=KEEP)


def _fit_split(labeled, attr: str):
    """``attr == value`` -> one color, everything else -> another (or KEEP)."""
    grouped = _options(labeled, attr)
    if len(grouped) < 2:
        return None
    for value in sorted(grouped, key=str):
        inside = grouped[value]
        outside = [s for key, sets in grouped.items() if key != value for s in sets]
        if len(inside) < MIN_SUPPORT or len(outside) < MIN_SUPPORT:
            continue
        color, other = _pick(inside, False), _pick(outside, True)
        if color is None or other is None or color in (KEEP, other):
            continue
        return [[value, color]], other
    return None


def fit_object_colormap(
    states: Sequence[Grid], targets: Sequence[Grid], tests: Sequence[Grid]
) -> ObjectTable | None:
    """Smallest attribute table that recolors whole objects to reproduce train."""
    if not _bg_untouched(states, targets):
        return None
    best: ObjectTable | None = None
    for conn in CONNS:
        labeled = _labels(states, targets, conn)
        if labeled is None:
            continue
        found: list[ObjectTable] = []
        for attr in ATTRS:
            rows = _fit_attr(labeled, tests, conn, attr)
            if rows is not None:
                found.append([conn, attr, rows])
        for attr in ATTRS:
            split = _fit_split(labeled, attr)
            if split is not None:
                found.append([conn, attr, split[0], split[1]])
        for table in found:
            if best is not None and _rank(table) >= _rank(best):
                continue
            if all(
                apply_object_colormap(s, table) == t
                for s, t in zip(states, targets, strict=True)
            ):
                best = table
    return best


def _rank(table: ObjectTable) -> tuple[int, int]:
    """Plain tables (test keys all seen) before split tables, then fewer rows."""
    return len(table), len(table[2])  # type: ignore[arg-type]
