"""Sleep word-making: G1 anti-unification candidates as ``comb`` op rows.

``grow.compress.candidates`` rewritten to emit ops: each new template (not
already a comb row in any status) becomes ``kind: comb, status: incubating,
by: sleep``; ``mdl_bits`` = MDL saving * log2(vocab).
"""

import math

from arcagi.grow import compress as g1
from arcagi.grow import prog as pg
from arcagi.grow.sig import infer_sig

from . import formats as fm


def lib_from_ops(ops: list[dict], statuses=("live",)) -> list[dict]:
    """comb rows -> seed library blocks (``blocks.json`` entries)."""
    out = []
    for o in ops:
        if o["kind"] != "comb" or o["status"] not in statuses:
            continue
        p = o["payload"]
        out.append({"name": p["name"], "body": pg.from_json(p["body"]),
                    "holes": p.get("holes", 0), "sig": o["sig"],
                    "src_tasks": p.get("src_tasks", []),
                    "saving": p.get("saving", 0), "uses": 0, "idle": 0,
                    "born": o["born"]["epoch"]})
    return out


def sleep_ops(ops: list[dict], feed: dict, params: dict, epoch: int,
              n_prims: int) -> list[dict]:
    """New incubating comb rows from this epoch's gate feed (<= m)."""
    have = {pg.key(pg.from_json(o["payload"]["body"])) for o in ops
            if o["kind"] == "comb"}
    known = {b["name"]: b for b in lib_from_ops(ops)}
    vocab = max(2, n_prims + len(known) + 3)
    p = g1.Params(m=int(params["m"]), k=float(params["k"]),
                  max_holes=int(params["max_holes"]))
    new = []
    for c in g1.candidates(feed, p):
        if len(new) >= p.m:
            break
        k = pg.key(c["body"])
        if k in have or any(n.startswith("g1_") and n not in known
                            for n in pg.ops(c["body"])):
            continue
        sig = infer_sig(c["body"], known)
        if sig is None:
            continue
        have.add(k)
        name = g1.block_name(c["body"])
        new.append(fm.new_op(
            f"comb_{name}", "comb",
            {"name": name, "body": pg.to_json(c["body"]), "holes": c["holes"],
             "src_tasks": c["src_tasks"], "saving": c["saving"]},
            "sleep", epoch, sig=sig,
            mdl_bits=round(c["saving"] * math.log2(vocab), 3),
            parent_route="rt_sleep"))
    return new
