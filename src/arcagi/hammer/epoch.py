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
from pathlib import Path

from arcagi.grow import compress as g1
from arcagi.grow import curve as gc
from arcagi.grow import knobs as kn
from arcagi.grow import pool as pl
from arcagi.grow import prog as pg

from . import body
from . import formats as fm  # noqa: F401  (used by run_epoch)

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
