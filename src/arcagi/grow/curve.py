"""Learning-curve loop: enumerate L16 -> verify -> G1 compress -> next pass.

H8 (and r08 H24) are measured every pass with the same solver but never feed
compression. One row per pass (COLUMNS). ``AUC_L`` = sum of solved_L over
passes 1..8 (pass 0 is the starting tree before any learning).

r08 (``grow.pool``): practice pool P searched every pass with a growing
budget, never scored; with ``gate="loo"`` both L16 and P programs feed G1 only
through the train-only leave-one-out + MDL gate (D-r8-6). ``gate="r07"`` keeps
the r07 rule (test-correct L16 programs feed G1) for the control curve.
"""

import csv
import hashlib
import io
import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from arcagi.tasks.io import load_task

from . import backend
from . import compress as g1
from . import pool as pl
from . import prog as pg
from .evolve import evolve
from .knobs import Knobs

ROOT = Path(__file__).resolve().parents[3]
TASKSET = ROOT / "data" / "r07" / "taskset.json"
TASKSET_R08 = ROOT / "data" / "r08" / "taskset.json"
COLUMNS = ["pass", "solved_L", "solved_H", "wall_s", "nodes", "llm_calls",
           "lib_size", "lib_bits", "mean_prog_nodes", "nodes_solved",
           "solved_P", "clean_P", "budget_P", "lib_from_P", "logcost_L",
           "solved_H24", "nodes_total", "false_pos", "synth_ok"]
COLD_START = 2  # G1 cold start while the G1 feed has <= this programs (D-r7-10)
COLD_K = 1.0
BUDGET = 100_000
N_PASSES = 9  # pass 0 + 8 learning passes


@dataclass(frozen=True)
class Config:
    tree: str
    knobs: Knobs = field(default_factory=Knobs)
    seed: int = 0
    passes: int = N_PASSES
    budget: int = BUDGET
    workers: int = 6
    learn: bool = True  # G1 on/off
    g4: bool = True  # G4 on/off (scored tasks only; P is enumeration only)
    exclude: tuple[str, ...] = ()  # primitives removed from the enumerator
    taskset: Path = TASKSET
    gate: str = "r07"  # "r07": test-right L16 feeds G1; "loo": D-r8-6 gate
    pool: str = ""  # practice pool: "" | "all" (themed P32) | "rand32" | "foot32"
    pool_budget0: int = 25_000
    pool_cap: int = 400_000
    pool_frac: float = 1.0  # CRN subset share of P (D-r8-3)
    h24: bool = False  # measure H24
    retire_after: int = g1.RETIRE_AFTER
    mdl_div: float = pl.MDL_DIV  # MDL gate divisor (r08 first runs: 4)


def _get_tasks(ids) -> list:
    tdir = ROOT / "data" / "ARC-AGI" / "data" / "training"
    return [load_task(tdir / f"{tid}.json") for tid in ids]


def load_taskset(path: Path = TASKSET) -> tuple[list, list]:
    data = json.loads(path.read_text())
    return (_get_tasks(e["task_id"] for e in data["learn"]),
            _get_tasks(e["task_id"] for e in data["holdout"]))


def _lists(grid):
    return [list(r) for r in grid]


def _pairs(examples):
    return [(_lists(e.input), _lists(e.output)) for e in examples]


def _check(program, examples, lib) -> bool:
    try:
        return all(
            pg.norm(backend.run(program, x, lib)) == pg.norm(y) for x, y in examples
        )
    except backend.EvalError:
        return False
    except RecursionError:
        return False


def _set_lam_depth(depth: int) -> None:
    if backend.ENGINE != "seed":
        return
    from arcagi.seed import enum as _enum
    from arcagi.seed import lam as _lam

    for mod in (_enum, _lam):  # runtime knob, the seed sources stay untouched
        if hasattr(mod, "LAM_DEPTH"):
            mod.LAM_DEPTH = depth


