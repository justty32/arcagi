"""The hammer tree's five files: reading, atomic writing and field checks.

Files (notes/rounds/r09/02-規劃-fable.md §1.1, 03-設計.md §4):

* ``_metainfo.json`` per node (and one at the root, ``kind: tree``)
* ``_witness.jsonl`` per node
* ``ops.jsonl`` at the root: the op table (comb/decomp/rewrite/route/gate/sieve)
* ``ledger.jsonl`` at the root: append-only event log
* ``frozen.json`` at the root: what the tree may never change by itself

Every whole-file write goes through ``write_json`` / ``write_jsonl`` (tmp file
in the same directory, then ``os.replace``); appends are one ``write`` of a
complete line. ``check_*`` return a list of error strings (empty = ok).
"""

import hashlib
import json
import os
import time
from pathlib import Path

SCHEMA_FROZEN = "hammer-frozen/1"
OP_KINDS = ("comb", "decomp", "rewrite", "route", "gate", "sieve")
OP_STATUS = ("incubating", "live", "dormant")
OP_BY = ("sleep", "foundry", "agent-r08", "agent-r09", "user", "gate-scan")
NODE_KINDS = ("solve", "gate", "grow", "stall", "route", "judge", "foundry",
              "tree")
NODES = ("solve", "gate", "grow", "stall", "route", "judge", "foundry")
ROUTE_ARMS = ("rt_sleep", "rt_vsplit", "rt_pool", "rt_gatescan")
STALL_STATES = ("ok", "starve", "saturate", "stop")
LEDGER_KINDS = ("epoch", "promote", "demote", "rollback", "layer2", "say",
                "foundry", "stall", "route", "pause", "resume", "weight",
                "add-op", "incubate", "ablate", "inbox-error")
WITNESS_STATUS = ("open", "fitted", "dropped")
GATE_G1 = {"mdl_div": 1.0, "loo_frac": 0.25, "loo_min_pairs": 3, "lib_cap": 16,
           "retire_after": 2, "m": 3, "k": 2.0, "max_holes": 2}
BUDGETS = {"L": 100_000, "P0": 25_000, "P_cap": 400_000, "epochs": 8,
           "P_mult": 2.0, "shadow_slow": 100_000}
JUDGE = {"stage1": {"new_solves_min": 1, "h24_regress": False},
         "stage2": {"not_worse_frac": 0.8, "drop_min": 1.0, "se_mult": 2},
         "no_crowd": {"solved_superset": True, "ntf_ratio_max": 2.0},
         "ablate_max": 3}
LLM_TAX_EVALS = 100_000
TTL = 3


# ---------------------------------------------------------------- raw I/O

def _tmp(path: Path) -> Path:
    return path.with_name(f".{path.name}.{os.getpid()}.tmp")


