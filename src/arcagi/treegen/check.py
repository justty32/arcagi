"""Fail-closed structural, provenance, range and imported-root checks."""

import tempfile
from pathlib import Path

from arcagi.hammer.check import check_root

from . import boundary, bounds, genome, guards, refs
from .import_ import import_tree


def references(doc: dict) -> list[str]:
    """Validate all refs and reject definitions unreachable from the tree."""
    used = set()

    def visit(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if "$ref" in value:
                key = value["$ref"].rsplit("/", 1)[-1]
                if key not in used and key in doc["defs"]:
                    used.add(key)
                    visit(doc["defs"][key])
            else:
                for item in value.values():
                    visit(item)

    try:
        refs.expand(doc["tree"], doc["defs"])
        visit(doc["tree"])
    except (ValueError, TypeError, AttributeError) as exc:
        return [f"dangling_ref:{exc}"]
    return [f"unused_def:{key}" for key in sorted(doc["defs"].keys() - used)]


def check(
    doc: dict | str | Path,
    parent_doc: dict | str | Path | list,
    *,
    files_dir: Path | None = None,
    forbid_root: Path | None = None,
) -> dict:
    """Check against the union of parents; inherited taint is diagnostic only."""
    boundary.check_stop()
    errors, inherited = [], []
    try:
        source = Path(doc) if isinstance(doc, (str, Path)) else None
        document = genome.load(doc)
        parent_inputs = parent_doc if isinstance(parent_doc, list) else [parent_doc]
        if not parent_inputs:
            raise ValueError("check requires at least one parent")
        parents = [genome.expanded(p) for p in parent_inputs]
        if document["schema"] != "aos-tree/1":
            errors.append("schema:expected aos-tree/1")
        if document["genome_sha"] != refs.genome_sha(
            document["defs"], document["tree"]
        ):
            errors.append("genome_sha:mismatch")
        errors.extend(references(document))
        if any(e.startswith("dangling_ref") for e in errors):
            return {"ok": False, "errors": errors, "inherited_taint": []}
        tree = genome.expanded(document)
        errors.extend(genome.immutable_errors(tree, parents))
        errors.extend(bounds.validate(tree))
        ops = tree["ops.jsonl"]
        if not any(o["kind"] == "comb" and o["status"] == "live" for o in ops):
            errors.append("missing_live_comb")
        if not any(o["kind"] == "gate" and o["status"] == "live" for o in ops):
            errors.append("missing_live_gate")
        base = {o["id"] for p in parents for o in p["ops.jsonl"]}
        genome.SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ga-check-", dir=genome.SCRATCH) as tmp:
            tmp = Path(tmp)
            # Keep the claimed hash on disk: validation must not repair forgeries.
            from arcagi.hammer.formats import write_json

            write_json(tmp / "tree.json", document)
            parent_path = next(
                (Path(p) for p in parent_inputs if isinstance(p, (str, Path))),
                genome.PARENT,
            )
            blobs = files_dir or (source or parent_path).parent / "files"
            root = import_tree(tmp / "tree.json", tmp / "root", files_dir=blobs)
            errors.extend(f"check_root:{error}" for error in check_root(root))
            leak = guards.leak(
                root, base_ops=base, forbid_root=forbid_root or guards.LIVE_ROOT
            )
            inherited = leak["inherited"]
            errors.extend(f"leak:{row['op_id']}:{row['pool']}" for row in leak["new"])
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OverflowError,
    ) as exc:
        errors.append(f"invalid:{exc}")
    return {
        "ok": not errors,
        "errors": sorted(set(errors)),
        "inherited_taint": inherited,
    }


def ga_check(
    doc: str | Path,
    parent: str | Path | list,
    *,
    fit: str | Path | None = None,
    quick_dir: Path | None = None,
) -> dict:
    """CLI acceptance optionally verifies a fitness record against quick.json."""
    result = check(doc, parent)
    if fit is not None:
        from .fitness import verify_fit

        result["errors"].extend(
            verify_fit(Path(fit), genome.load(doc)["genome_sha"], quick_dir)
        )
        result["ok"] = not result["errors"]
    return result