def solve_task(job: dict) -> dict:
    """Worker: one task under one library; enumerator, optional G4, then the
    optional G1 gate and S5 audit."""
    task = job["task"]
    _set_lam_depth(job["lam_depth"])
    lib = backend.Library.load(job["lib_path"])
    train = _pairs(task.train)
    test = _pairs(task.test)
    budget = job["budget"]
    g4_budget = int(budget * job["g4_frac"])
    enum_budget = budget - g4_budget

    def search(pairs, b):
        with backend.prims.without(*job["exclude"]):  # ablation, e.g. empty-noT
            return backend.solve_with(pairs, lib, b, job["order"], job["decomp"],
                                      job["decomp_set"], job["sub_lam_depth"])

    t0 = time.perf_counter()
    res = search(train, enum_budget)
    nodes = res.nodes
    program, source = res.program, "enum"
    if program is None and g4_budget > 0:
        donor_progs = [pg.from_json(d) for d in job["donors"]]
        program, used, _ = evolve(task.task_id, train, list(res.near), lib,
                                  g4_budget, job["seed"], donor_progs)
        nodes += used
        source = "g4"
    train_ok = program is not None and _check(program, train, lib)
    test_ok = train_ok and _check(program, test, lib)
    out = {
        "task_id": task.task_id,
        "program": pg.to_json(program) if program is not None else None,
        "source": source if program is not None else None,
        "train_ok": train_ok,
        "test_ok": test_ok,
        "nodes": nodes,
        "nodes_to_first": res.nodes_to_first if source == "enum" else nodes,
        "near_top": pg.to_json(res.near[0][0]) if res.near else None,
    }
    if job["gate"] and train_ok:
        def research(pairs):
            r = search(pairs, enum_budget // 4)
            return r.program, r.nodes

        mdl = pl.mdl_ok(program, train, job["mdl_div"])
        loo, gate_nodes = pl.loo_ok(train, research,
                                    lambda p, ex: _check(p, ex, lib)) if mdl \
            else (False, 0)
        out.update(gate_ok=mdl and loo, mdl_ok=mdl, gate_nodes=gate_nodes)
    if job["n_orig"] is not None and train_ok:  # audit only, never a filter
        pairs = pl.synth_pairs(task.task_id, job["n_orig"])
        ok = sum(_check(program, [e], lib) for e in pairs)
        out.update(synth_n=len(pairs), synth_ok=ok)
    out["seconds"] = round(time.perf_counter() - t0, 3)
    return out


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    for r in rows:
        w.writerow([_fmt(r.get(c)) for c in COLUMNS])
    path.write_text(buf.getvalue())


def curve_sha(path: Path) -> str:
    """sha1 of curve.csv with the wall_s column blanked (seconds never repeat)."""
    rows = list(csv.reader(path.read_text().splitlines()))
    i = rows[0].index("wall_s")
    for r in rows[1:]:
        r[i] = ""
    return hashlib.sha1("\n".join(",".join(r) for r in rows).encode()).hexdigest()


def delta(rows: list[dict]) -> int:
    """solved_L(last pass) - solved_L(pass 0)."""
    return int(rows[-1]["solved_L"]) - int(rows[0]["solved_L"])


def auc_l(rows: list[dict]) -> int:
    return sum(int(r["solved_L"]) for r in rows if int(r["pass"]) >= 1)


def run_curve(cfg: Config, out_dir: Path, lib_dir: Path, log=print) -> list[dict]:
    """Run the pass loop; write curve.csv, solutions.jsonl and blocks.json.

    Returned rows also carry ``_tcost`` ({task: capped log2 cost} over L16 and
    H24) for the r08 paired bootstrap.
    """
    learn_set, hold_set = load_taskset(cfg.taskset)
    h24_set = _get_tasks(pl.h24_ids(cfg.taskset)) if cfg.h24 else []
    practice = _get_tasks(pl.practice_ids(cfg.taskset, cfg.pool, cfg.seed,
                                          cfg.pool_frac))
    tasks = learn_set + hold_set + h24_set
    learn_ids = {t.task_id for t in learn_set}
    h24_ids = {t.task_id for t in h24_set}
    pool_ids = {t.task_id for t in practice}
    n_orig = pl.synth_n_original() if practice else {}
    loo = cfg.gate == "loo"
    out_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)
    assert lib_dir.resolve() != (ROOT / "aos" / "seedlib").resolve()
    lib_path = lib_dir / "blocks.json"
    params = g1.Params(m=cfg.knobs.m, k=cfg.knobs.k, max_holes=cfg.knobs.max_holes)
    g4_frac = cfg.knobs.g4_frac if cfg.g4 else 0.0
    blocks: list[dict] = []
    born: list[dict] = []
    uses: dict[str, int] = {}
    rows: list[dict] = []
    cost0: dict[str, float] = {}
    donors: list = []
    sols_log = (out_dir / "solutions.jsonl").open("w")
    n_prims = len(getattr(backend._seed, "PRIMS", {})) if hasattr(
        backend, "_seed") else 0
    base_job = {"lib_path": str(lib_path), "seed": cfg.seed,
                "lam_depth": cfg.knobs.lam_depth, "exclude": tuple(cfg.exclude),
                "decomp": cfg.knobs.decomp, "decomp_set": cfg.knobs.decomp_set,
                "sub_lam_depth": cfg.knobs.sub_lam_depth, "mdl_div": cfg.mdl_div}
    with ProcessPoolExecutor(max_workers=cfg.workers) as ex:
        for pass_no in range(cfg.passes):
            _save_lib(blocks, lib_path)
            order = g1.order_from_uses(uses) if (
                cfg.learn and cfg.knobs.order == "prior" and uses) else None
            b_p = pl.budget(cfg.pool_budget0, cfg.knobs.budget_mult, cfg.pool_cap,
                            pass_no) if practice else None
            t0 = time.perf_counter()  # every pass re-searches every task
            jobs = [{**base_job, "task": t, "budget": cfg.budget, "order": order,
                     "g4_frac": g4_frac, "donors": donors,
                     "gate": loo and t.task_id in learn_ids, "n_orig": None}
                    for t in tasks]
            jobs += [{**base_job, "task": t, "budget": b_p, "order": order,
                      "g4_frac": 0.0, "donors": [], "gate": loo,
                      "n_orig": n_orig.get(t.task_id, 0)} for t in practice]
            sols_all = list(ex.map(solve_task, jobs, chunksize=1))
            wall = time.perf_counter() - t0
            by_id = {s["task_id"]: s for s in sols_all}
            sols = sols_all[:len(learn_set) + len(hold_set)]
            psols = sols_all[len(tasks):]
            solved_l = {s["task_id"]: pg.from_json(s["program"]) for s in sols
                        if s["test_ok"] and s["task_id"] in learn_ids}
            if loo:  # train-only gate for L16 and P alike (D-r8-6)
                feed = {s["task_id"]: pg.from_json(s["program"]) for s in sols_all
                        if s.get("gate_ok")}
            else:
                feed = dict(solved_l)
            fed = [by_id[t] for t in feed]
            sizes = [pg.size(p) for p in solved_l.values()]
            tcost = {}
            for tid in sorted(learn_ids | h24_ids):
                s = by_id[tid]
                c = pl.task_cost(s["nodes_to_first"], s["test_ok"], cfg.budget)
                if pass_no == 0:
                    cost0[tid] = c
                tcost[tid] = round(pl.capped(c, cost0.get(tid), cfg.budget), 4)
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
                "solved_P": sum(s["train_ok"] for s in psols) if practice else None,
                "clean_P": sum(t in pool_ids for t in feed) if practice else None,
                "budget_P": b_p,
                "lib_from_P": sum(any(t in pool_ids for t in b["src_tasks"])
                                  for b in blocks) if practice else None,
                "logcost_L": round(sum(tcost[t] for t in sorted(learn_ids)), 3),
                "solved_H24": sum(by_id[t]["test_ok"] for t in h24_ids)
                if cfg.h24 else None,
                "nodes_total": sum(s["nodes"] + s.get("gate_nodes", 0)
                                   for s in sols_all),
                "false_pos": sum(not s["test_ok"] for s in fed) if loo else None,
                "synth_ok": sum(s.get("synth_ok", 0) * 2 >= s.get("synth_n", 1)
                                for s in fed if s["task_id"] in pool_ids)
                if practice else None,
                "_tcost": tcost,
            }
            rows.append(row)
            for s in sols_all:
                part = ("P" if s["task_id"] in pool_ids else
                        "L" if s["task_id"] in learn_ids else
                        "H24" if s["task_id"] in h24_ids else "H")
                sols_log.write(json.dumps({"pass": pass_no, "set": part, **s},
                                          sort_keys=True) + "\n")
            log(f"[{cfg.tree} s{cfg.seed}] pass {pass_no}: L={row['solved_L']} "
                f"H={row['solved_H']} H24={row['solved_H24']} "
                f"P={row['solved_P']}/{row['clean_P']} lib={len(blocks)} "
                f"logcost={row['logcost_L']} wall={wall:.1f}s")
            # G4 donors: the next pass's subtrees come from the G1 feed only
            donors = [json.loads(d) for d in sorted(
                {json.dumps(pg.to_json(p)) for t, p in feed.items()
                 if t in learn_ids})]
            if cfg.learn:
                for p in feed.values():
                    for name in pg.ops(p):
                        uses[name] = uses.get(name, 0) + 1
                extra = {}
                p_now = params
                if len(feed) <= COLD_START:  # cold start: near misses, k=1
                    extra = {f"{s['task_id']}~near": pg.from_json(s["near_top"])
                             for s in sols if s["task_id"] in learn_ids
                             and s["task_id"] not in feed and s["near_top"]}
                    p_now = g1.Params(m=params.m, k=COLD_K,
                                      max_holes=params.max_holes)
                blocks, added = g1.update(blocks, feed, p_now, pass_no, extra,
                                          cap=cfg.knobs.lib_cap,
                                          retire_after=cfg.retire_after)
                born += added
    sols_log.close()
    _save_lib(blocks, lib_path)
    _save_lib(blocks, out_dir / "blocks.json")
    _save_lib(born, out_dir / "blocks_born.json")
    write_csv(rows, out_dir / "curve.csv")
    for r in rows:
        r.pop("_sols", None)
    return rows


def _save_lib(blocks: list[dict], path: Path) -> None:
    out = [{**b, "body": pg.to_json(b["body"])} for b in blocks]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
