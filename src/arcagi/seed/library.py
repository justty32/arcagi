"""Library of learned blocks, stored as JSON (``aos/seedlib/blocks.json``).

File format: a JSON list of dicts ``{name, body, sig, src_tasks, saving, uses}``.
``body`` is a program in JSON form (lists instead of tuples) that may contain
hole leaves ``["$h0"]`` / ``["$h1"]``. ``sig`` is a type string (see
``types.parse``): with k > 0 holes it is a function type of k arguments (the
hole types) returning the block's type; with no holes it is the block's own
type, which may be a function type (the block then acts like a lambda).

The enumerator uses blocks whose body has no free ``$0``/``$1`` (outside its own
lambdas); others are still runnable through the interpreter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .interp import HOLES, Program, from_json, to_json
from .types import FnT, Type, parse, show


@dataclass(frozen=True)
class Block:
    name: str
    body: Program
    sig: Type
    src_tasks: tuple[str, ...] = ()
    saving: float = 0.0
    uses: int = 0

    @property
    def holes(self) -> int:
        return hole_count(self.body)

    @property
    def hole_types(self) -> tuple[Type, ...]:
        if self.holes == 0:
            return ()
        assert isinstance(self.sig, FnT)
        return self.sig.args

    @property
    def ret(self) -> Type:
        if self.holes == 0:
            return self.sig
        assert isinstance(self.sig, FnT)
        return self.sig.ret

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "body": to_json(self.body),
            "sig": show(self.sig),
            "src_tasks": list(self.src_tasks),
            "saving": self.saving,
            "uses": self.uses,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Block:
        b = cls(
            name=str(d["name"]),
            body=from_json(d["body"]),
            sig=parse(d["sig"]) if isinstance(d["sig"], str) else d["sig"],
            src_tasks=tuple(d.get("src_tasks", ())),
            saving=float(d.get("saving", 0.0)),
            uses=int(d.get("uses", 0)),
        )
        k = b.holes
        if k and not (isinstance(b.sig, FnT) and len(b.sig.args) == k):
            raise ValueError(f"block {b.name}: sig must take {k} hole arguments")
        return b


def hole_count(prog: Program) -> int:
    """1 + highest hole index used in ``prog`` (0 if no holes)."""
    if isinstance(prog, int):
        return 0
    if len(prog) == 1:
        return HOLES.index(prog[0]) + 1 if prog[0] in HOLES else 0
    kids = prog[2:] if prog[0] in ("lam", "blk") else prog[1:]
    return max((hole_count(k) for k in kids), default=0)


def free_vars(prog: Program, depth: int = 0) -> bool:
    """True if ``prog`` references $0/$1 not bound by its own lambdas."""
    if isinstance(prog, int):
        return False
    if len(prog) == 1:
        return prog[0] in ("$0", "$1") and depth == 0
    if prog[0] == "lam":
        return free_vars(prog[2], depth + 1)
    kids = prog[2:] if prog[0] == "blk" else prog[1:]
    return any(free_vars(k, depth) for k in kids)


@dataclass
class Library:
    blocks: list[Block] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.by_name: dict[str, Block] = {}
        for b in self.blocks:
            if b.name in self.by_name:
                raise ValueError(f"duplicate block name {b.name!r}")
            self.by_name[b.name] = b

    def __len__(self) -> int:
        return len(self.blocks)

    def add(self, block: Block) -> None:
        if block.name in self.by_name:
            raise ValueError(f"duplicate block name {block.name!r}")
        self.blocks.append(block)
        self.by_name[block.name] = block

    @classmethod
    def load(cls, path: str | Path) -> Library:
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected a JSON list of blocks")
        return cls([Block.from_dict(d) for d in data])

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps([b.to_dict() for b in self.blocks], indent=1)
        path.write_text(text + "\n", encoding="utf-8")
