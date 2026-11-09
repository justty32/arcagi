"""Guided and uniform mutations on expanded, immutable-sealed genomes."""

import random
from collections import defaultdict
from pathlib import Path

from arcagi.hammer.formats import read_json, read_jsonl

from . import boundary, bounds, genome
from .effect import effective_arms

OPERATORS = ("M1", "M2", "M3", "M5")
PROBABILITIES = (0.4, 0.25, 0.25, 0.1)


def load_guide(directory: str | Path, parent: dict) -> dict:
    """Read retirement hints and aggregate only layer-2 op credit."""
    directory = Path(directory)
    for name in ("retire_suggest.jsonl", "credit.jsonl"):
        if not (directory / name).is_file():
            raise ValueError(f"missing mutation guide: {directory / name}")
    totals = defaultdict(float)
    for row in read_jsonl(directory / "credit.jsonl"):
        if row["layer"] == 2 and row["to"].startswith("ops/"):
            totals[row["to"][4:]] += row["amount"]
    live = [
        op["id"]
        for op in genome.expanded(parent)["ops.jsonl"]
        if op["status"] == "live"
    ]
    ranked = sorted(live, key=lambda key: (-totals[key], key))
    return {
        "retire": {
            row["op_id"]: row["verdict"]
            for row in read_jsonl(directory / "retire_suggest.jsonl")
        },
        "high": ranked[:3],
        "low": min(live, key=lambda key: (totals[key], key)) if live else None,
    }


def _safe_removal(op: dict, ops: list[dict]) -> bool:
    if op["kind"] == "gate":
        return False
    if op["kind"] == "decomp" and sum(o["kind"] == "decomp" for o in ops) <= 1:
        return False
    return not (
        op["kind"] == "comb"
        and op["status"] == "live"
        and sum(o["kind"] == "comb" and o["status"] == "live" for o in ops) <= 1
    )


def candidates(tree: dict) -> dict[str, list]:
    """Exclude structurally invalid mutations and ineffective route edits."""
    targets = bounds.targets(tree)
    ops = tree["ops.jsonl"]
    arms = effective_arms(ops)

    def changes_route(op: dict, operator: str) -> bool:
        if op["kind"] != "route":
            return True
        changed = [o for o in ops if o["id"] != op["id"]]
        if operator == "M2":
            status = "dormant" if op["status"] == "live" else "live"
            changed.append({**op, "status": status})
        return effective_arms(changed) != arms

    return {
        "M1": [t for t in targets if t[4] != "weight"],
        "M2": [
            o
            for o in ops
            if o["kind"] != "gate"
            and o["status"] in ("live", "dormant")
            and (
                o["status"] == "dormant"
                or _safe_removal(o, ops)
                or o["kind"] == "decomp"
            )
            and changes_route(o, "M2")
        ],
        "M3": [o for o in ops if _safe_removal(o, ops) and changes_route(o, "M3")],
        "M5": [t for t in targets if t[4] == "weight"],
    }


def target_weight(operator: str, target: object, guide: dict) -> float:
    """Apply D18 multipliers to the indicated operation and status only."""
    if operator in ("M1", "M5"):
        return 2.0 if target[3] in guide.get("high", []) else 1.0
    op = target
    verdict = guide.get("retire", {}).get(op["id"])
    if operator == "M3" and verdict == "dormant-stale":
        return 4.0
    if operator == "M2":
        if op["status"] == "dormant" and verdict == "dormant-active":
            return 2.0
        if op["status"] == "live" and op["id"] == guide.get("low"):
            return 2.0
    return 1.0


def mutate(tree_doc: dict, rng: random.Random, guide: dict) -> tuple[dict, dict]:
    """Apply one M1/M2/M3/M5 mutation without changing the caller's document."""
    boundary.check_stop()
    tree = genome.expanded(tree_doc)
    options = candidates(tree)
    available = [op for op in OPERATORS if options[op]]
    if not available:
        raise ValueError("no available mutation")
    arm = "guided" if rng.random() < 0.8 else "uniform"
    operator = rng.choices(
        available,
        weights=[
            PROBABILITIES[OPERATORS.index(op)] if arm == "guided" else 1
            for op in available
        ],
    )[0]
    choices = options[operator]
    target = rng.choices(
        choices,
        weights=[
            target_weight(operator, t, guide) if arm == "guided" else 1 for t in choices
        ],
    )[0]
    if operator in ("M1", "M5"):
        path, container, key, _, name = target
        before = container[key]
        rule = read_json(bounds.BOUNDS)["limits"][name]
        after = (
            before + rng.choice((-2, -1, 1, 2))
            if type(before) is int
            else before * rng.uniform(0.7, 1.3)
        )
        after = max(rule["min"], min(rule["max"], after))
        container[key] = after
    elif operator == "M2":
        path = f"ops/{target['id']}/status"
        before = target["status"]
        after = "dormant" if before == "live" else "live"
        target["status"] = after
    else:
        path, before, after = f"ops/{target['id']}", target, None
        tree["ops.jsonl"].remove(target)
    assert not genome.immutable_errors(tree, [genome.expanded(tree_doc)])
    return genome.pack(tree_doc, tree), {
        "parents": [tree_doc["genome_sha"]],
        "arm": arm,
        "redraws": 0,
        "ops": [{"op": operator, "path": path, "from": before, "to": after}],
    }
