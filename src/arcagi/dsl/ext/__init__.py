"""Extra grid primitives owned by the aos side line S1 (``notes/rounds/支線.md``).

Add modules here and list their primitives in ``EXT_PRIMS``
(``name -> arcagi.dsl.primitives.Primitive``). ``arcagi.dsl.registry`` merges
this table into ``ALL``; names already defined there win. Keep the semantics
identical to the native engine so programs stay portable.
"""

from arcagi.dsl.primitives import Primitive

EXT_PRIMS: dict[str, Primitive] = {}
