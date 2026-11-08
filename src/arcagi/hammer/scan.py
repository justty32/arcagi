"""Layer-2 scan: the review (G1 gate, route table) searched by brute force.

02-規劃-fable.md §4 and 03-設計.md §4 proposals 3 / 4 (written down before
any run). Only L16 + P48 are used: ids come from the taskset's ``learn`` /
``P48`` keys and holdout ids are never loaded; short curves run
``epoch.run_epoch(..., holdout=False)`` on scratch roots whose truth files
carry empty H8 / H24 lists.

``--kind gate``
  1. Neighbourhood of the live ``gate`` row: single-factor variants
     ``mdl_div∈{0.5,1,2}``, ``loo_frac∈{0.1,0.25,0.5}``, ``lib_cap∈{8,16,32}``,
     ``retire_after∈{1,2,3}``, ``k∈{1,2,4}``, ``max_holes∈{1,2}``.
  2. Offline replay (0 arcbatch calls) on the root's
     ``epochs/*/solutions.jsonl``: the gate feed is recomputed per variant
     (MDL re-checked with the variant's ``mdl_div``; the stored LOO verdict is
     reused, so ``loo_frac`` / ``loo_min_pairs`` variants are invisible
     offline and collapse with the base), then ``grow.sleep_ops`` with the
     variant's m / k / max_holes; variants are grouped by ``blocks_sha`` (sha1
     of the sorted new comb bodies).
  3. Only the <= 4 groups whose block set differs from the base get a short
     curve: 3 CRN seeds (P48 subsets ``grow.pool.subset(P, seed, 0.75)``,
     L16 whole) x 4 epochs, base and variant on the same seeds.
  4. Judge on the folds ``sha1(task_id+"r09AB")`` (even last hex -> A):
     selected when fold A, summed over seeds at the last epoch, loses 0 tasks
     and solves more, or solves the same and sum(nodes_to_first) drops >= 5%;
     accepted when fold B (out of fold) also loses 0 and drops >= 5% or
     solves >= 1 more. Accepted -> new ``gate`` row live, old row dormant
     (``--write``); every tried variant gets a ledger row ``layer: 2,
     by: gate-scan`` with ``accepted`` as is.

``--kind route``: neighbourhood = each live route row's priority +-1, or its
arm swapped for each other arm; same short curves and judge. The route arm
only matters when a stall state other than ok occurs inside 4 epochs, so
variants whose state never fires are judged equal (Δ0) without a run.

    python -m arcagi.hammer.scan <root> --kind gate|route [--write] [--dry]
"""

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

from arcagi.grow import pool as pl
from arcagi.grow import prog as pg
from arcagi.hammer import formats as fm
from arcagi.hammer.sieve import TASKSET, fold, train_ids

NEIGH = {"mdl_div": (0.5, 1.0, 2.0), "loo_frac": (0.1, 0.25, 0.5),
         "lib_cap": (8, 16, 32), "retire_after": (1, 2, 3),
         "k": (1.0, 2.0, 4.0), "max_holes": (1, 2)}
SEEDS = (1, 2, 3)
EPOCHS = 4
MAX_REPS = 4
DROP_MIN = 0.05


DOUBLE = [{"mdl_div": a, "k": b} for a in (0.5, 2.0) for b in (1.0, 4.0)] + \
    [{"k": b, "max_holes": 1} for b in (1.0, 4.0)] + \
    [{"mdl_div": a, "max_holes": 1} for a in (0.5, 2.0)]


def gate_variants(params: dict) -> list[dict]:
    """12 single-factor + 8 double-factor variants (02 §4)."""
    out = []
    for k, vals in NEIGH.items():
        for v in vals:
            if params.get(k) != v:
                out.append({**params, k: v})
    for d in DOUBLE:
        v = {**params, **d}
        if v != params and v not in out:
            out.append(v)
    return out


# ---------------------------------------------------------------- offline

