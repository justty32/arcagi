"""Rewrite rules over JSON programs (tuples of ``(name, *params)`` steps).

Each rule is a function ``rule(program, ctx) -> Iterator[Program]`` that yields
programs one edit away from ``program``. ``ctx`` (see ``arcagi.solvers.rewrite``)
supplies the intermediate train grids of a program prefix and the targets, so
rules that need fresh parameters infer them the way the BFS does, from the
examples. The table ``RULES`` is fixed and ordered cheap-first.
"""

import inspect
from collections.abc import Callable, Iterator, Sequence
from itertools import islice
from typing import Protocol

from arcagi.dsl.objects_props import CONNS
from arcagi.dsl.program import Program, Step
from arcagi.dsl.registry import CATALOG, FIRST_STEP_ONLY, PRIMITIVES
from arcagi.objrule import OBJRULE_PRIMS
from arcagi.tasks import Grid

LEARNERS = frozenset({"colormap", "object_colormap", "local_rule"})
INSERT_CAP = 12  # parameter candidates per primitive and insert position
OBJRULE_CAP = 24  # per-object rule candidates per primitive
_ALIASES = {"ny": "fy", "nx": "fx"}


class Context(Protocol):
    targets: Sequence[Grid]
    palette: Sequence[int]  # colors seen in the task's train grids

    def states(self, prefix: Program) -> list[Grid] | None: ...


type Rule = Callable[[Program, Context], Iterator[Program]]


def _signature(name: str) -> tuple[str, ...] | None:
    try:
        params = list(inspect.signature(PRIMITIVES[name].apply).parameters.values())
    except (TypeError, ValueError):
        return None
    if any(p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) for p in params[1:]):
        return None
    return tuple(_ALIASES.get(p.name, p.name) for p in params[1:])


SIGNATURES = {name: _signature(name) for name in PRIMITIVES}
MACROS = tuple(name for name in CATALOG.macros() if name in PRIMITIVES)


def _replace(program: Program, index: int, step: Step) -> Program:
    return (*program[:index], step, *program[index + 1 :])


def _neighbors(value: object, palette: Sequence[int]) -> list[object]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int):
        values = [*palette, value - 1, value + 1]
        return list(dict.fromkeys(v for v in values if v != value))
    if isinstance(value, str) and value in CONNS:
        return [c for c in CONNS if c != value]
    return []


def param_neighbors(program: Program, ctx: Context) -> Iterator[Program]:
    """One-coordinate scan: ints -> task colors and +-1, conn -> other kinds."""
    for i, step in enumerate(program):
        if step[0] in LEARNERS:
            continue
        for j, value in enumerate(step[1:], start=1):
            for other in _neighbors(value, ctx.palette):
                yield _replace(program, i, (*step[:j], other, *step[j + 1 :]))


def swap_prim(program: Program, ctx: Context) -> Iterator[Program]:
    """Swap a step's primitive for another one with the same parameter names."""
    for i, step in enumerate(program):
        sig = SIGNATURES.get(step[0])  # type: ignore[call-overload]
        if sig is None:
            continue
        for name, other in SIGNATURES.items():
            if name == step[0] or other != sig:
                continue
            if i and name in FIRST_STEP_ONLY:
                continue
            yield _replace(program, i, (name, *step[1:]))


def _one_step(states, targets, names, cap: int = INSERT_CAP) -> Iterator[Step]:
    """One step per primitive in ``names``, parameters inferred states -> targets."""
    for name in names:
        try:
            cands = list(islice(PRIMITIVES[name].candidates(states, targets), cap))
        except (ValueError, IndexError, KeyError, ZeroDivisionError):
            continue
        for params in cands:
            yield (name, *params)


def residual(program: Program, ctx: Context) -> Iterator[Program]:
    """Residual sub-task: solve program output -> target with one more step.

    Every non-object-rule primitive proposes parameters from the program's final
    train grids against the targets (``append_objrule`` does the object rules).
    """
    states = ctx.states(program)
    if states is None or list(states) == list(ctx.targets):
        return
    names = [
        n
        for n in PRIMITIVES
        if n not in OBJRULE_PRIMS and not (program and n in FIRST_STEP_ONLY)
    ]
    for step in _one_step(states, ctx.targets, names):
        yield (*program, step)


def insert_step(program: Program, ctx: Context) -> Iterator[Program]:
    """Insert one primitive before some step; parameters inferred on the grids
    there (appending at the end is ``residual``)."""
    for pos in range(len(program) - 1, -1, -1):
        states = ctx.states(program[:pos])
        if states is None:
            continue
        names = [n for n in PRIMITIVES if not (pos and n in FIRST_STEP_ONLY)]
        for step in _one_step(states, ctx.targets, names):
            yield (*program[:pos], step, *program[pos:])


def delete_step(program: Program, ctx: Context) -> Iterator[Program]:
    for i in range(len(program)):
        yield (*program[:i], *program[i + 1 :])


def swap_adjacent(program: Program, ctx: Context) -> Iterator[Program]:
    for i in range(len(program) - 1):
        if program[i] != program[i + 1]:
            yield (*program[:i], program[i + 1], program[i], *program[i + 2 :])


def macro_ref(program: Program, ctx: Context) -> Iterator[Program]:
    """Replace a contiguous run of steps by one existing macro (``m_*`` block)."""
    for start in range(len(program)):
        for stop in range(start + 1, len(program) + 1):
            for name in MACROS:
                if start and name in FIRST_STEP_ONLY:
                    continue
                yield (*program[:start], (name,), *program[stop:])


def append_objrule(program: Program, ctx: Context) -> Iterator[Program]:
    """Append one per-object rule fitted on the program's final grids."""
    states = ctx.states(program)
    if states is None:
        return
    names = [n for n in OBJRULE_PRIMS if n in PRIMITIVES]
    for step in _one_step(states, ctx.targets, names, OBJRULE_CAP):
        yield (*program, step)


RULES: dict[str, Rule] = {
    "residual": residual,
    "append_objrule": append_objrule,
    "param_neighbors": param_neighbors,
    "delete_step": delete_step,
    "swap_adjacent": swap_adjacent,
    "swap_prim": swap_prim,
    "macro_ref": macro_ref,
    "insert_step": insert_step,
}


def literal_grid(value: object) -> bool:
    """True for a >=3x3 nested-list literal (a memorised grid), at any depth."""
    if not isinstance(value, (list, tuple)):
        return False
    rows = [v for v in value if isinstance(v, (list, tuple))]
    if len(rows) >= 3 and all(
        len(r) >= 3 and all(isinstance(x, int) for x in r) for r in rows
    ):
        return True
    return any(literal_grid(v) for v in value)


def has_literal_grid(program: Program) -> bool:
    return any(
        literal_grid(p) for step in program if step[0] not in LEARNERS for p in step[1:]
    )


def objrule_misplaced(program: Program) -> bool:
    """Gate: >1 per-object rule step, or one followed by a non-learner step.

    Object rules are fitted against the final targets; chaining them or
    editing their output overfitted every such training case (r05 line B).
    """
    spots = [i for i, step in enumerate(program) if step[0] in OBJRULE_PRIMS]
    if not spots:
        return False
    tail = [step[0] for step in program[spots[0] + 1 :]]
    return len(spots) > 1 or any(name not in LEARNERS for name in tail)


__all__ = [
    "MACROS",
    "RULES",
    "Context",
    "Rule",
    "has_literal_grid",
    "literal_grid",
    "objrule_misplaced",
]
