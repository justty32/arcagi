"""Per-object rules: actions whose parameter is read from each object.

``OBJRULE_PRIMS`` (``recolor_from`` / ``move_from`` / ``extend_from``) is loaded
lazily so ``arcagi.dsl.extract`` can import ``arcagi.objrule.view`` without a
cycle. Modules: ``view`` (object-scope selectors / properties), ``fit`` (per-
object train targets and sources), ``prims`` (primitives), ``gen`` (object-scope
extraction scoring for ``arcagi.blocks.gen_extract``).
"""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "OBJRULE_PRIMS":
        from .prims import OBJRULE_PRIMS

        return OBJRULE_PRIMS
    raise AttributeError(name)


__all__ = ["OBJRULE_PRIMS"]
