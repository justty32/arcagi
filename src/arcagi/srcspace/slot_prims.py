"""Search primitives for ``kind=slot_macro`` blocks (see ``slots``).

``slot_primitives(catalog)`` returns ``name -> Primitive``: ``apply(grid,
*values)`` fills the template's slots and runs its steps; ``candidates``
offers the stored slot tuples (observed first, at most ``MAX_COMBOS``). Only
live blocks whose steps all name known primitives are returned. The registry
lookup happens at call time, so ``arcagi.dsl.registry`` may import this module.
"""

import json
from collections.abc import Sequence

from arcagi.blocks.catalog import Catalog, RefError, expand_steps

from .slots import KIND, MAX_COMBOS, fill, slot_combos


def _make(template: list, combos: list[tuple]):
    from arcagi.dsl.primitives import Primitive

    def apply(grid, *values):
        from arcagi.dsl.registry import ALL

        for name, *params in fill(template, values):  # type: ignore[union-attr]
            grid = ALL[name].apply(grid, *params)
        return grid

    def candidates(_states: Sequence, _targets: Sequence) -> list[tuple]:
        return list(combos)

    return apply, candidates, Primitive


def slot_primitives(catalog: Catalog, *, known: frozenset[str] | None = None) -> dict:
    """Live slot-macro blocks as ``Primitive`` objects keyed by block name."""
    if known is None:
        from arcagi.dsl.registry import ALL

        known = frozenset(ALL)
    found = {}
    for name, block in sorted(catalog.blocks.items()):
        if block.kind != KIND or block.status != "live":
            continue
        path = block.path / "program.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            here = path.resolve()
            template = expand_steps(raw, here.parent, ((str(here), ""),))
        except (OSError, ValueError, RefError):
            continue
        if not isinstance(template, list) or not all(
            isinstance(s, list) and s and s[0] in known for s in template
        ):
            continue
        combos = slot_combos(block.meta, MAX_COMBOS)
        if not combos:
            continue
        apply, candidates, primitive = _make(template, combos)
        found[name] = primitive(name, apply, candidates)
    return found
