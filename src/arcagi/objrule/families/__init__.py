"""Per-object rule families owned by the aos side line S3 (``notes/rounds/支線.md``).

Add modules here and list their primitives in ``FAMILY_PRIMS``
(``name -> arcagi.dsl.primitives.Primitive``). ``objrule.prims`` merges this
table into ``OBJRULE_PRIMS``; names already defined there win.

Families: ``keyed`` (paint a region around / inside each object with a color
looked up by an object property), ``parts`` (the same over a part of the
object: a half, every other cell), ``stamp`` (a fixed pattern per key),
``bridge`` (join same-colored aligned objects), ``rays`` (ray directions per
key), ``mirror`` (complete symmetry about a center object), ``moves`` (one step
toward the source, erase unmatched objects), ``template`` (paste an in-grid
template onto markers). ``scope`` adds ``conn@color`` (objects re-extracted on
another background color) and ``group`` (all cells of a color as one object).
"""

from arcagi.dsl.primitives import Primitive

from .bridge import BRIDGE_PRIMS
from .keyed import KEYED_PRIMS
from .mirror import MIRROR_PRIMS
from .moves import MOVES_PRIMS
from .parts import PARTS_PRIMS
from .rays import RAYS_PRIMS
from .stamp import STAMP_PRIMS
from .template import TEMPLATE_PRIMS

FAMILY_PRIMS: dict[str, Primitive] = {
    **KEYED_PRIMS,
    **STAMP_PRIMS,
    **BRIDGE_PRIMS,
    **RAYS_PRIMS,
    **MIRROR_PRIMS,
    **PARTS_PRIMS,
    **MOVES_PRIMS,
    **TEMPLATE_PRIMS,
}
