"""The seed engine used by the learning loop (read-only calls into arcagi.seed)."""

import inspect

from arcagi.seed import prims
from arcagi.seed import prims as _seed
from arcagi.seed.enum import solve
from arcagi.seed.interp import EvalError, run
from arcagi.seed.library import Library

ENGINE = "seed"
_HAS_DECOMP = "decompose" in inspect.signature(solve).parameters


def solve_with(train, lib, budget, order, decomp: bool):
    """``seed.enum.solve`` with decomposition explicitly on or off."""
    if _HAS_DECOMP:
        return solve(train, lib, budget, order, decompose=decomp)
    if decomp:
        raise RuntimeError("this seed has no deductive decomposition")
    return solve(train, lib, budget, order)


__all__ = ["ENGINE", "EvalError", "Library", "_seed", "prims", "run", "solve",
           "solve_with"]
