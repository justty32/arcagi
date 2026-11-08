"""Subtrees as blocks: step runs shared by several training programs.

A train-passing program is a chain ``prog -> step -> params``; its subtrees
worth reusing are contiguous step runs with fixed parameters. Macro-name
steps are expanded first so a run can span an existing macro, learner steps
(fitted tables) are excluded, and so are runs carrying task-specific
constants: a literal grid of at least 3x3 or a literal output size.
"""

from collections import defaultdict
from dataclasses import dataclass

from arcagi.blocks import LEARNER_NAMES

type Step = tuple[object, ...]
type Fragment = tuple[Step, ...]
type Programs = dict[str, list[Fragment]]

# Primitives whose parameters are an absolute output height/width.
SIZE_PRIMITIVES = frozenset({"resize_crop", "canvas"})
DEFAULT_SIZES = (2, 3, 4, 5)


@dataclass(frozen=True)
class Subtree:
    steps: Fragment
    tasks: tuple[str, ...]
    status: str  # live | covered


def is_literal_grid(value: object) -> bool:
    """A rectangular-ish list of >= 3 rows each with >= 3 cells."""
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 3
        and all(isinstance(r, (list, tuple)) and len(r) >= 3 for r in value)
    )


def _has_grid(value: object) -> bool:
    if is_literal_grid(value):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_grid(v) for v in value)
    if isinstance(value, dict):
        return any(_has_grid(v) for v in value.values())
    return False


def has_task_constant(step: Step) -> bool:
    if step[0] in SIZE_PRIMITIVES:
        return True
    return any(_has_grid(p) for p in step[1:])


def expand(program: Fragment, macros: dict[str, Fragment]) -> Fragment:
    """Inline macro-name steps (recursively) into their primitive steps."""
    out: list[Step] = []
    for step in program:
        if len(step) == 1 and step[0] in macros:
            out.extend(expand(macros[step[0]], macros))  # type: ignore[arg-type]
        else:
            out.append(step)
    return tuple(out)


def _freeze(value: object) -> object:
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, dict):
        return ("__dict__", tuple((k, _freeze(v)) for k, v in value.items()))
    return value


def _windows(program: Fragment, sizes: tuple[int, ...]) -> set[Fragment]:
    out = set()
    for size in sizes:
        for start in range(len(program) - size + 1):
            window = program[start : start + size]
            if not any(s[0] in LEARNER_NAMES or has_task_constant(s) for s in window):
                out.add(_freeze(window))  # type: ignore[arg-type]
    return out


def _inside(small: Fragment, big: Fragment) -> bool:
    n = len(small)
    return any(big[i : i + n] == small for i in range(len(big) - n + 1))


def shared_subtrees(
    programs: Programs,
    min_tasks: int = 3,
    *,
    macros: dict[str, Fragment] | None = None,
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    limit: int = 10,
) -> list[Subtree]:
    """Runs shared by ``>= min_tasks`` tasks, most tasks first, at most ``limit``.

    Runs equal to an existing macro are skipped, as is a run contained in a
    longer kept run with the same task set (only maximal runs survive).
    ``status`` follows ``blocks.library``: covered when every task already has
    a cheaper program without the run.
    """
    macros = macros or {}
    expanded = {t: [expand(p, macros) for p in progs] for t, progs in programs.items()}
    frozen = {t: [_freeze(p) for p in progs] for t, progs in expanded.items()}
    known = {_freeze(expand(m, macros)) for m in macros.values()}
    seen: dict[Fragment, set[str]] = defaultdict(set)
    for task, progs in frozen.items():
        for program in progs:
            for window in _windows(program, sizes):  # type: ignore[arg-type]
                seen[window].add(task)
    ranked = sorted(
        (kv for kv in seen.items() if len(kv[1]) >= min_tasks and kv[0] not in known),
        key=lambda kv: (-len(kv[1]), -len(kv[0]), repr(kv[0])),
    )
    kept: list[tuple[Fragment, set[str]]] = []
    for window, tasks in ranked:
        if any(
            len(big) > len(window) and tb == tasks and _inside(window, big)
            for big, tb in ranked
        ):
            continue
        kept.append((window, tasks))
    out = []
    for window, tasks in kept[:limit]:
        from arcagi.blocks.library import is_covered  # lazy: registry imports us

        status = "covered" if is_covered(window, frozen) else "live"  # type: ignore[arg-type]
        out.append(Subtree(window, tuple(sorted(tasks)), status))
    return out
