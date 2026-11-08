"""Mining driver: shared subtrees (plain and slotted) -> report lines / blocks.

Plain subtrees land only when at least ``MIN_LANDED`` reach ``min_tasks``;
otherwise ``min_tasks=2`` candidates are listed, never written. Slotted
subtrees land when they reach ``min_tasks``. At most ``LIMIT`` blocks in all.
"""

import json
from pathlib import Path

from arcagi.blocks.catalog import load_catalog
from arcagi.blocks.library import task_programs

from .fold import canonical, fold_refs, macro_refs, node_count
from .promote import promote, subtree_program, thaw
from .slots import fold_slots, promote_slots, shared_slot_subtrees, slot_name
from .subtree import expand, shared_subtrees

LIMIT = 10
MIN_LANDED = 3


def _records(paths: list[Path]):
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


def fold_stats(
    programs: dict, macros: dict, refs: dict, templates: dict | None = None
) -> tuple[int, int]:
    """Total nodes of all programs expanded vs folded (``$ref``, then slots)."""
    before = after = 0
    for progs in programs.values():
        for program in progs:
            flat = expand(program, macros)
            before += node_count(flat)
            folded = fold_refs(thaw(flat), refs)  # type: ignore[arg-type]
            after += node_count(fold_slots(folded, templates or {}))
    return before, after


def mine(traces: list[Path], root: Path, min_tasks: int = 3, *, write: bool = False):
    programs = task_programs(_records(traces))
    macros = load_catalog(root).macros(include_covered=True)
    refs = macro_refs(root)
    sources = [str(p) for p in traces]
    yield f"{len(programs)} tasks, {sum(map(len, programs.values()))} programs"
    plain = shared_subtrees(programs, min_tasks, macros=macros, limit=LIMIT)
    land_plain = len(plain) >= MIN_LANDED
    if not land_plain:
        yield f"plain subtrees at min_tasks={min_tasks}: {len(plain)} (< {MIN_LANDED})"
        plain = shared_subtrees(programs, 2, macros=macros, limit=LIMIT)
        yield "candidates at min_tasks=2 (not written):"
    for sub in plain:
        program = subtree_program(sub.steps, refs)
        yield f"  plain [{sub.status}] tasks={len(sub.tasks)} {canonical(program)}"
        if write and land_plain:
            promote(sub, root=root, macros=refs, sources=sources)
    slotted = shared_slot_subtrees(
        programs,
        min_tasks,
        macros=macros,
        limit=LIMIT - (len(plain) if land_plain else 0),
    )
    new_refs = dict(refs)
    for sub in slotted:
        yield (
            f"  slot {slot_name(sub.template)} [{sub.status}] tasks={len(sub.tasks)} "
            f"{canonical(sub.template)} slots={canonical(sub.slots)}"
        )
        if write:
            promote_slots(sub, root=root, macros=refs, sources=sources)
    if land_plain and write:
        new_refs = macro_refs(root)
    before, after = fold_stats(programs, macros, new_refs)
    templates = {slot_name(s.template): s.template for s in slotted}
    _, with_slots = fold_stats(programs, macros, new_refs, templates)
    yield f"nodes expanded={before} folded($ref)={after} +slots={with_slots}"
