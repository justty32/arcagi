"""Rebuild a fresh hammer tree from a genome and optional state sidecar."""

import hashlib
import re
from pathlib import Path

from arcagi.hammer.formats import new_op, read_json, write_json, write_jsonl

from . import boundary
from .refs import expand


def import_tree(
    tree_json: str | Path,
    dest: str | Path,
    state_json: str | Path | None = None,
    files_dir: str | Path | None = None,
) -> Path:
    """Import into an absent or empty directory without overwriting a tree."""
    boundary.check_stop()
    tree_json, dest = Path(tree_json), Path(dest).resolve()
    document = read_json(tree_json)
    if document["schema"] != "aos-tree/1":
        raise ValueError("unsupported tree schema")
    if document["boundary_profile"] != boundary.PROFILE:
        raise ValueError("unsupported boundary profile")
    tree = expand(document["tree"], document["defs"])
    files_dir = Path(files_dir) if files_dir is not None else tree_json.parent / "files"
    state = {}
    if state_json is not None:
        sidecar = read_json(Path(state_json))
        if sidecar["schema"] != "aos-tree-state/1":
            raise ValueError("unsupported state schema")
        state = sidecar["ops"]
    # Validate all file blobs before making any destination writes.
    entries = []

    def collect(value: object, parts: tuple[str, ...] = ()) -> None:
        relative = "/".join(parts)
        kind = boundary.file_kind(relative)
        if kind is not None:
            path = boundary.safe_path(dest, relative)
            if kind == "file":
                if not isinstance(value, dict) or value.get("$file") != relative:
                    raise ValueError(f"invalid file stub: {relative}")
                sha = value["sha1"]
                if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
                    raise ValueError(f"invalid file sha1: {relative}")
                data = (files_dir / sha).read_bytes()
                if hashlib.sha1(data).hexdigest() != sha or len(data) != value["bytes"]:
                    raise ValueError(f"file sha1/bytes mismatch: {relative}")
                if value["mode"] not in ("755", "644"):
                    raise ValueError(f"invalid file mode: {relative}")
                entries.append((path, kind, (data, int(value["mode"], 8))))
            else:
                entries.append((path, kind, value))
            return
        if not isinstance(value, dict):
            raise ValueError(f"unexpected tree entry: {relative}")
        for name, item in value.items():
            if not name or "/" in name or name in (".", ".."):
                raise ValueError(f"invalid tree path component: {name!r}")
            collect(item, (*parts, name))

    collect(tree)
    boundary.empty_directory(dest)
    for path, kind, value in entries:
        boundary.check_stop()
        if kind == "json":
            write_json(path, value)
        elif kind == "file":
            data, mode = value
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(mode)
        else:
            ops = []
            for definition in value:
                defaults = new_op(
                    definition["id"],
                    definition["kind"],
                    definition["payload"],
                    definition["by"],
                    definition["born"]["epoch"],
                )
                saved = state.get(definition["id"], {})
                op = {
                    **definition,
                    **{k: saved.get(k, defaults[k]) for k in boundary.OP_STATE_FIELDS},
                }
                ops.append(op)
                if op["kind"] in boundary.PROJECTION_KINDS:
                    projection = boundary.safe_path(
                        dest, f"ops/{op['id']}/_metainfo.json"
                    )
                    write_json(
                        projection, {k: op[k] for k in boundary.PROJECTION_FIELDS}
                    )
            write_jsonl(path, ops)
    # check_root requires an existing ledger; runtime history is not a genome.
    write_jsonl(dest / "ledger.jsonl", [])
    return dest
