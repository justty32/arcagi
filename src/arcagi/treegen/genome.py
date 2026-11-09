"""Shared block-4 genome representation and immutable-field contracts."""

import copy
import shutil
from pathlib import Path

from arcagi.hammer.formats import read_json, write_json

from . import boundary, refs

EVO = Path("/home/lorkhan/code/playground-arc1/ws/evo")
SCRATCH = Path(
    "/tmp/claude-1000/-home-lorkhan-repo-arcagi/"
    "b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t2f"
)
PARENT = EVO / "rt/hammer/tree.json"
REPORTS = Path(__file__).resolve().parents[3] / "reports/think2-1109"
IMMUTABLE_OP = ("id", "kind", "born", "by", "sig", "parent_route")


def load(doc: dict | str | Path) -> dict:
    """Accept in-memory documents as well as CLI paths."""
    return read_json(doc) if isinstance(doc, (str, Path)) else doc


def expanded(doc: dict | str | Path) -> dict:
    """Expand via the block-1 implementation, returning independent containers."""
    doc = load(doc)
    return refs.expand(doc["tree"], doc["defs"])


def pack(doc: dict, tree: dict) -> dict:
    """Rebuild definitions after editing an expanded tree."""
    defs, tree = refs.deduplicate(tree)
    return {
        **copy.deepcopy(doc),
        "defs": defs,
        "tree": tree,
        "genome_sha": refs.genome_sha(defs, tree),
    }


def destination(path: str | Path) -> Path:
    """Limit new population and scratch artifacts to authorized roots."""
    boundary.check_stop()
    path = Path(path).resolve()
    if not any(
        path != root.resolve() and path.is_relative_to(root.resolve())
        for root in (EVO, SCRATCH)
    ):
        raise ValueError("GA destination must be below evo or t2f scratch")
    return path


def write(path: Path, doc: dict, files: Path | None = None) -> dict:
    """Rehash every genome write; copy immutable file blobs when supplied."""
    boundary.check_stop()
    saved = copy.deepcopy(doc)
    saved["genome_sha"] = refs.genome_sha(saved["defs"], saved["tree"])
    if files is not None and files.is_dir():
        target = path.parent / "files"
        boundary.safe_path(path.parent, "files")
        shutil.copytree(files, target, dirs_exist_ok=True)
    boundary.safe_path(path.parent, path.name)
    write_json(path, saved)
    return saved


def _different(a: object, b: object, prefix: str) -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        return [
            error
            for key in sorted(a.keys() | b.keys())
            for error in (
                [f"immutable:{prefix}/{key}"]
                if key not in a or key not in b
                else _different(a[key], b[key], f"{prefix}/{key}")
            )
        ]
    return [] if refs.canonical(a) == refs.canonical(b) else [f"immutable:{prefix}"]


def _numeric_mask(item: object) -> object:
    if type(item) in (int, float):
        return "<numeric>"
    if isinstance(item, dict):
        return {key: _numeric_mask(value) for key, value in item.items()}
    return item


def immutable_errors(tree: dict, parents: list[dict]) -> list[str]:
    """Allow only the four mutation surfaces and op deletion/recombination."""
    errors = []
    parent_ops = [{op["id"]: op for op in p["ops.jsonl"]} for p in parents]
    for op in tree["ops.jsonl"]:
        originals = [ops[op["id"]] for ops in parent_ops if op["id"] in ops]
        if not originals:
            errors.append(f"alien_op:{op['id']}")
            continue
        for original in originals:
            for field in IMMUTABLE_OP:
                if _different(op.get(field), original.get(field), field):
                    errors.append(f"immutable:{op['id']}.{field}")
            a, b = copy.deepcopy(op), copy.deepcopy(original)
            for value in (a, b):
                for field in IMMUTABLE_OP:
                    value.pop(field, None)
                value.pop("status", None)
                if original["kind"] == "gate":
                    value["payload"]["params"] = _numeric_mask(
                        value["payload"]["params"]
                    )
                if original["kind"] == "route":
                    value["payload"].pop("priority", None)
            errors.extend(_different(a, b, op["id"]))
    # All parents must share the locked skeleton. Judge numeric values may vary,
    # while judge booleans and its shape remain immutable.
    for parent in parents:
        a, b = copy.deepcopy(tree), copy.deepcopy(parent)
        for value in (a, b):
            value.pop("ops.jsonl", None)

            value["frozen.json"]["judge"] = _numeric_mask(value["frozen.json"]["judge"])
            for node in value["nodes"].values():
                node["_metainfo.json"].pop("weight", None)
        errors.extend(_different(a, b, "tree"))
        for original in parent["ops.jsonl"]:
            if original["kind"] == "gate" and not any(
                op["id"] == original["id"] and op["status"] == "live"
                for op in tree["ops.jsonl"]
            ):
                errors.append(f"gate_not_live:{original['id']}")
        if any(op["kind"] == "decomp" for op in parent["ops.jsonl"]) and not any(
            op["kind"] == "decomp" for op in tree["ops.jsonl"]
        ):
            errors.append("missing_decomp")
    return sorted(set(errors))
