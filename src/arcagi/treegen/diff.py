"""Compare expanded tree contents using JSON pointers."""

from pathlib import Path

from arcagi.hammer.formats import read_json

from .refs import expand


def diff_trees(
    a: str | Path,
    b: str | Path,
    ignore_op_order: bool = False,
) -> dict:
    """Return content differences, ignoring export metadata and ref layout."""
    document_a, document_b = read_json(Path(a)), read_json(Path(b))
    left = expand(document_a["tree"], document_a["defs"])
    right = expand(document_b["tree"], document_b["defs"])
    if ignore_op_order:
        for tree in (left, right):
            if "ops.jsonl" in tree:
                tree["ops.jsonl"] = sorted(tree["ops.jsonl"], key=lambda op: op["id"])
    diffs = []
    missing = object()

    def compare(x: object, y: object, path: str) -> None:
        if isinstance(x, dict) and isinstance(y, dict):
            for key in sorted(x.keys() | y.keys()):
                token = key.replace("~", "~0").replace("/", "~1")
                compare(x.get(key, missing), y.get(key, missing), f"{path}/{token}")
        elif isinstance(x, list) and isinstance(y, list):
            for i in range(max(len(x), len(y))):
                compare(
                    x[i] if i < len(x) else missing,
                    y[i] if i < len(y) else missing,
                    f"{path}/{i}",
                )
        elif type(x) is not type(y) or x != y:
            diffs.append(
                {
                    "path": path,
                    "a": None if x is missing else x,
                    "b": None if y is missing else y,
                }
            )

    compare(left, right, "/tree")
    return {"a": str(a), "b": str(b), "n_diff": len(diffs), "diffs": diffs}
