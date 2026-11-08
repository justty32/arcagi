"""Two-stage promotion judge, not-crowding-out gate, TTL / dormancy.

Promotion (ruling (2), 03 §4): MDL saves bits (``mdl_bits > 0``) **and**
>= 1 new solve path (``evidence.new_solves``) or witness hit, **and** the
no-crowd gate holds for the fast lane: Solved_L(shadow) ⊇ Solved_L(live) and
max(ntf_shadow / ntf_live) over shared solves <= 2.0. Promotions are one
batch per epoch; the H24 fuse in epoch.py can roll a batch back.
"""

from . import formats as fm


def no_crowd(main: dict[str, dict], shadow: dict[str, dict], ids_l,
             ratio_max: float = 2.0) -> tuple[bool, float]:
    live_ok = {t for t in ids_l if main[t]["test_ok"]}
    sh_ok = {t for t in ids_l if t in shadow and shadow[t]["test_ok"]}
    ratios = [(shadow[t]["nodes_to_first"] or 1) / max(1, main[t]["nodes_to_first"]
                                                      or 1)
              for t in live_ok & sh_ok]
    worst = max(ratios) if ratios else 1.0
    return live_ok <= sh_ok and worst <= ratio_max, round(worst, 3)


def judge(ops: list[dict], env: str, crowd_ok: bool,
          tried: set[str] | None = None) -> tuple[list[str], list[str]]:
    """Mutate ops in place; return (promoted ids, ids sent dormant).

    TTL only counts down for rows that got a shadow trial (``tried``); a
    dormant row returns to incubating only when ``env`` is not in its
    ``tried_env_hashes`` and it was never blamed by the H24 fuse.
    """
    up, down = [], []
    for o in ops:
        if o["status"] == "dormant" and env not in o["tried_env_hashes"] \
                and o["blamed_by"] is None:
            o["status"], o["ttl"] = "incubating", fm.TTL
        if o["status"] != "incubating":
            continue
        ev = o["evidence"]
        hit = bool(ev["new_solves"]) or ev["witness_hits"] > 0
        mdl = o["kind"] != "comb" or (o["mdl_bits"] or 0) > 0
        gate = crowd_ok or o["kind"] == "decomp"
        if hit and mdl and gate:
            o["status"] = "live"
            o["env_hash"] = env
            up.append(o["id"])
            continue
        if tried is not None and o["id"] not in tried:
            continue
        o["ttl"] -= 1
        if o["ttl"] <= 0:
            o["status"] = "dormant"
            o["tried_env_hashes"] = sorted(set(o["tried_env_hashes"]) | {env})
            down.append(o["id"])
    return up, down


def rollback(ops: list[dict], ids: list[str], epoch: int) -> None:
    for o in ops:
        if o["id"] in ids:
            o["status"] = "dormant"
            o["blamed_by"] = f"h24@{epoch}"
            if o["env_hash"]:
                o["tried_env_hashes"] = sorted(set(o["tried_env_hashes"])
                                               | {o["env_hash"]})
