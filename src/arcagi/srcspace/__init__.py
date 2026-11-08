"""srcspace: block JSON <-> Janet source, ``$ref`` folding, subtrees as blocks.

The solver never depends on this package's Janet side; ``janet_bridge`` only
syntax-checks text when the external ``janet`` binary exists.
"""

from .emit import to_janet
from .fold import fold_refs, node_count, unfold_refs
from .parse import from_janet
from .promote import promote
from .slot_prims import slot_primitives
from .slots import shared_slot_subtrees
from .subtree import shared_subtrees

__all__ = [
    "fold_refs",
    "from_janet",
    "node_count",
    "promote",
    "shared_slot_subtrees",
    "shared_subtrees",
    "slot_primitives",
    "to_janet",
    "unfold_refs",
]
