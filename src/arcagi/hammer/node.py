"""Node folders: ``_metainfo.json`` entry resolution and in-process calls.

A node's ``entry`` is ``module:function``; the function maps a list of JSON
rows to a list of JSON rows (``run(rows) -> rows``). ``exec.py`` calls the
same function over stdin / stdout JSONL, so both paths are bit-identical.
"""

import importlib
from pathlib import Path

from . import formats as fm


def resolve(entry: str):
    mod, fn = entry.split(":", 1)
    return getattr(importlib.import_module(mod), fn)


def node_entry(node: str | Path) -> str:
    """``node``: a node folder (with _metainfo.json) or an entry string."""
    p = Path(node)
    if (p / "_metainfo.json").exists():
        return fm.load_metainfo(p)["entry"]
    if ":" in str(node):
        return str(node)
    return fm.node_meta(str(node))["entry"]


def run(node: str | Path, rows: list[dict]) -> list[dict]:
    return resolve(node_entry(node))(rows)
