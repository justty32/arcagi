"""Anti-unified subtrees: shared step runs with parameter slots.

Runs with the same step names and parameter arities, found in at least
``min_tasks`` training tasks, are generalised: parameter positions equal in
every occurrence stay fixed, the others become ``{"$slot": k}`` (1-based).
Each slot remembers the values seen in training; the block's ``candidates``
proposes observed value tuples first, then other combinations, at most
``MAX_COMBOS``. Blocks are written with ``kind=slot_macro`` so the plain macro
loader ignores them; ``slot_primitives`` turns them into search primitives.
"""

import hashlib
import itertools
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from arcagi.blocks import read_json, write_json
from arcagi.blocks.sync import write_block

from .fold import canonical, fold_refs
from .promote import thaw
from .subtree import DEFAULT_SIZES, Fragment, Programs, _freeze, _windows, expand

KIND = "slot_macro"
PREFIX = "m_sub_"
MAX_COMBOS = 30
MAX_SLOTS = 3


@dataclass(frozen=True)
class SlotSubtree:
    template: list  # JSON steps with {"$slot": k}
    slots: list[list]  # per-slot observed values, most frequent first
    combos: list[list]  # observed joint slot tuples
    tasks: tuple[str, ...]
    status: str


def _shape(window: Fragment) -> tuple:
    return tuple((step[0], len(step)) for step in window)


def anti_unify(windows: Sequence[Fragment]) -> tuple[list, list[tuple[int, int]]]:
    """Template steps and the (step, param) positions that became slots."""
    first = windows[0]
    template: list = []
    positions: list[tuple[int, int]] = []
    for si, step in enumerate(first):
        out = [step[0]]
        for pi in range(1, len(step)):
            values = {w[si][pi] for w in windows}
            if len(values) == 1:
                out.append(thaw(step[pi]))
            else:
                positions.append((si, pi))
                out.append({"$slot": len(positions)})
        template.append(out)
    return template, positions


def _slot_cost(program: Fragment, window: Fragment, n_slots: int) -> float:
    from arcagi.dsl.program import cost

    n = len(window)
    for i in range(len(program) - n + 1):
        if _shape(program[i : i + n]) == _shape(window):
            return cost(program[:i] + program[i + n :]) + 1 + 0.1 * n_slots
    return float("inf")


def shared_slot_subtrees(
    programs: Programs,
    min_tasks: int = 3,
    *,
    macros: dict[str, Fragment] | None = None,
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    limit: int = 10,
) -> list[SlotSubtree]:
    """Group runs by shape, keep groups over ``min_tasks`` tasks with 1..3 slots."""
    from arcagi.dsl.program import cost

    macros = macros or {}
    frozen = {
        t: [_freeze(expand(p, macros)) for p in progs] for t, progs in programs.items()
    }
    groups: dict[tuple, dict[Fragment, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for task, progs in frozen.items():
        for program in progs:
            for window in _windows(program, sizes):  # type: ignore[arg-type]
                groups[_shape(window)][window].add(task)
    found = []
    for shape, members in groups.items():
        tasks = set().union(*members.values())
        if len(tasks) < min_tasks or len(members) < 2:
            continue
        windows = sorted(members, key=repr)
        template, positions = anti_unify(windows)
        if not 1 <= len(positions) <= MAX_SLOTS:
            continue
        counts: list[Counter] = [Counter() for _ in positions]
        combos: Counter = Counter()
        for window, ts in members.items():
            combo = tuple(window[si][pi] for si, pi in positions)
            combos[combo] += len(ts)
            for k, value in enumerate(combo):
                counts[k][value] += len(ts)
        covered = all(
            min((cost(p) for p in frozen[t] if _shape_in(p, shape) < 0), default=1e9)
            < min(_slot_cost(p, windows[0], len(positions)) for p in frozen[t])
            for t in tasks
        )
        found.append(
            SlotSubtree(
                template=template,
                slots=[[thaw(v) for v, _ in c.most_common()] for c in counts],
                combos=[[thaw(v) for v in combo] for combo, _ in combos.most_common()],
                tasks=tuple(sorted(tasks)),
                status="covered" if covered else "live",
            )
        )
    found.sort(key=lambda s: (-len(s.tasks), -len(s.template), canonical(s.template)))
    return found[:limit]


def _shape_in(program: Fragment, shape: tuple) -> int:
    n = len(shape)
    for i in range(len(program) - n + 1):
        if _shape(program[i : i + n]) == shape:
            return i
    return -1


def slot_name(template: list) -> str:
    return PREFIX + hashlib.sha1(canonical(template).encode()).hexdigest()[:8]


def promote_slots(
    sub: SlotSubtree,
    *,
    root: Path,
    macros: dict[str, list] | None = None,
    sources: list[str] | None = None,
) -> Path:
    """Write ``m_sub_<hash>/`` with ``program.json`` template and metainfo slots."""
    name = slot_name(sub.template)
    folder = Path(root) / name
    program = fold_refs(sub.template, macros or {})
    old = read_json(folder / "_metainfo.json", {}) or {}
    status = "retired" if old.get("status") == "retired" else sub.status  # type: ignore[union-attr]
    write_block(
        folder,
        {
            "name": name,
            "kind": KIND,
            "doc": "Subtree with slots: " + canonical(sub.template),
            "params": [f"${k + 1}" for k in range(len(sub.slots))],
            "slots": sub.slots,
            "slot_combos": sub.combos,
            "source_tasks": list(sub.tasks),
            "source_traces": sources or [],
            "origin": "srcspace.slots",
        },
    )
    meta = read_json(folder / "_metainfo.json", {})
    meta["status"] = status  # type: ignore[index]
    write_json(folder / "_metainfo.json", meta)
    write_json(folder / "program.json", program)
    return folder


def fill(template: object, values: Sequence[object]) -> object:
    """Replace every ``{"$slot": k}`` with ``values[k-1]``."""
    if isinstance(template, dict) and list(template) == ["$slot"]:
        return values[template["$slot"] - 1]
    if isinstance(template, list):
        return [fill(v, values) for v in template]
    return template


def slot_combos(meta: dict, limit: int = MAX_COMBOS) -> list[tuple]:
    """Observed tuples first, then the product of per-slot values; capped."""
    seen: dict[str, tuple] = {}
    observed = [tuple(c) for c in meta.get("slot_combos", [])]
    for combo in itertools.chain(observed, itertools.product(*meta.get("slots", []))):
        seen.setdefault(canonical(list(combo)), tuple(combo))
        if len(seen) >= limit:
            break
    return list(seen.values())


def _match(template: list, run: list) -> list | None:
    """Slot values if ``run`` instantiates ``template``, else None."""
    values: dict[int, object] = {}
    for tstep, step in zip(template, run, strict=True):
        if not isinstance(step, list) or len(tstep) != len(step):
            return None
        for t, v in zip(tstep, step, strict=True):
            if isinstance(t, dict) and list(t) == ["$slot"]:
                values[t["$slot"]] = v
            elif t != v:
                return None
    return [values[k] for k in sorted(values)]


def fold_slots(program: list, templates: dict[str, list]) -> list:
    """Replace runs matching a slot template by ``[name, *values]`` steps."""
    out: list = []
    i = 0
    while i < len(program):
        for name, template in templates.items():
            run = program[i : i + len(template)]
            values = _match(template, run) if len(run) == len(template) else None
            if values is not None:
                out.append([name, *values])
                i += len(template)
                break
        else:
            out.append(program[i])
            i += 1
    return out
