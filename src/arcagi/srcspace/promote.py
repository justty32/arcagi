"""Write a shared subtree as a macro block ``aos/blocks/m_sub_<hash>/``.

Same folder format as ``blocks.library`` macros (``kind=macro``,
``program.json``, ``_entry``), so the catalog, registry and node-pool accounts
pick it up unchanged. Runs equal to an existing macro inside the subtree are
written as ``{"$ref": "../m_x/program.json"}`` steps (aos N-45).
"""

import hashlib
import json
from pathlib import Path

from arcagi.blocks import default_blocks_root, read_json, write_json
from arcagi.blocks.sync import write_block

from .fold import canonical, fold_refs
from .subtree import Fragment, Subtree

PREFIX = "m_sub_"


def thaw(value: object) -> object:
    """Undo ``subtree._freeze``: tuples -> lists, frozen dicts -> dicts."""
    if isinstance(value, tuple):
        if len(value) == 2 and value[0] == "__dict__":
            return {k: thaw(v) for k, v in value[1]}  # type: ignore[union-attr]
        return [thaw(v) for v in value]
    return value


def subtree_name(steps: Fragment) -> str:
    digest = hashlib.sha1(canonical(thaw(steps)).encode()).hexdigest()[:8]
    return PREFIX + digest


def subtree_program(steps: Fragment, macros: dict[str, list] | None = None) -> list:
    """JSON steps, existing macro runs folded into ``$ref``."""
    return fold_refs(thaw(steps), macros or {})  # type: ignore[arg-type]


def promote(
    subtree: Subtree,
    name: str | None = None,
    *,
    root: Path | None = None,
    macros: dict[str, list] | None = None,
    sources: list[str] | None = None,
) -> Path:
    """Write the block folder and return it; a retired block stays retired."""
    root = Path(root) if root is not None else default_blocks_root()
    name = name or subtree_name(subtree.steps)
    folder = root / name
    program = subtree_program(subtree.steps, macros)
    old = read_json(folder / "_metainfo.json", {}) or {}
    status = "retired" if old.get("status") == "retired" else subtree.status  # type: ignore[union-attr]
    doc = "Subtree macro: " + " -> ".join(json.dumps(s) for s in program)
    write_block(
        folder,
        {
            "name": name,
            "kind": "macro",
            "doc": doc,
            "params": [],
            "source_tasks": list(subtree.tasks),
            "source_traces": sources or [],
            "origin": "srcspace.subtree",
        },
    )
    meta = read_json(folder / "_metainfo.json", {})
    meta["status"] = status  # type: ignore[index]
    write_json(folder / "_metainfo.json", meta)
    write_json(folder / "program.json", program)
    return folder