def _solutions(root: Path, keep: set) -> list[list[dict]]:
    eps = sorted((p for p in (Path(root) / "epochs").glob("*/solutions.jsonl")),
                 key=lambda p: int(p.parent.name))
    return [[r for r in fm.read_jsonl(p) if r["task_id"] in keep] for p in eps]


def _train(tid: str) -> list:
    from arcagi.hammer.foundry import _load_task
    return [(e["input"], e["output"]) for e in _load_task(tid)["train"]]


def blocks_sha(root: Path, params: dict, ops: list[dict]) -> str:
    """Replay the gate feed + sleep under ``params``; sha of new comb bodies."""
    from arcagi.grow.backend import _seed
    from arcagi.hammer import grow as gw

    keep = set(train_ids())
    ops = copy.deepcopy([o for o in ops if o["kind"] != "comb"
                         or o["by"] != "sleep"])
    bodies = []
    for n, rows in enumerate(_solutions(root, keep)):
        feed = {}
        for r in rows:
            if not (r.get("train_ok") and r.get("program") is not None):
                continue
            prog = pg.from_json(r["program"])
            mdl = pl.mdl_ok(prog, _train(r["task_id"]), params["mdl_div"])
            loo = bool(r.get("gate_ok")) if r.get("mdl_ok") else False
            if mdl and loo:
                feed[r["task_id"]] = prog
        new = gw.sleep_ops(ops, feed, params, n, len(_seed.PRIMS))
        ops += new
        bodies += [json.dumps(o["payload"]["body"]) for o in new]
    return hashlib.sha1("\n".join(sorted(bodies)).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- short curves

def _h_free_taskset(work: Path, seed: int) -> Path:
    """Taskset copy with L16 + a P48 subset and empty holdout lists."""
    d = json.loads(TASKSET.read_text())
    learn = [e["task_id"] if isinstance(e, dict) else e for e in d["learn"]]
    p48 = [e["task_id"] if isinstance(e, dict) else e for e in d["P48"]]
    out = {"learn": learn, "P48": pl.subset(p48, seed, 0.75),
           "holdout": [], "holdout24": []}
    path = work / f"taskset-s{seed}.json"
    fm.write_json(path, out)
    return path


def short_curve(work: Path, name: str, seed: int, ops_patch,
                threads: int = 6) -> dict[str, dict]:
    """4 epochs on a scratch root; last epoch's solutions by task id."""
    from arcagi.hammer import epoch as ep

    root = work / f"{name}-s{seed}"
    shutil.rmtree(root, ignore_errors=True)
    fm.init_root(root, _h_free_taskset(work, seed))
    fm.write_ops(root, ops_patch(fm.load_ops(root)))
    for n in range(EPOCHS):
        ep.run_epoch(root, n, holdout=False, threads=threads)
    last = root / "epochs" / str(EPOCHS - 1) / "solutions.jsonl"
    return {r["task_id"]: r for r in fm.read_jsonl(last)}


def _fold_cmp(base: dict, cand: dict, f: str) -> dict:
    lost = gained = nb = nc = 0
    for s in base:
        ids = [t for t in base[s] if fold(t) == f]
        ok_b = {t for t in ids if base[s][t].get("test_ok")}
        ok_c = {t for t in ids if cand[s].get(t, {}).get("test_ok")}
        lost += len(ok_b - ok_c)
        gained += len(ok_c - ok_b)
        nb += sum(base[s][t]["nodes_to_first"] or 0 for t in ok_b & ok_c)
        nc += sum(cand[s][t]["nodes_to_first"] or 0 for t in ok_b & ok_c)
    return {"lost": lost, "gained": gained, "ntf_base": nb, "ntf": nc,
            "drop": round(1 - nc / nb, 4) if nb else 0.0}


def judge(base: dict, cand: dict) -> dict:
    a, b = _fold_cmp(base, cand, "A"), _fold_cmp(base, cand, "B")
    sel = a["lost"] == 0 and (a["gained"] > 0 or a["drop"] >= DROP_MIN)
    acc = sel and b["lost"] == 0 and (b["gained"] >= 1 or b["drop"] >= DROP_MIN)
    return {"A": a, "B": b, "selected": sel, "accepted": acc}


def _set_gate(params):
    def patch(ops):
        for o in ops:
            if o["kind"] == "gate" and o["status"] == "live":
                o["payload"]["params"] = dict(params)
        return ops
    return patch


def scan_gate(root: Path, work: Path, write: bool = False, dry: bool = False,
              epoch: int | None = None, probe: int = 0) -> dict:
    """``probe``: also run short curves for that many offline-Δ0 variants
    (checks that the offline dedupe is right; their verdicts are recorded
    like any other)."""
    root, work = Path(root), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    ops = fm.load_ops(root)
    live = next(o for o in ops if o["kind"] == "gate" and o["status"] == "live")
    base_p = live["payload"]["params"]
    base_sha = blocks_sha(root, base_p, ops)
    groups: dict[str, list[dict]] = {}
    for v in gate_variants(base_p):
        groups.setdefault(blocks_sha(root, v, ops), []).append(v)
    reps = [vs[0] for s, vs in groups.items() if s != base_sha][:MAX_REPS]
    same = groups.get(base_sha, [])
    step = max(1, len(same) // max(1, probe)) if probe else 1
    reps += same[::step][:probe]
    tried = []
    base_runs = cand_runs = None
    if reps and not dry:
        base_runs = {s: short_curve(work, "base", s, _set_gate(base_p))
                     for s in SEEDS}
    for s, vs in groups.items():
        for v in vs:
            rec = {"params": v, "blocks_sha": s, "offline_same": s == base_sha,
                   "run": v in reps and not dry}
            if rec["run"]:
                tag = "v" + hashlib.sha1(json.dumps(v, sort_keys=True)
                                         .encode()).hexdigest()[:6]
                cand_runs = {sd: short_curve(work, tag, sd, _set_gate(v))
                             for sd in SEEDS}
                rec["judge"] = judge(base_runs, cand_runs)
            else:
                rec["judge"] = {"accepted": False, "note": "offline Δ0"
                                if s == base_sha else "not run (rep cap / dry)"}
            tried.append(rec)
    n = epoch if epoch is not None else max(
        [r.get("epoch", 0) for r in fm.load_ledger(root)
         if isinstance(r.get("epoch"), int)] + [0])
    accepted = [r for r in tried if r["judge"].get("accepted")]
    if write:
        best = accepted[0] if accepted else None
        for r in tried:
            oid = None
            if best is r:
                oid = f"gate_scan_{n}"
                live["status"] = "dormant"
                live["tried_env_hashes"].append(fm.env_hash(ops))
                ops.append(fm.new_op(oid, "gate", {"params": r["params"]},
                                     "gate-scan", n, status="live"))
                fm.write_ops(root, ops)
            fm.append_ledger(root, {
                "kind": "layer2", "epoch": n, "layer": 2, "by": "gate-scan",
                "scan": "gate", "op_ids": [oid] if oid else [],
                "variant": r["params"], "blocks_sha": r["blocks_sha"],
                "judge": r["judge"] | {"accepted": best is r}})
    return {"base": base_p, "base_sha": base_sha, "groups": len(groups),
            "variants": len(tried), "ran": 0 if dry else len(reps),
            "ran_offline_same": 0 if dry else sum(v in same for v in reps),
            "accepted": len(accepted), "tried": tried}


def route_variants(ops: list[dict]) -> list[tuple[str, dict]]:
    out = []
    for o in ops:
        if o["kind"] != "route" or o["status"] != "live":
            continue
        p = o["payload"]
        for d in (-1, 1):
            out.append((o["id"], {**p, "priority": p["priority"] + d}))
        for arm in fm.ROUTE_ARMS:
            if arm != p["arm"]:
                out.append((o["id"], {**p, "arm": arm}))
    return out


def _patch_route(oid: str, payload: dict):
    def patch(ops):
        for o in ops:
            if o["id"] == oid:
                o["payload"] = dict(payload)
        return ops
    return patch


def scan_route(root: Path, work: Path, write: bool = False,
               dry: bool = False) -> dict:
    """Route neighbourhood. Offline dedupe: a variant whose picked arm is the
    same as the base's for every stall state that fired in ``root`` is Δ0;
    the other groups (<= 4 representatives) get short curves."""
    from arcagi.hammer.route import pick_arm

    root, work = Path(root), Path(work)
    ops = fm.load_ops(root)
    fired = {r.get("state") for r in fm.load_ledger(root) if r["kind"] == "stall"}
    fired |= {(fm.read_json(p) or {}).get("stall")
              for p in (Path(root) / "epochs").glob("*/status.json")}
    fired = sorted(x for x in fired if x)

    def arms(table):
        return tuple(pick_arm(table, st) for st in fired)

    base_arms = arms(ops)
    groups: dict[tuple, list] = {}
    for oid, p in route_variants(ops):
        table = _patch_route(oid, p)(copy.deepcopy(ops))
        groups.setdefault(arms(table), []).append((oid, p))
    reps = [vs[0] for a, vs in groups.items() if a != base_arms][:MAX_REPS]
    base_runs = None
    if reps and not dry:
        base_runs = {s: short_curve(work, "rbase", s, lambda o: o) for s in SEEDS}
    tried = []
    for a, vs in groups.items():
        for oid, p in vs:
            rec = {"op": oid, "payload": p, "arms": dict(zip(fired, a)),
                   "run": (oid, p) in reps and not dry}
            if rec["run"]:
                tag = "r" + hashlib.sha1(json.dumps([oid, p], sort_keys=True)
                                         .encode()).hexdigest()[:6]
                cand = {sd: short_curve(work, tag, sd, _patch_route(oid, p))
                        for sd in SEEDS}
                rec["judge"] = judge(base_runs, cand)
            else:
                rec["judge"] = {"accepted": False, "note": "offline Δ0"
                                if a == base_arms else "not run (rep cap / dry)"}
            tried.append(rec)
    acc = [r for r in tried if r["judge"].get("accepted")]
    if write:
        n = max([r.get("epoch", 0) for r in fm.load_ledger(root)
                 if isinstance(r.get("epoch"), int)] + [0])
        best = acc[0] if acc else None
        for r in tried:
            oid = None
            if best is r:
                old = next(o for o in ops if o["id"] == r["op"])
                old["status"] = "dormant"
                old["tried_env_hashes"].append(fm.env_hash(ops))
                oid = f"{r['op']}_scan{n}"
                ops.append(fm.new_op(oid, "route", r["payload"], "gate-scan", n,
                                     status="live"))
                fm.write_ops(root, ops)
            fm.append_ledger(root, {
                "kind": "layer2", "epoch": n, "layer": 2, "by": "gate-scan",
                "scan": "route", "op_ids": [oid] if oid else [],
                "variant": {"op": r["op"], "payload": r["payload"]},
                "judge": r["judge"] | {"accepted": best is r}})
    return {"fired": fired, "base_arms": dict(zip(fired, base_arms)),
            "groups": len(groups), "variants": len(tried),
            "ran": 0 if dry else len(reps), "accepted": len(acc), "tried": tried}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="hammer layer-2 scan")
    ap.add_argument("root")
    ap.add_argument("--kind", choices=("gate", "route"), required=True)
    ap.add_argument("--work", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry", action="store_true",
                    help="offline replay only, no short curves")
    ap.add_argument("--probe", type=int, default=0,
                    help="also run N offline-Δ0 variants (dedupe check)")
    a = ap.parse_args(argv)
    if a.kind == "gate":
        work = Path(a.work or Path(a.root) / "tmp" / "scan")
        res = scan_gate(Path(a.root), work, a.write, a.dry, probe=a.probe)
    else:
        res = scan_route(Path(a.root), Path(a.work or Path(a.root) / "tmp" / "scan"),
                         a.write, a.dry)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
