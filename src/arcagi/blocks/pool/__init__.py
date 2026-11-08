"""Node-pool style accounts for blocks (one full eval report = one epoch).

``ledger`` settles epochs, ``budget`` turns shares into generator candidate
counts, ``__main__`` is the CLI: ``uv run python -m arcagi.blocks.pool --report
R.json --epoch N --split S``.
"""

from .budget import allocate
from .ledger import (
    DEFAULT_CONFIG,
    EpochError,
    run_epoch,
    selected_steps,
    settle,
)

__all__ = [
    "DEFAULT_CONFIG",
    "EpochError",
    "allocate",
    "run_epoch",
    "selected_steps",
    "settle",
]
