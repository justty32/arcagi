"""Epoch flow of the hammer tree, plus the dec-g1 compatibility loop (M0).

``run_compat(out_dir, lib_dir, backend)`` re-runs r08 ``dec-g1`` (r07 knobs,
decomp on, lib cap 40, test-right L16 feeds G1, H8 + H24 measured) with the
body's backend; its curve.csv sha must equal r08's ``7aebb3c73f28``.

``run_epoch(root, n, *, holdout=True, stall_fn=None, route_fn=None,
foundry_fn=None, frozen_engine=False, backend="native") -> dict`` runs one
epoch (02 §5 steps 1-7, 03 §4) on the tree at ``root`` and returns its curve
row. ``holdout=False`` skips H8 / H24 entirely (scan / sieve / LTO folds;
they never load holdout ids then). Hook points for line B:

* ``stall_fn(ledger_rows) -> "ok"|"starve"|"saturate"|"stop"``
  (default: ``arcagi.hammer.stall.judge_stall`` if importable, else "ok")
* ``route_fn(ops, stall) -> arm`` (default: the live ``route`` row with the
  highest priority for that stall state)
* ``foundry_fn(root, task_id)`` on stop (default:
  ``arcagi.hammer.foundry.request`` if importable, else a request file in
  ``foundry/requests/pending/``)

Ops wiring: live ``comb`` rows are the library, the live ``gate`` row's
params drive the G1 gate, live ``sieve`` excludes go to the enumerator,
live ``decomp`` rows switch the main run to the Python backend.
"""

import json
import shutil
import time
from pathlib import Path

from arcagi.grow import compress as g1
from arcagi.grow import curve as gc
from arcagi.grow import knobs as kn
from arcagi.grow import pool as pl
from arcagi.grow import prog as pg

from . import body
from . import formats as fm
from . import gate as gt
from . import grow as gw
from . import judge as jg

R08_TASKSET = gc.TASKSET_R08


# ---------------------------------------------------------------- dec-g1

def _tcost(by_id, ids, budget, pass_no, cost0):
    tc = {}
    for tid in sorted(ids):
        s = by_id[tid]
        c = pl.task_cost(s["nodes_to_first"], s["test_ok"], budget)
        if pass_no == 0:
            cost0[tid] = c
        tc[tid] = round(pl.capped(c, cost0.get(tid), budget), 4)
    return tc


