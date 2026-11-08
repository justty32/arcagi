"""Create or complete ``aos/blocks/<name>/`` from the Python block tables.

Run: ``uv run python -m arcagi.blocks.sync [--root aos/blocks]``. Existing
``status`` and account fields (``counter_uses``, unknown keys) are preserved;
only descriptive fields are refreshed.
"""

import argparse
import inspect
import os
from pathlib import Path
from typing import Any

from . import default_blocks_root, read_json, write_json

ENTRY_SCRIPT = """#!/bin/sh
# aos block entry: stdin {"grid": [[...]], "params": [...]} -> stdout grid JSON.
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
exec "$root/.venv/bin/python" -m arcagi.blocks.run "$(basename "$here")"
"""

# Terminal learners are not in PRIMITIVES; their parameters are fitted tables.
LEARNERS: dict[str, dict[str, Any]] = {
    "colormap": {
        "doc": "Terminal color table: replace each color by its learned target color.",
        "params": ["table"],
    },
    "object_colormap": {
        "doc": "Terminal object table: recolor whole objects by one learned attribute.",
        "params": ["table"],
    },
    "local_rule": {
        "doc": "Terminal neighborhood rule table over n4/n8 features.",
        "params": ["features", "rule"],
    },
}

_DESCRIPTIVE = ("name", "kind", "doc", "params")
_DEFAULTS: dict[str, Any] = {"cost": 1, "status": "live", "counter_uses": 0}


def primitive_specs() -> dict[str, dict[str, Any]]:
    """name -> {kind, doc, params} for every registered primitive and learner."""
    from arcagi.dsl.registry import ALL as PRIMITIVES  # python impls, not macros

    specs: dict[str, dict[str, Any]] = {}
    for name, primitive in PRIMITIVES.items():
        try:
            params = list(inspect.signature(primitive.apply).parameters)[1:]
        except (TypeError, ValueError):
            params = []
        doc_lines = (inspect.getdoc(primitive.apply) or "").splitlines()
        doc = doc_lines[0] if doc_lines else f"Grid primitive {name}."
        specs[name] = {"kind": "primitive", "doc": doc, "params": params}
    for name, spec in LEARNERS.items():
        specs[name] = {"kind": "learner", **spec}
    return specs


def write_block(folder: Path, fields: dict[str, Any], *, refresh: bool = True) -> None:
    """Write ``_metainfo.json`` (merging with existing) and ``_entry``."""
    path = folder / "_metainfo.json"
    existing = read_json(path, {})
    meta = dict(existing) if isinstance(existing, dict) else {}
    for key, value in fields.items():
        if refresh or key not in meta:
            if key in ("status", "counter_uses") and key in meta:
                continue
            meta[key] = value
    for key, value in _DEFAULTS.items():
        meta.setdefault(key, value)
    ordered = {k: meta[k] for k in (*_DESCRIPTIVE, *_DEFAULTS) if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    write_json(path, ordered)
    entry = folder / "_entry"
    if not entry.exists() or entry.read_text(encoding="utf-8") != ENTRY_SCRIPT:
        entry.write_text(ENTRY_SCRIPT, encoding="utf-8")
    os.chmod(entry, 0o755)


def sync(root: Path | None = None) -> list[str]:
    """Create/complete one folder per block; return the synced names."""
    root = Path(root) if root is not None else default_blocks_root()
    names = []
    for name, spec in primitive_specs().items():
        write_block(root / name, {"name": name, **spec})
        names.append(name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    names = sync(args.root)
    print(f"synced {len(names)} blocks into {args.root or default_blocks_root()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
