"""The seed engine used by the learning loop (read-only calls into arcagi.seed).

Compatible with two seed signatures: r07 (``decompose: bool``) and r08
(``decompose: bool | frozenset[str]``, ``sub_lam_depth``, ``seed.decomp
.SPLITS`` / ``DEFAULT_SPLITS``).
"""

import inspect

from arcagi.seed import decomp as _decomp
from arcagi.seed import prims
from arcagi.seed import prims as _seed
from arcagi.seed.enum import solve
from arcagi.seed.interp import EvalError, run
from arcagi.seed.library import Library

ENGINE = "seed"
_PARAMS = inspect.signature(solve).parameters
_HAS_DECOMP = "decompose" in _PARAMS
_HAS_SUB_LAM = "sub_lam_depth" in _PARAMS
SPLITS: tuple[str, ...] = tuple(getattr(_decomp, "SPLITS", ()))
DEFAULT_SPLITS: frozenset[str] = frozenset(getattr(_decomp, "DEFAULT_SPLITS", ()))
HAS_SPLIT_SETS = _HAS_SUB_LAM and bool(SPLITS)

# Knob values for ``decomp_set``: "default" = the seed's DEFAULT_SPLITS,
# "default+halves" adds one split, "none" turns decomposition off.
DECOMP_SETS = ["none", "default", "default+halves", "default+nest",
               "default+halves+nest"]


def split_set(name: str) -> frozenset[str] | bool:
    """Map a ``decomp_set`` knob value to the seed's ``decompose`` argument."""
    if name == "none":
        return False
    parts = name.split("+")
    if parts[0] != "default":
        raise ValueError(f"bad decomp_set {name!r}")
    if len(parts) == 1:
        return True
    if not HAS_SPLIT_SETS:
        raise RuntimeError(f"this seed has no split sets ({name})")
    extra = frozenset(parts[1:])
    unknown = extra - set(SPLITS)
    if unknown:
        raise RuntimeError(f"unknown splits {sorted(unknown)}")
    return DEFAULT_SPLITS | extra


def solve_with(train, lib, budget, order, decomp: bool,
               decomp_set: str = "default", sub_lam_depth: int | None = None):
    """``seed.enum.solve`` with decomposition explicitly on or off.

    ``decomp=False`` always means plain enumeration; with ``decomp`` on,
    ``decomp_set`` picks the split set (r08 seed only for non-default sets).
    """
    if not _HAS_DECOMP:
        if decomp:
            raise RuntimeError("this seed has no deductive decomposition")
        return solve(train, lib, budget, order)
    arg = split_set(decomp_set) if decomp else False
    if _HAS_SUB_LAM:
        return solve(train, lib, budget, order, decompose=arg,
                     sub_lam_depth=sub_lam_depth)
    if sub_lam_depth is not None:
        raise RuntimeError("this seed has no sub_lam_depth")
    return solve(train, lib, budget, order, decompose=arg)


__all__ = ["DECOMP_SETS", "DEFAULT_SPLITS", "ENGINE", "EvalError",
           "HAS_SPLIT_SETS", "Library", "SPLITS", "_seed", "prims", "run",
           "solve", "solve_with", "split_set"]
