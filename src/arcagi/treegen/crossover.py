"""X1 op-subset and X3 judge-block crossover after expanding references."""

import copy
import random

from . import boundary, genome


def cross(
    a_doc: dict, b_doc: dict, rng: random.Random, *, operator: str | None = None
) -> tuple[dict, dict]:
    """Recombine two mutations, preserving op provenance and list order."""
    boundary.check_stop()
    a, b = genome.expanded(a_doc), genome.expanded(b_doc)
    left = {op["id"]: op for op in a["ops.jsonl"]}
    right = {op["id"]: op for op in b["ops.jsonl"]}
    common = left.keys() & right.keys()
    for key in sorted(common):
        if any(
            left[key][field] != right[key][field] for field in ("born", "by", "kind")
        ):
            raise ValueError(f"immutable:{key}.born/by/kind")
    operator = operator or rng.choice(("X1", "X3"))
    changes = []
    if operator == "X3":
        before = a["frozen.json"]["judge"]
        a["frozen.json"]["judge"] = copy.deepcopy(b["frozen.json"]["judge"])
        changes.append(
            {
                "op": operator,
                "path": "frozen.json/judge",
                "from": before,
                "to": a["frozen.json"]["judge"],
            }
        )
    elif operator == "X1":
        if not common:
            raise ValueError("X1 needs common op ids")
        kind = rng.choice(sorted({left[key]["kind"] for key in common}))
        eligible = sorted(key for key in common if left[key]["kind"] == kind)
        chosen = set(rng.sample(eligible, rng.randint(1, len(eligible))))
        a["ops.jsonl"] = [
            copy.deepcopy(right[o["id"]]) if o["id"] in chosen else o
            for o in a["ops.jsonl"]
        ]
        # Insert each b-only row before its next surviving b neighbour.
        for index, op in enumerate(b["ops.jsonl"]):
            if op["id"] in left:
                continue
            ids = [o["id"] for o in a["ops.jsonl"]]
            following = next(
                (o["id"] for o in b["ops.jsonl"][index + 1 :] if o["id"] in ids), None
            )
            at = ids.index(following) if following is not None else len(ids)
            a["ops.jsonl"].insert(at, copy.deepcopy(op))
        changes.append(
            {
                "op": operator,
                "path": "ops.jsonl",
                "ids": sorted(chosen),
                "inserted": [o["id"] for o in b["ops.jsonl"] if o["id"] not in left],
            }
        )
    else:
        raise ValueError(f"unsupported crossover: {operator}")
    return genome.pack(a_doc, a), {
        "parents": [a_doc["genome_sha"], b_doc["genome_sha"]],
        "arm": "cross",
        "ops": changes,
        "redraws": 0,
    }
