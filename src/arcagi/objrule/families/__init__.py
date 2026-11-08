"""Per-object rule families owned by the aos side line S3 (``notes/rounds/支線.md``).

Add modules here and list their primitives in ``FAMILY_PRIMS``
(``name -> arcagi.dsl.primitives.Primitive``). ``objrule.prims`` merges this
table into ``OBJRULE_PRIMS``; names already defined there win.

Families: ``keyed`` (paint a region around / inside each object with a color
looked up by an object property), ``stamp`` (a fixed pattern per key),
``bridge`` (join same-colored aligned objects), ``rays`` (rays in
directions chosen by key); ``scope`` adds the ``conn@color`` re-extraction.
"""

from arcagi.dsl.primitives import Primitive

from .bridge import BRIDGE_PRIMS
from .keyed import KEYED_PRIMS
from .rays import RAYS_PRIMS
from .stamp import STAMP_PRIMS

FAMILY_PRIMS: dict[str, Primitive] = {
    **KEYED_PRIMS,
    **STAMP_PRIMS,
    **BRIDGE_PRIMS,
    **RAYS_PRIMS,
}
