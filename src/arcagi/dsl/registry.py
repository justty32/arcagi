"""The full primitive registry used by programs and search.

Python implementations come from the primitive modules; the aos block folders
(``aos/blocks/``, see ``arcagi.blocks.catalog``) decide which of them are live and
add macro primitives (fixed JSON sub-programs) and live predicates (object
selectors). Without that folder the registry is exactly the Python tables.
"""

import importlib

from arcagi.blocks.catalog import load_catalog

from . import predicates
from .cells import CELLS
from .objects import OBJECTS
from .primitives import BASE, MARK, Primitive, _no_params
from .primitives_more import MORE

ALL: dict[str, Primitive] = {**BASE, **MORE, **CELLS, **OBJECTS}
CATALOG = load_catalog()
predicates.install(CATALOG.predicates())  # live pred blocks become selectors

# Round 3: formula / extract generated blocks feed parameterised primitives.
for _module, _table, _kind in (
    ("formula_prims", "FORMULA_PRIMS", "formula"),
    ("extract_prims", "EXTRACT_PRIMS", "extract"),
):
    try:
        _mod = importlib.import_module(f"{__package__}.{_module}")
    except ModuleNotFoundError as _err:
        if _err.name != f"{__package__}.{_module}":
            raise
        continue
    if hasattr(_mod, "install"):
        _mod.install(CATALOG.rules(_kind))
    ALL.update(getattr(_mod, _table))
# Round 4: per-object rules take each object's parameter from an object-scope
# extract block (``arcagi.objrule``); live object blocks arrive via extract_prims.
from arcagi.objrule import OBJRULE_PRIMS  # noqa: E402

ALL.update(OBJRULE_PRIMS)
# Object selectors widen the tree a lot; they are only tried as the first step.
FIRST_STEP_ONLY = frozenset(OBJECTS)


def _macro(program):
    def apply(grid):
        for name, *params in program:
            grid = ALL[name].apply(grid, *params)
        return grid

    return apply


PRIMITIVES: dict[str, Primitive] = {
    name: prim for name, prim in ALL.items() if name not in CATALOG.retired
}
for _name, _program in CATALOG.macros().items():
    if all(step[0] in ALL for step in _program):
        PRIMITIVES[_name] = Primitive(_name, _macro(_program), _no_params)

__all__ = ["ALL", "FIRST_STEP_ONLY", "MARK", "PRIMITIVES", "Primitive"]
