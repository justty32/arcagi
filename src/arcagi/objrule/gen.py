"""Object-scope extractions scored on training for ``arcagi.blocks.gen_extract``.

A body *supports* a task when, for some action kind (recolor / move / extend)
and connectivity, it explains the per-object train targets of that task
(``fit.targets`` + ``fit.explains``: every targeted object, >= 3 objects, >= 2
distinct values). Only same-shape tasks take part.
"""

import json
from collections.abc import Sequence

from arcagi.dsl import background as bgc
from arcagi.dsl import grid as g
from arcagi.dsl.objects_props import CONNS
from arcagi.tasks import Grid, Task

from . import fit
from . import view as ov

DEFAULT_BUDGET = 400  # used when the pool budget module is unavailable


def budget(generator: str, used: int) -> int:
    """Object-scope candidates left after ``used`` grid-scope ones."""
    try:
        from arcagi.blocks.pool.budget import allocate, announce
    except ImportError:
        return DEFAULT_BUDGET
    total = allocate().get(generator, DEFAULT_BUDGET + used)
    announce(generator, total)
    return max(total - used, 0)


def all_bodies() -> list[dict]:
    """Every object-scope body in canonical order, one per (sel, prop)."""
    props = sorted({p for ps in fit.KIND_PROPS.values() for p in ps})
    return ov.bodies(props)


def _rows(task: Task) -> list[tuple[str, list[Grid], fit.Targets]]:
    pairs = [(e.input, e.output) for e in task.train]
    if any(o is None or g.shape(i) != g.shape(o) for i, o in pairs):
        return []
    states = [i for i, _ in pairs]
    outs = [o for _, o in pairs]
    found = []
    for kind in fit.KIND_PROPS:
        for conn in CONNS:
            try:
                rows = fit.targets(kind, conn, states, outs)  # type: ignore[arg-type]
            except fit.ERRORS:
                continue
            if rows is not None:
                found.append((kind, states, rows))
    return found


def score(
    tasks: Sequence[Task], bodies: Sequence[dict]
) -> list[tuple[dict, frozenset]]:
    """``(body, supported task ids)`` for every body, in input order."""
    support: dict[str, set[str]] = {}
    keys = [json.dumps(b, sort_keys=True) for b in bodies]
    for task in tasks:
        grids = [e.input for e in task.train] + [
            e.output for e in task.train if e.output is not None
        ]
        with bgc.task_context(bgc.task_background(grids)):
            for kind, states, rows in _rows(task):
                props = fit.KIND_PROPS[kind]
                for key, body in zip(keys, bodies, strict=True):
                    if body["prop"] in props and fit.explains(body, states, rows):
                        support.setdefault(key, set()).add(task.task_id)
    return [
        (b, frozenset(support.get(k, ()))) for k, b in zip(keys, bodies, strict=True)
    ]