def write_text(path: Path, text: str) -> None:
    """Atomic whole-file write: tmp in the same directory, then rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp(path)
    with tmp.open("w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json(path: Path, obj) -> None:
    write_text(path, json.dumps(obj, indent=1, sort_keys=True) + "\n")


def read_json(path: Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    write_text(path, "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def append_jsonl(path: Path, row: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------- the five

def load_ops(root: Path) -> list[dict]:
    return read_jsonl(Path(root) / "ops.jsonl")


def write_ops(root: Path, ops: list[dict]) -> None:
    write_jsonl(Path(root) / "ops.jsonl", ops)


def append_ops(root: Path, rows: list[dict]) -> None:
    """Append op rows (ids must be new); rewrites the file atomically."""
    ops = load_ops(root)
    have = {o["id"] for o in ops}
    for r in rows:
        if r["id"] in have:
            raise ValueError(f"duplicate op id {r['id']}")
        have.add(r["id"])
    write_ops(root, ops + list(rows))


def load_ledger(root: Path) -> list[dict]:
    return read_jsonl(Path(root) / "ledger.jsonl")


def append_ledger(root: Path, row: dict) -> None:
    row = {"time": now(), **row}
    append_jsonl(Path(root) / "ledger.jsonl", row)


def load_frozen(root: Path) -> dict:
    return read_json(Path(root) / "frozen.json")


def load_metainfo(node_dir: Path) -> dict:
    return read_json(Path(node_dir) / "_metainfo.json")


def write_metainfo(node_dir: Path, meta: dict) -> None:
    write_json(Path(node_dir) / "_metainfo.json", meta)


def load_witness(node_dir: Path) -> list[dict]:
    return read_jsonl(Path(node_dir) / "_witness.jsonl")


def append_witness(node_dir: Path, row: dict) -> None:
    append_jsonl(Path(node_dir) / "_witness.jsonl", row)


def env_hash(ops: list[dict]) -> str:
    """sha1 of the live environment, first 12 hex digits.

    = sorted live comb bodies + live sieve excludes + live gate params, plus
    the live decomp split names (a live split changes what a shadow run can
    solve, so dormant rows must see it as a new environment).
    """
    live = [o for o in ops if o.get("status") == "live"]
    env = {
        "comb": sorted(json.dumps(o["payload"].get("body"), sort_keys=True)
                       for o in live if o["kind"] == "comb"),
        "sieve": sorted({x for o in live if o["kind"] == "sieve"
                         for x in o["payload"].get("exclude", [])}),
        "gate": sorted(json.dumps(o["payload"].get("params"), sort_keys=True)
                       for o in live if o["kind"] == "gate"),
        "decomp": sorted(o["payload"].get("name", "") for o in live
                         if o["kind"] == "decomp"),
    }
    return hashlib.sha1(json.dumps(env, sort_keys=True).encode()).hexdigest()[:12]


def ids_sha(ids) -> str:
    """sha1 of sorted task ids joined by newlines (first 12 digits)."""
    return hashlib.sha1("\n".join(sorted(ids)).encode()).hexdigest()[:12]


def new_op(op_id: str, kind: str, payload: dict, by: str, epoch: int,
           status: str = "incubating", sig: str | None = None,
           mdl_bits: float | None = None, parent_route: str | None = None) -> dict:
    """One ops.jsonl row with every field present."""
    return {"id": op_id, "kind": kind, "status": status, "payload": payload,
            "sig": sig, "mdl_bits": mdl_bits,
            "evidence": {"new_solves": [], "witness_hits": 0, "shadow_epochs": 0},
            "ttl": TTL, "env_hash": None, "parent_route": parent_route,
            "by": by, "born": {"epoch": epoch, "by": by}, "blamed_by": None,
            "tried_env_hashes": []}


# ---------------------------------------------------------------- checks

def _need(row: dict, keys, where: str) -> list[str]:
    return [f"{where}: missing {k}" for k in keys if k not in row]


def check_op(o: dict) -> list[str]:
    w = f"op {o.get('id')}"
    err = _need(o, ("id", "kind", "status", "payload", "sig", "mdl_bits",
                    "evidence", "ttl", "env_hash", "parent_route", "by", "born",
                    "blamed_by", "tried_env_hashes"), w)
    if err:
        return err
    if o["kind"] not in OP_KINDS:
        err.append(f"{w}: kind {o['kind']}")
    if o["status"] not in OP_STATUS:
        err.append(f"{w}: status {o['status']}")
    if o["by"] not in OP_BY:
        err.append(f"{w}: by {o['by']}")
    if not isinstance(o["payload"], dict):
        return err + [f"{w}: payload not an object"]
    if not isinstance(o["tried_env_hashes"], list):
        err.append(f"{w}: tried_env_hashes not a list")
    ev = o["evidence"]
    err += _need(ev, ("new_solves", "witness_hits", "shadow_epochs"), w + ".evidence")
    err += _need(o["born"], ("epoch", "by"), w + ".born")
    p = o["payload"]
    need = {"comb": ("body",), "decomp": ("name",), "gate": ("params",),
            "route": ("when_stall", "arm", "priority")}.get(o["kind"], ())
    err += _need(p, need, w + ".payload")
    if o["kind"] == "sieve" and not ("exclude" in p or "forbid_ast" in p):
        err.append(f"{w}.payload: sieve needs exclude or forbid_ast")
    if o["kind"] == "route" and not err:
        if p["when_stall"] not in STALL_STATES[:3]:
            err.append(f"{w}.payload: when_stall {p['when_stall']}")
        if p["arm"] not in ROUTE_ARMS:
            err.append(f"{w}.payload: arm {p['arm']}")
    return err


def check_ledger_row(r: dict, i: int) -> list[str]:
    w = f"ledger line {i + 1}"
    err = _need(r, ("kind", "epoch", "time"), w)
    if "kind" in r and r["kind"] not in LEDGER_KINDS:
        err.append(f"{w}: kind {r['kind']}")
    if r.get("layer") not in (None, 1, 2):
        err.append(f"{w}: layer {r.get('layer')}")
    return err


def check_metainfo(m: dict, where: str) -> list[str]:
    err = _need(m, ("name", "kind", "entry", "reads", "writes", "status",
                    "weight", "born"), where)
    if not err:
        if m["kind"] not in NODE_KINDS:
            err.append(f"{where}: kind {m['kind']}")
        if m["status"] not in ("active", "paused"):
            err.append(f"{where}: status {m['status']}")
    return err


def check_witness_row(r: dict, where: str) -> list[str]:
    err = _need(r, ("id", "task", "pair", "dir", "src", "examples", "props",
                    "info_bits", "status", "fit", "epoch"), where)
    if not err:
        if r["dir"] not in ("fwd", "bwd"):
            err.append(f"{where}: dir {r['dir']}")
        if r["status"] not in WITNESS_STATUS:
            err.append(f"{where}: status {r['status']}")
    return err


def check_frozen(f: dict) -> list[str]:
    err = _need(f, ("schema", "h24_floor", "holdout", "purity", "judge",
                    "layers_max", "priors", "budgets", "llm_tax_evals"), "frozen")
    if err:
        return err
    if f["schema"] != SCHEMA_FROZEN:
        err.append(f"frozen: schema {f['schema']}")
    for h in ("H8", "H24"):
        err += _need(f["holdout"].get(h, {}), ("n", "sha"), f"frozen.holdout.{h}")
    err += _need(f["budgets"], ("L", "P0", "P_cap", "epochs"), "frozen.budgets")
    err += _need(f["judge"], ("stage1", "stage2"), "frozen.judge")
    return err


# ---------------------------------------------------------------- tree

def taskset_ids(taskset: Path) -> dict[str, list[str]]:
    """L16 / H8 / H24 / P ids from an r08 or r09 taskset file.

    P: ``P48`` (r09, line C) if present, else r08 ``pool_foot32``.
    """
    data = json.loads(Path(taskset).read_text())

    def ids(key):
        return [e["task_id"] if isinstance(e, dict) else e for e in data[key]]

    p_key = next(k for k in ("P48", "pool_p48", "p48", "pool_foot32")
                 if k in data)
    return {"L16": ids("learn"), "H8": ids("holdout"), "H24": ids("holdout24"),
            "P": ids(p_key), "_p_key": [p_key]}


def node_meta(name: str) -> dict:
    entry = {"solve": "arcagi.hammer.body:run"}.get(
        name, f"arcagi.hammer.node:run_{name}")
    return {"name": name, "kind": name, "entry": entry,
            "reads": ["ops.jsonl", "truth/train"],
            "writes": ["epochs/<n>/solutions.jsonl"] if name == "solve" else
            ["ops.jsonl", "ledger.jsonl"],
            "status": "active", "weight": 1.0,
            "born": {"epoch": 0, "by": "agent-r09"}}


def seed_ops(halves_nest: str = "incubating") -> list[dict]:
    """The op table a fresh tree starts with.

    ``halves_nest``: status of the two r08 hand-written splits ("incubating"
    in the main tree, "live" in hammer-static, "" = leave them out).
    """
    ops = [new_op("gate_g1", "gate", {"params": dict(GATE_G1)}, "agent-r09", 0,
                  status="live")]
    for name in ("halves", "nest") if halves_nest else ():
        ops.append(new_op(f"decomp_{name}", "decomp", {"name": name},
                          "agent-r08", 0, status=halves_nest))
    table = [("ok", "rt_sleep", 2), ("ok", "rt_vsplit", 1),
             ("starve", "rt_pool", 2), ("starve", "rt_sleep", 1),
             ("saturate", "rt_vsplit", 2), ("saturate", "rt_gatescan", 1)]
    for when, arm, pri in table:
        ops.append(new_op(f"route_{when}_{arm}", "route",
                          {"when_stall": when, "arm": arm, "priority": pri},
                          "agent-r09", 0, status="live"))
    return ops


def init_root(root: Path, taskset: Path, halves_nest: str = "incubating",
              tree: str = "hammer", budgets: dict | None = None) -> Path:
    """Create an empty hammer tree at ``root`` (fails if ops.jsonl exists)."""
    root = Path(root)
    if (root / "ops.jsonl").exists():
        raise FileExistsError(f"{root} already has ops.jsonl")
    ids = taskset_ids(taskset)
    sha = hashlib.sha1(Path(taskset).read_bytes()).hexdigest()
    frozen = {
        "schema": SCHEMA_FROZEN, "tree": tree,
        "h24_floor": "per-epoch no regress",
        "taskset": {"path": str(taskset), "sha1": sha, "p_key": ids["_p_key"][0]},
        "holdout": {"H8": {"n": len(ids["H8"]), "sha": ids_sha(ids["H8"])},
                    "H24": {"n": len(ids["H24"]), "sha": ids_sha(ids["H24"])}},
        "purity": {"script": "scripts/r07_purity.sh"},
        "judge": json.loads(json.dumps(JUDGE)),
        "layers_max": 3, "priors": [],
        "budgets": {**BUDGETS, **(budgets or {})},
        "llm_tax_evals": LLM_TAX_EVALS, "foundry_wait_sec": 0,
        "split_ab": "sha1(task_id+'r09AB')",
    }
    write_json(root / "frozen.json", frozen)
    write_metainfo(root, {**node_meta("solve"), "name": tree, "kind": "tree",
                          "entry": "arcagi.hammer.epoch:run_epoch",
                          "reads": ["frozen.json", "ops.jsonl"],
                          "writes": ["epochs/", "live/", "ledger.jsonl"]})
    write_ops(root, seed_ops(halves_nest))
    write_text(root / "ledger.jsonl", "")
    write_json(root / "truth" / "train" / "taskset.json",
               {"L16": ids["L16"], "P": ids["P"]})
    write_json(root / "truth" / "cal" / "ids.json",
               {"H8": ids["H8"], "H24": ids["H24"]})
    for name in NODES:
        d = root / "nodes" / name
        write_metainfo(d, node_meta(name))
        for sub in ("inbox", "outbox"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        if not (d / "_witness.jsonl").exists():
            write_text(d / "_witness.jsonl", "")
    for sub in ("foundry/requests/pending", "foundry/requests/done",
                "foundry/wax", "epochs", "live", "ops"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    append_ledger(root, {"kind": "epoch", "epoch": -1, "layer": 1,
                         "by": "agent-r09", "op_ids": [], "note": "init_root"})
    return root
