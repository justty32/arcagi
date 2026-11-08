"""Read block folders (``aos/blocks/*/_metainfo.json``) into a ``Catalog``.

A missing root yields an empty catalog, so the solver behaves exactly as in
round 1. Unknown metainfo keys are ignored; a broken folder is skipped.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import default_blocks_root

STATUSES = ("live", "covered", "retired")
# Same shape as arcagi.dsl.program.Program; not imported so that
# arcagi.dsl.registry can import this module without a cycle.
type Program = tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class Block:
    name: str
    kind: str
    status: str
    cost: float
    path: Path
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Catalog:
    root: Path | None
    blocks: dict[str, Block] = field(default_factory=dict)

    def status(self, name: str) -> str:
        """Status of ``name``; blocks without a folder count as ``live``."""
        block = self.blocks.get(name)
        return block.status if block else "live"

    def cost(self, name: str) -> float:
        block = self.blocks.get(name)
        return block.cost if block else 1.0

    @property
    def retired(self) -> frozenset[str]:
        return frozenset(n for n, b in self.blocks.items() if b.status == "retired")

    def macros(self, *, include_covered: bool = False) -> dict[str, Program]:
        """``kind=macro`` programs; retired always and covered by default excluded."""
        allowed = {"live", "covered"} if include_covered else {"live"}
        found: dict[str, Program] = {}
        for name, block in sorted(self.blocks.items()):
            if block.kind != "macro" or block.status not in allowed:
                continue
            program = load_macro_program(block.path)
            if program:
                found[name] = program
        return found

    def predicates(self) -> dict[str, list]:
        """Live ``kind=pred`` blocks: name -> predicate AST from ``_rule.json``."""
        from arcagi.dsl.predicates import read_rule

        found: dict[str, list] = {}
        for name, block in sorted(self.blocks.items()):
            if block.kind == "pred" and block.status == "live":
                body = read_rule(block.path)
                if body is not None:
                    found[name] = body
        return found

    def rules(self, kind: str) -> dict[str, Any]:
        """Live blocks of ``kind`` (e.g. formula, extract): name -> ``_rule.json``."""
        found: dict[str, Any] = {}
        for name, block in sorted(self.blocks.items()):
            if block.kind != kind or block.status != "live":
                continue
            try:
                found[name] = json.loads((block.path / "_rule.json").read_text())
            except (OSError, ValueError):
                continue
        return found


def load_macro_program(folder: Path) -> Program | None:
    try:
        steps = json.loads((folder / "program.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(steps, list) or not all(
        isinstance(s, list) and s and isinstance(s[0], str) for s in steps
    ):
        return None
    return tuple(tuple(step) for step in steps)


def _read_block(folder: Path) -> Block | None:
    try:
        meta = json.loads((folder / "_metainfo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    name = meta.get("name") or folder.name
    status = meta.get("status", "live")
    cost = meta.get("cost", 1)
    return Block(
        name=str(name),
        kind=str(meta.get("kind", "primitive")),
        status=status if status in STATUSES else "live",
        cost=float(cost) if isinstance(cost, (int, float)) else 1.0,
        path=folder,
        meta=meta,
    )


def load_catalog(root: Path | None = None) -> Catalog:
    """Load every ``<root>/*/_metainfo.json``; default root per package docs."""
    root = Path(root) if root is not None else default_blocks_root()
    if not root.is_dir():
        return Catalog(root=None)
    blocks = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        block = _read_block(folder)
        if block is not None:
            blocks[block.name] = block
    return Catalog(root=root, blocks=blocks)


__all__ = ["Block", "Catalog", "load_catalog", "load_macro_program"]
