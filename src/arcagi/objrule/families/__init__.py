"""Per-object rule families owned by the aos side line S3 (``notes/rounds/支線.md``).

Add modules here and list their primitives in ``FAMILY_PRIMS``
(``name -> arcagi.dsl.primitives.Primitive``). ``objrule.prims`` merges this
table into ``OBJRULE_PRIMS``; names already defined there win.
"""

from arcagi.dsl.primitives import Primitive

FAMILY_PRIMS: dict[str, Primitive] = {}
