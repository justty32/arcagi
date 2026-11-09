"""Export the hammer-v1 genome and its runtime state sidecar."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from arcagi.hammer.formats import write_json

from . import boundary
from .refs import count_refs, deduplicate, genome_sha


def export_tree(root: str | Path, out_dir: str | Path, dedup: bool = True) -> dict:
    """Write tree.json, state.json and content-addressed file blobs."""
    return _export_tree(root, out_dir, dedup)


def _export_tree(
    root: str | Path,
    out_dir: str | Path,
    dedup: bool = True,
    *,
    tree_name: str = "tree.json",
    state_name: str | None = "state.json",
) -> dict:
    """Share the exporter with CLI variants without overwriting earlier exports."""
    boundary.check_stop()
    root, out_dir = Path(root).resolve(), Path(out_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"tree root is not a directory: {root}")
    if out_dir.is_relative_to(root):
        raise ValueError("export directory must not be inside the source tree")
    paths, skipped = boundary.inventory(root)
    tree, state, blobs = {}, {}, {}
    total_bytes = 0
    for relative in paths:
        boundary.check_stop()
        path = root / relative
        data = path.read_bytes()
        total_bytes += len(data)
        kind = boundary.file_kind(relative)
        if kind == "file":
            sha = hashlib.sha1(data).hexdigest()
            blobs[sha] = data
            value = {
                "$file": relative,
                "sha1": sha,
                "mode": "755" if path.stat().st_mode & 0o111 else "644",
                "bytes": len(data),
            }
        elif kind == "ops":
            value = []
            for line_number, line in enumerate(data.decode().splitlines(), 1):
                if not line.strip():
                    continue
                op = json.loads(line)
                unknown = (
                    set(op)
                    - set(boundary.OP_DEFINITION_FIELDS)
                    - set(boundary.OP_STATE_FIELDS)
                )
                if unknown:
                    raise ValueError(
                        f"ops.jsonl:{line_number}: unknown fields {sorted(unknown)}"
                    )
                if op["id"] in state:
                    raise ValueError(f"duplicate op id: {op['id']}")
                value.append({k: op[k] for k in boundary.OP_DEFINITION_FIELDS})
                state[op["id"]] = {
                    k: op[k] for k in boundary.OP_STATE_FIELDS if k in op
                }
        else:
            value = json.loads(data)
        parent = tree
        parts = Path(relative).parts
        for part in parts[:-1]:
            parent = parent.setdefault(part, {})
        parent[parts[-1]] = value
    defs, tree = deduplicate(tree) if dedup else ({}, tree)
    document = {
        "schema": "aos-tree/1",
        "name": root.name,
        "boundary_profile": boundary.PROFILE,
        "exported_from": str(root),
        "at": datetime.now().astimezone().isoformat(),
        "dedup": dedup,
        "genome_sha": genome_sha(defs, tree),
        "defs": defs,
        "tree": tree,
        "stats": {
            "files": len(paths),
            "bytes": total_bytes,
            "refs": count_refs({"defs": defs, "tree": tree}),
            "defs": len(defs),
            "skipped": skipped,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "files").mkdir(exist_ok=True)
    for sha, data in blobs.items():
        boundary.check_stop()
        (out_dir / "files" / sha).write_bytes(data)
    boundary.check_stop()
    write_json(boundary.safe_path(out_dir, tree_name), document)
    if state_name is not None:
        write_json(
            boundary.safe_path(out_dir, state_name),
            {"schema": "aos-tree-state/1", "ops": state},
        )
    return document
