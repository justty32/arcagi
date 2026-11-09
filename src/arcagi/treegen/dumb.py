"""Make isolated, hash-distinct negative controls; never patch hammer.

Audit of the original recipes (line numbers refer to hammer sources):
* no-learn/lib_cap=0 is inert: gate.py:17 returns it, but epoch.py:325-327
  calls grow.sleep_ops, whose grow.py:39-44 reads m/k/max_holes, not lib_cap.
  Replacement: pause grow and foundry (epoch.py:325,366) to block new combs,
  plus judge (epoch.py:392-393) to block inherited incubating promotions.
* gate-dormant is inert: gate.py:15-17 falls back to GATE_G1 when no live
  gate exists. Dormant rows may revive (judge.py:34-38). Replacement: keep
  that mutation and pause grow/foundry/judge as above.
* judge-block's frozen stage1/stage2 thresholds are inert: judge.py:24-48
  never reads frozen; promotion uses hit, mdl and crowd_ok. Replacement:
  pause nodes/judge/_metainfo.json (epoch.py:224-226,392-393). Grow can still
  add incubating combs, but ledger promote stays zero.
These replacements guarantee no comb promotions. no-learn/gate-dormant
also block comb additions in the normal isolated run (no external inbox).
null changes the root node's unused name: export-level name alone is not
hashed (treegen/refs.py:19-21). no-decomp keeps the first decomp op.
no-learn-all additionally asks meter to clear uses after each epoch:
epoch.py:317-321 accumulates uses outside pause controls, and epoch.py:250
feeds those counts to order_from_uses for the next search's ordering.
"""

import hashlib
from pathlib import Path

from arcagi.hammer.formats import read_json, write_json

from . import boundary
from .refs import deduplicate, expand, genome_sha, sha12

RECIPES = (
    "no-learn",
    "gate-dormant",
    "judge-block",
    "no-decomp",
    "null",
    "no-learn-all",
)


def make(parent_tree_json: str | Path, recipe: str, out_tree_json: str | Path) -> dict:
    """Write a changed genome plus verified file blobs, refusing overwrites."""
    boundary.check_stop()
    if recipe not in RECIPES:
        raise ValueError(f"unknown dumb recipe: {recipe}")
    source, out = Path(parent_tree_json).resolve(), Path(out_tree_json).resolve()
    if source == out or out.exists():
        raise ValueError(f"dumb destination already exists or equals parent: {out}")
    doc = read_json(source)
    if doc["genome_sha"] != genome_sha(doc["defs"], doc["tree"]):
        raise ValueError("parent genome_sha mismatch")
    tree = expand(doc["tree"], doc["defs"])
    original_content = sha12(tree)
    ops = tree["ops.jsonl"]
    if recipe in ("no-learn", "no-learn-all", "gate-dormant"):
        for name in ("grow", "foundry", "judge"):
            tree["nodes"][name]["_metainfo.json"]["status"] = "paused"
        for op in ops:
            if op["kind"] == "gate":
                if recipe == "gate-dormant":
                    op["status"] = "dormant"
                else:
                    op["payload"]["params"]["lib_cap"] = 0
        if recipe == "no-learn-all":
            tree["_metainfo.json"]["meter_freeze_uses"] = True
    elif recipe == "judge-block":
        tree["nodes"]["judge"]["_metainfo.json"]["status"] = "paused"
    elif recipe == "no-decomp":
        first = next((o for o in ops if o["kind"] == "decomp"), None)
        tree["ops.jsonl"] = [o for o in ops if o["kind"] != "decomp" or o is first]
    else:
        tree["_metainfo.json"]["name"] += "-null"
    if sha12(tree) == original_content:
        raise ValueError(f"dumb recipe changed nothing: {recipe}")
    defs, stored = deduplicate(tree)
    sha = genome_sha(defs, stored)
    if sha == doc["genome_sha"]:
        raise ValueError(f"dumb recipe changed nothing: {recipe}")
    blobs = {}

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if "$file" in value:
                key = value["sha1"]
                if len(key) != 40 or any(c not in "0123456789abcdef" for c in key):
                    raise ValueError("invalid blob sha1")
                data = (source.parent / "files" / key).read_bytes()
                if hashlib.sha1(data).hexdigest() != key:
                    raise ValueError("blob sha1 mismatch")
                blobs[key] = data
            else:
                for item in value.values():
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(tree)
    for key, data in blobs.items():
        target = boundary.safe_path(out.parent, f"files/{key}")
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f"blob destination collision: {target}")
    result = {
        **doc,
        "name": f"{doc['name']}-{recipe}",
        "defs": defs,
        "tree": stored,
        "genome_sha": sha,
        "dumb": {
            "recipe": recipe,
            "parent_sha": doc["genome_sha"],
            "original_inert": recipe in RECIPES[:3],
            "replacement": recipe in RECIPES[:3],
        },
    }
    for key, data in blobs.items():
        boundary.check_stop()
        target = boundary.safe_path(out.parent, f"files/{key}")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    write_json(out, result)
    return result
