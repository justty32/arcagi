"""Extra grid primitives owned by the aos side line S1 (``notes/rounds/支線.md``).

Add modules here and list their primitives in ``EXT_PRIMS``
(``name -> arcagi.dsl.primitives.Primitive``). ``arcagi.dsl.registry`` merges
this table into ``ALL``; names already defined there win. Keep the semantics
identical to the native engine so programs stay portable.
"""

from arcagi.dsl.primitives import Params, Primitive

from . import prims as _p

# The native engine searches these; the Python search only runs and verifies
# them (no candidates), so the Python-first phase of native/bin/solve keeps its
# r05 behaviour and timing. Flip to let the Python search propose them too.
PYTHON_SEARCH = False


def _none(_states: object, _targets: object) -> list[Params]:
    return []


def _prim(name: str, apply, candidates) -> Primitive:
    return Primitive(name, apply, candidates if PYTHON_SEARCH else _none)


EXT_PRIMS: dict[str, Primitive] = {
    "x_ray": _prim("x_ray", _p.ray, _p.ray_candidates),
    "x_connect": _prim("x_connect", _p.connect, _p.connect_candidates),
    "x_compress": _prim("x_compress", _p.compress, _p.compress_candidates),
    "x_crop_color": _prim("x_crop_color", _p.crop_color, _p.crop_color_candidates),
    "x_period": _prim("x_period", _p.period, _p.period_candidates),
    "x_vrule": _prim("x_vrule", _p.vrule, _p.vrule_candidates),
}
