"""Read-only think-1 scorecard loading and node-level health summaries."""

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

from arcagi.hammer.formats import NODES

from . import boundary
from .credit import OP_NODE

REPO = Path(__file__).resolve().parents[3]
BAD_VERDICTS = frozenset(("retire-candidate", "dormant-stale"))


def load_script(name: str) -> ModuleType:
    """Load a local reference script without main(), writes or bytecode caches."""
    if name not in ("think1_meter", "think1_audit"):
        raise ValueError(f"unsupported reference script: {name}")
    boundary.check_stop()
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def summarize(root: Path, epoch: int, epochs: list[int]) -> tuple[dict, list[dict]]:
    """Aggregate the original scorecard; retirement remains a suggestion only."""
    audit = load_script("think1_audit")
    rows = audit.scorecard(root, epoch, epochs)
    nodes = {}
    suggestions = []
    for name in NODES:
        boundary.check_stop()
        ops = [row for row in rows if OP_NODE.get(row["kind"]) == name]
        verdicts = dict(sorted(Counter(row["verdict"] for row in ops).items()))
        nodes[name] = {
            "ok": not BAD_VERDICTS.intersection(verdicts),
            "verdicts": verdicts,
            "n_ops": len(ops),
        }
        if name not in OP_NODE.values():
            nodes[name]["note"] = "no ops"
        for row in ops:
            if row["verdict"] in BAD_VERDICTS:
                suggestions.append(
                    {
                        "schema": "t2-retire-suggest/1",
                        "epoch": epoch,
                        "node": f"nodes/{name}",
                        "op_id": row["id"],
                        "verdict": row["verdict"],
                    }
                )
    return {"schema": "t2-health/1", "epoch": epoch, "nodes": nodes}, suggestions


def check(
    actual: dict,
    suggestions: list[dict],
    expected: dict,
    expected_suggestions: list[dict],
) -> dict:
    """Require all seven nodes and the original per-op scorecard counts."""
    errors = []
    if actual != expected:
        errors.append(
            "health nodes/verdicts/ok/counts differ from the reference scorecard"
        )
    if suggestions != expected_suggestions:
        errors.append("retire suggestions differ from the reference scorecard")
    counts = {name: node["n_ops"] for name, node in expected["nodes"].items()}
    for name, node in actual["nodes"].items():
        if sum(node["verdicts"].values()) != node["n_ops"]:
            errors.append(f"{name}: verdict counts do not sum to n_ops")
    return {
        "pass": not errors,
        "nodes": len(actual["nodes"]),
        "n_ops": sum(counts.values()),
        "ops_by_node": counts,
        "errors": errors,
    }
