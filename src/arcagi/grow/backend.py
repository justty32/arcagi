"""The seed engine used by the learning loop (read-only calls into arcagi.seed)."""

from arcagi.seed import prims as _seed
from arcagi.seed.enum import solve
from arcagi.seed.interp import EvalError, run
from arcagi.seed.library import Library

ENGINE = "seed"

__all__ = ["ENGINE", "EvalError", "Library", "_seed", "run", "solve"]
