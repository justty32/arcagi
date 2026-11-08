"""The full primitive registry used by programs and search."""

from .primitives import BASE, MARK, Primitive
from .primitives_more import MORE

PRIMITIVES: dict[str, Primitive] = {**BASE, **MORE}

__all__ = ["MARK", "PRIMITIVES", "Primitive"]