def run_compat(out_dir: Path, lib_dir: Path, backend: str = "native",
               passes: int = gc.N_PASSES, threads: int = 6, log=print) -> list[dict]:
    """r08 dec-g1 through hammer.body; same rows and files as run_curve."""
    knobs = kn.load(gc.TASKSET.parent / "knobs.json").with_(decomp=True,
                                                             lib_cap=40)
    learn, hold = gc.load_taskset(R08_TASKSET)
    h24 = gc._get_tasks(pl.h24_ids(R08_TASKSET))
    tasks = learn + hold + h24
    learn_ids = {t.task_id for t in learn}
    h24_ids = {t.task_id for t in h24}
    out_dir, lib_dir = Path(out_dir), Path(lib_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lib_path = lib_dir / "blocks.json"
    params = g1.Params(m=knobs.m, k=knobs.k, max_holes=knobs.max_holes)
    cfg = body.BodyCfg(backend=backend, decomp=True, lam_depth=knobs.lam_depth,
                       threads=threads, tmp_dir=str(lib_dir / "tmp"))
    n_prims = len(gc.backend._seed.PRIMS)
    blocks, born, uses, rows, cost0 = [], [], {}, [], {}
    sols_log = (out_dir / "solutions.jsonl").open("w")
    for pass_no in range(passes):
        gc._save_lib(blocks, lib_path)
        order = g1.order_from_uses(uses) if uses else None
        sols_all, wall = body.timed(body.solve_batch, tasks, lib_path,
                                    gc.BUDGET, cfg, order)
        by_id = {s["task_id"]: s for s in sols_all}
        sols = sols_all[:len(learn) + len(hold)]
        solved_l = {s["task_id"]: pg.from_json(s["program"]) for s in sols
                    if s["test_ok"] and s["task_id"] in learn_ids}
        feed = dict(solved_l)
        sizes = [pg.size(p) for p in solved_l.values()]
        tcost = _tcost(by_id, learn_ids | h24_ids, gc.BUDGET, pass_no, cost0)
        row = {
            "pass": pass_no, "solved_L": len(solved_l),
            "solved_H": sum(s["test_ok"] for s in sols
                            if s["task_id"] not in learn_ids),
            "wall_s": round(wall, 2), "nodes": sum(s["nodes"] for s in sols),
            "llm_calls": 0, "lib_size": len(blocks),
            "lib_bits": g1.lib_bits(blocks, n_prims),
            "mean_prog_nodes": round(sum(sizes) / len(sizes), 3) if sizes else None,
            "nodes_solved": sum(s["nodes_to_first"] or 0 for s in sols
                                if s["test_ok"] and s["task_id"] in learn_ids),
            "logcost_L": round(sum(tcost[t] for t in sorted(learn_ids)), 3),
            "solved_H24": sum(by_id[t]["test_ok"] for t in h24_ids),
            "nodes_total": sum(s["nodes"] + s.get("gate_nodes", 0)
                               for s in sols_all),
        }
        rows.append(row)
        for s in sols_all:
            part = ("L" if s["task_id"] in learn_ids else
                    "H24" if s["task_id"] in h24_ids else "H")
            sols_log.write(json.dumps({"pass": pass_no, "set": part, **s},
                                      sort_keys=True) + "\n")
        log(f"[dec-g1/{backend}] pass {pass_no}: L={row['solved_L']} "
            f"H={row['solved_H']} H24={row['solved_H24']} lib={len(blocks)} "
            f"wall={wall:.1f}s")
        for p in feed.values():
            for name in pg.ops(p):
                uses[name] = uses.get(name, 0) + 1
        extra, p_now = {}, params
        if len(feed) <= gc.COLD_START:
            extra = {f"{s['task_id']}~near": pg.from_json(s["near_top"])
                     for s in sols if s["task_id"] in learn_ids
                     and s["task_id"] not in feed and s["near_top"]}
            p_now = g1.Params(m=params.m, k=gc.COLD_K, max_holes=params.max_holes)
        blocks, added = g1.update(blocks, feed, p_now, pass_no, extra,
                                  cap=knobs.lib_cap, retire_after=g1.RETIRE_AFTER)
        born += added
    sols_log.close()
    gc._save_lib(blocks, out_dir / "blocks.json")
    gc._save_lib(born, out_dir / "blocks_born.json")
    gc.write_csv(rows, out_dir / "curve.csv")
    return rows


# ---------------------------------------------------------------- hammer

ROW_KEYS = ["epoch", "solved_L", "solved_H8", "solved_H24", "solved_P",
            "logcost_L", "lib_size", "lib_bits", "n_incubating", "n_live",
            "n_dormant", "gate_in", "promoted", "rolled_back", "stall", "arm",
            "evals_body", "evals_shadow", "evals_meta", "evals_foundry",
            "llm_calls", "false_pos", "env_hash", "near_best_L", "wall_s"]


def _default_stall(rows):
    try:
        from .stall import judge_stall
    except ImportError:
        return "ok"
    return judge_stall(rows)


def _default_route(ops, stall):
    try:
        from .route import pick_arm
        return pick_arm(ops, stall)
    except ImportError:
        rows = [o for o in ops if o["kind"] == "route" and o["status"] == "live"
                and o["payload"]["when_stall"] == stall]
        rows.sort(key=lambda o: (-o["payload"]["priority"], o["id"]))
        return rows[0]["payload"]["arm"] if rows else None


def _default_foundry(root, task_id, epoch):
    """On stop: line B's ``foundry.pick_task`` + ``request`` (no waiting,
    foundry_wait_sec = 0); a stub request file if foundry is missing."""
    try:
        from .foundry import pick_task, request
    except ImportError:
        p = Path(root) / "foundry" / "requests" / "pending" / f"{task_id}.json"
        fm.write_json(p, {"task": task_id, "time": fm.now(), "stub": True})
        return p
    tid = pick_task(root)
    return request(root, tid, epoch) if tid else None


def _inbox(root: Path, n: int, ops: list[dict]) -> None:
    """Read nodes/*/inbox/*.json at the epoch boundary (02 §6)."""
    for d in sorted((root / "nodes").glob("*/")):
        for f in sorted((d / "inbox").glob("*.json")):
            try:
                msg = json.loads(f.read_text())
                cmd = msg["cmd"]
                reply = _apply(root, d, msg, ops, n)
                kind = cmd
            except (ValueError, KeyError) as e:
                reply, kind = f"bad message: {e!r}", "inbox-error"
            fm.append_ledger(root, {"kind": kind, "epoch": n, "layer": 1,
                                    "by": "user", "node": d.name,
                                    "op_ids": [], "msg": f.read_text()[:2000],
                                    "reply": reply})
            fm.write_text(d / "outbox" / f"{f.stem}.reply.md", reply + "\n")
            f.unlink()


def _apply(root, d, msg, ops, n) -> str:
    cmd = msg["cmd"]
    if cmd == "say":
        return f"epoch {n}: noted by {d.name} (no LLM in this node)."
    if cmd in ("pause", "resume"):
        if d.name == "solve":
            return "solve cannot be paused (the body runs every epoch)."
        m = fm.load_metainfo(d)
        m["status"] = "paused" if cmd == "pause" else "active"
        fm.write_metainfo(d, m)
        return f"{d.name} is now {m['status']}."
    if cmd == "weight":
        for o in ops:
            if o["id"] == msg["route"] and o["kind"] == "route":
                old = o["payload"]["priority"]
                o["payload"]["priority"] = msg["w"]
                return f"{o['id']} priority {old} -> {msg['w']}."
        return f"no route row {msg['route']}."
    if cmd == "add-op":
        row = {**fm.new_op(msg["op"]["id"], msg["op"]["kind"], {}, "user", n),
               **msg["op"], "by": "user"}
        row["status"] = "live" if msg.get("live") else "incubating"
        row["born"] = {"epoch": n, "by": "user"}
        err = fm.check_op(row)
        if err or any(o["id"] == row["id"] for o in ops):
            return f"rejected: {err or 'duplicate id'}"
        ops.append(row)
        return f"added {row['id']} as {row['status']}."
    raise KeyError(f"unknown cmd {cmd}")


def _paused(root: Path, name: str) -> bool:
    m = fm.read_json(root / "nodes" / name / "_metainfo.json", {})
    return m.get("status") == "paused"


def _cfg(ops, threads, backend, root):
    live_dec = sorted(o["payload"]["name"] for o in ops
                      if o["kind"] == "decomp" and o["status"] == "live")
    excl = tuple(sorted({x for o in ops if o["kind"] == "sieve"
                         and o["status"] == "live"
                         for x in o["payload"].get("exclude", [])}))
    gate = gt.live_params(ops)
    be = "python" if live_dec else backend
    cfg = body.BodyCfg(backend=be, decomp=True,
                       decomp_set="+".join(["default", *live_dec]),
                       sub_lam_depth=3 if "nest" in live_dec else None,
                       exclude=excl, threads=threads, tmp_dir=str(root / "tmp"),
                       gate=gt.body_gate(gate))
    return cfg, gate


def _main_run(root, ops, tasks, ids, budgets, threads, backend, n, state):
    lib = gw.lib_from_ops(ops)
    lib_path = root / "epochs" / str(n) / "blocks.json"
    gc._save_lib(lib, lib_path)
    cfg, gate = _cfg(ops, threads, backend, root)
    order = g1.order_from_uses(state["uses"]) if state["uses"] else None
    sols = body.solve_batch(tasks, lib_path, budgets, cfg, order,
                            gate_ids=set(ids["L16"]) | set(ids["P"]))
    return {s["task_id"]: s for s in sols}, lib, gate


def run_epoch(root: Path, n: int, *, holdout: bool = True, stall_fn=None,
              route_fn=None, foundry_fn=None, frozen_engine: bool = False,
              backend: str = "native", threads: int = 6) -> dict:
    """One epoch (①..⑦) on the tree at ``root``; returns the curve row."""
    root = Path(root)
    t0 = time.perf_counter()
    frozen = fm.load_frozen(root)
    bud = frozen["budgets"]
    ops = fm.load_ops(root)
    state = fm.read_json(root / "live" / "state.json",
                         {"uses": {}, "cost0": {}, "prev": None, "batch": [],
                          "pool_mult": 1.0})
    _inbox(root, n, ops)
    tr = fm.read_json(root / "truth" / "train" / "taskset.json")
    ids = {"L16": tr["L16"], "P": tr["P"], "H8": [], "H24": []}
    if holdout:
        cal = fm.read_json(root / "truth" / "cal" / "ids.json")
        ids["H8"], ids["H24"] = cal["H8"], cal["H24"]
    all_ids = ids["L16"] + ids["H8"] + ids["H24"] + ids["P"]
    tasks = body.load_tasks(all_ids)
    b_p = pl.budget(bud["P0"], bud["P_mult"] * state["pool_mult"], bud["P_cap"], n)
    budgets = {t: (b_p if t in set(ids["P"]) else bud["L"]) for t in all_ids}
    evals = {"body": 0, "shadow": 0, "meta": 0, "foundry": 0, "llm_tax": 0}
    main, lib, gate = _main_run(root, ops, tasks, ids, budgets, threads,
                                backend, n, state)
    evals["body"] += sum(s["nodes"] + s.get("gate_nodes", 0) for s in main.values())
    rolled = False
    prev = state["prev"]
    h24 = sum(main[t]["test_ok"] for t in ids["H24"])
    if holdout and state["batch"] and prev and prev.get("solved_H24") is not None \
            and h24 < prev["solved_H24"]:  # H24 fuse: whole batch back to dormant
        jg.rollback(ops, state["batch"], n)
        fm.append_ledger(root, {"kind": "rollback", "epoch": n, "layer": 1,
                                "by": "judge", "op_ids": state["batch"],
                                "before": {"solved_H24": prev["solved_H24"]},
                                "after": {"solved_H24": h24}})
        main, lib, gate = _main_run(root, ops, tasks, ids, budgets, threads,
                                    backend, n, state)
        evals["body"] += sum(s["nodes"] + s.get("gate_nodes", 0)
                             for s in main.values())
        rolled = True
        batch = state["batch"]
        if len(batch) > 1:  # ablate the batch row by row (<= ablate_max reruns)
            snap = json.loads(json.dumps(ops))
            for oid in batch[:frozen["judge"].get("ablate_max", 3)]:
                for o in ops:
                    if o["id"] in batch and o["id"] != oid:
                        o["status"], o["blamed_by"] = "live", None
                trial, _, _ = _main_run(root, ops, tasks, ids, budgets, threads,
                                        backend, n, state)
                evals["body"] += sum(s["nodes"] + s.get("gate_nodes", 0)
                                     for s in trial.values())
                if sum(trial[t]["test_ok"] for t in ids["H24"]) >= prev["solved_H24"]:
                    fm.append_ledger(root, {"kind": "ablate", "epoch": n,
                                            "layer": 1, "by": "judge",
                                            "op_ids": [oid], "blamed": oid})
                    main, lib = trial, gw.lib_from_ops(ops)
                    break
                ops[:] = json.loads(json.dumps(snap))
    state["batch"] = []
    # ② gate feed (train-only LOO + MDL, D-r8-6)
    feed = {t: pg.from_json(s["program"]) for t, s in main.items()
            if s.get("gate_ok")}
    for p in feed.values():
        for name in pg.ops(p):
            state["uses"][name] = state["uses"].get(name, 0) + 1
    n_prims = len(gc.backend._seed.PRIMS)
    learn = not frozen_engine
    # ③ grow: sleep word-making -> incubating comb rows
    if learn and not _paused(root, "grow"):
        new = gw.sleep_ops(ops, feed, gate, n, n_prims)
        ops += new
        for o in new:
            fm.append_ledger(root, {"kind": "incubate", "epoch": n, "layer": 1,
                                    "by": "sleep", "op_ids": [o["id"]]})
    # ④ shadow, fast lane: live + incubating comb (L16 + P, never H)
    inc = [o for o in ops if o["status"] == "incubating"]
    tried: set[str] = set()  # ops that got a shadow trial this epoch
    crowd_ok, worst = True, 1.0
    lp = [t for t in tasks if t.task_id in set(ids["L16"]) | set(ids["P"])]
    if learn and any(o["kind"] == "comb" for o in inc):
        sh_lib = gw.lib_from_ops(ops, ("live", "incubating"))
        sh_path = root / "epochs" / str(n) / "shadow_blocks.json"
        gc._save_lib(sh_lib, sh_path)
        cfg, _ = _cfg(ops, threads, backend, root)
        cfg = body.BodyCfg(**{**cfg.to_dict(), "gate": None})
        order = g1.order_from_uses(state["uses"]) if state["uses"] else None
        shadow = {s["task_id"]: s for s in body.solve_batch(
            lp, sh_path, budgets, cfg, order)}
        evals["shadow"] += sum(s["nodes"] for s in shadow.values())
        crowd_ok, worst = jg.no_crowd(main, shadow, ids["L16"],
                                      frozen["judge"]["no_crowd"]["ntf_ratio_max"])
        for o in inc:
            if o["kind"] != "comb":
                continue
            o["evidence"]["shadow_epochs"] += 1
            tried.add(o["id"])
            name = o["payload"]["name"]
            for t, s in shadow.items():
                ok = s["test_ok"] if t in set(ids["L16"]) else s["train_ok"]
                was = (main[t]["test_ok"] if t in set(ids["L16"])
                       else main[t]["train_ok"])
                if ok and not was and name in pg.ops(pg.from_json(s["program"])):
                    o["evidence"]["new_solves"] = sorted(
                        set(o["evidence"]["new_solves"]) | {t})
    # ⑤ stall / route
    stall = (stall_fn or _default_stall)(fm.load_ledger(root))
    arm = (route_fn or _default_route)(ops, stall)
    if stall == "stop" and learn:
        unsolved = sorted(t for t in ids["L16"] if not main[t]["test_ok"])
        if unsolved and not _paused(root, "foundry"):
            (foundry_fn or _default_foundry)(root, unsolved[0], n)
    state["pool_mult"] = 2.0 if arm == "rt_pool" else 1.0
    if learn and arm == "rt_vsplit":  # slow lane: Python decomp rows
        todo = [t for t in lp if not (main[t.task_id]["test_ok"]
                                      if t.task_id in set(ids["L16"])
                                      else main[t.task_id]["train_ok"])]
        for o in [o for o in inc if o["kind"] == "decomp"]:
            cfg, _ = _cfg(ops, threads, "python", root)
            cfg = body.BodyCfg(**{**cfg.to_dict(), "backend": "python",
                                  "decomp_set": cfg.decomp_set + "+"
                                  + o["payload"]["name"], "gate": None,
                                  "sub_lam_depth": 3 if o["payload"]["name"]
                                  == "nest" else cfg.sub_lam_depth})
            slow = body.solve_batch(todo, root / "epochs" / str(n) / "blocks.json",
                                    {t.task_id: bud["shadow_slow"] for t in todo},
                                    cfg)
            evals["shadow"] += sum(s["nodes"] for s in slow)
            o["evidence"]["shadow_epochs"] += 1
            tried.add(o["id"])
            got = {s["task_id"] for s in slow if (s["test_ok"] if s["task_id"]
                   in set(ids["L16"]) else s["train_ok"])}
            o["evidence"]["new_solves"] = sorted(set(o["evidence"]["new_solves"])
                                                 | got)
    # ⑥ judge: one promotion batch per epoch
    env = fm.env_hash(ops)
    up, down = ([], []) if not learn or _paused(root, "judge") else \
        jg.judge(ops, env, crowd_ok, tried)
    if up:
        state["batch"] = up
        fm.append_ledger(root, {"kind": "promote", "epoch": n, "layer": 1,
                                "by": "judge", "op_ids": up,
                                "judge": {"stage": 1, "accepted": True,
                                          "no_crowd": crowd_ok, "ntf_worst": worst}})
    if down:
        fm.append_ledger(root, {"kind": "demote", "epoch": n, "layer": 1,
                                "by": "judge", "op_ids": down})
    fm.write_ops(root, ops)
    # ⑦ write epoch files
    solved_l = [t for t in ids["L16"] if main[t]["test_ok"]]
    cost0 = state["cost0"]
    tc = _tcost(main, ids["L16"], bud["L"], 0 if not cost0 else 1, cost0)
    near = [main[t].get("near_score") or 0.0 for t in ids["L16"]
            if not main[t]["test_ok"]]
    row = {
        "epoch": n, "solved_L": len(solved_l),
        "solved_H8": sum(main[t]["test_ok"] for t in ids["H8"]) if holdout else None,
        "solved_H24": h24 if holdout else None,
        "solved_P": sum(main[t]["train_ok"] for t in ids["P"]),
        "logcost_L": round(sum(tc.values()), 3), "lib_size": len(lib),
        "lib_bits": g1.lib_bits(lib, n_prims),
        "n_incubating": sum(o["status"] == "incubating" for o in ops),
        "n_live": sum(o["status"] == "live" for o in ops),
        "n_dormant": sum(o["status"] == "dormant" for o in ops),
        "gate_in": len(feed), "promoted": len(up), "rolled_back": rolled,
        "stall": stall, "arm": arm, "evals_body": evals["body"],
        "evals_shadow": evals["shadow"], "evals_meta": 0, "evals_foundry": 0,
        "llm_calls": 0,
        "false_pos": sum(not main[t]["test_ok"] for t in feed if t in set(ids["L16"])),
        "env_hash": env, "wall_s": round(time.perf_counter() - t0, 2),
        "near_best_L": round(max(near), 6) if near else None,
    }
    ed = root / "epochs" / str(n)
    fm.write_text(ed / "curve.csv", ",".join(ROW_KEYS) + "\n"
                  + ",".join(gc._fmt(row.get(k)) for k in ROW_KEYS) + "\n")
    fm.write_jsonl(ed / "solutions.jsonl",
                   [{"epoch": n, "set": next(k for k in ("L16", "H8", "H24", "P")
                                             if t in set(ids[k])), **main[t]}
                    for t in all_ids])
    status = {k: row[k] for k in ROW_KEYS}
    fm.write_json(ed / "status.json", status)
    fm.write_json(root / "live" / "_status.json", {**status, "time": fm.now()})
    fm.append_jsonl(root / "live" / "events.jsonl",
                    {"time": fm.now(), "event": "epoch", "epoch": n,
                     "promoted": up, "demoted": down, "rolled_back": rolled,
                     "stall": stall, "arm": arm})
    for o in ops:
        if o["kind"] in ("comb", "decomp"):
            fm.write_json(root / "ops" / o["id"] / "_metainfo.json",
                          {"id": o["id"], "kind": o["kind"], "status": o["status"],
                           "by": o["by"], "born": o["born"],
                           "evidence": o["evidence"], "payload": o["payload"]})
    fm.append_ledger(root, {"kind": "epoch", "epoch": n, "layer": 1, "by": "solve",
                            "op_ids": up, "after": {k: row[k] for k in (
                                "solved_L", "solved_H24", "logcost_L")},
                            "evals": evals, **{k: row[k] for k in (
                                "solved_L", "solved_H24", "lib_bits", "gate_in",
                                "near_best_L")}})
    state["prev"] = row
    fm.write_json(root / "live" / "state.json", state)
    return row


TREE_SETUP = {"hammer": ("incubating", False), "hammer-frozen": ("", True),
              "hammer-static": ("live", True)}


def run_tree(root: Path, tree: str, epochs: int = 8, taskset: Path | None = None,
             backend: str = "native", threads: int = 6, holdout: bool = True,
             log=print) -> list[dict]:
    """init_root if needed, then epochs 0..epochs (epoch 0 = start tree)."""
    root = Path(root)
    halves_nest, frozen_engine = TREE_SETUP[tree]
    if not (root / "ops.jsonl").exists():
        ts = taskset or (fm.ROOT_TASKSET if hasattr(fm, "ROOT_TASKSET") else None)
        ts = ts or gc.ROOT / "data" / "r09" / "taskset.json"
        if not Path(ts).exists():
            ts = R08_TASKSET
        fm.init_root(root, ts, halves_nest=halves_nest, tree=tree)
    (root / "RUN").touch()
    done = [r for r in fm.load_ledger(root) if r["kind"] == "epoch"
            and r["epoch"] >= 0]
    start = max((r["epoch"] for r in done), default=-1) + 1
    rows = [fm.read_json(root / "epochs" / str(e) / "status.json")
            for e in range(start)]
    for n in range(start, epochs + 1):
        if not (root / "RUN").exists():
            fm.append_jsonl(root / "live" / "events.jsonl",
                            {"time": fm.now(), "event": "stopped", "epoch": n})
            break
        r = run_epoch(root, n, holdout=holdout, frozen_engine=frozen_engine,
                      backend=backend, threads=threads)
        rows.append(r)
        log(f"[{tree}] epoch {n}: L={r['solved_L']} H8={r['solved_H8']} "
            f"H24={r['solved_H24']} P={r['solved_P']} lib={r['lib_size']} "
            f"inc={r['n_incubating']} up={r['promoted']} stall={r['stall']} "
            f"arm={r['arm']} wall={r['wall_s']}s")
    return rows


def export(root: Path, out: Path) -> None:
    """Snapshot epochs/ curve rows into reports/curve-r09/<tree>/."""
    root, out = Path(root), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for d in sorted((root / "epochs").glob("*/"), key=lambda p: int(p.name)):
        st = fm.read_json(d / "status.json")
        if st:
            rows.append(st)
    fm.write_text(out / "curve.csv", ",".join(ROW_KEYS) + "\n" + "".join(
        ",".join(gc._fmt(r.get(k)) for k in ROW_KEYS) + "\n" for r in rows))
    for f in ("ops.jsonl", "ledger.jsonl", "frozen.json"):
        if (root / f).exists():
            shutil.copy(root / f, out / f)
