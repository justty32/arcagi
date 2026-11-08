"""Learning-curve loop: enumerate L16 -> verify -> G1 compress -> next pass.

H8 is measured every pass with the same solver but never feeds compression.
One row per pass: pass, solved_L, solved_H, wall_s, nodes, llm_calls,
lib_size, lib_bits, mean_prog_nodes. ``AUC_L`` = sum of solved_L over passes
1..8 (pass 0 is the starting tree before any learning).
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
from . import prog as pg
from .evolve import evolve
from .knobs import Knobs

ROOT = Path(__file__).resolve().parents[3]
TASKSET = ROOT / "data" / "r07" / "taskset.json"
COLUMNS = ["pass", "solved_L", "solved_H", "wall_s", "nodes", "llm_calls",
           "lib_size", "lib_bits", "mean_prog_nodes"]
BUDGET = 100_000
N_PASSES = 9  # pass 0 + 8 learning passes


@dataclass(frozen=True)
class Config:
    tree: str  # "empty" | "g1g4"
    knobs: Knobs = field(default_factory=Knobs)
    seed: int = 0
    passes: int = N_PASSES
    budget: int = BUDGET
    workers: int = 6
    learn: bool = True  # G1 on/off
    g4: bool = True  # G4 on/off


def load_taskset(path: Path = TASKSET) -> tuple[list, list]:
    data = json.loads(path.read_text())
    tdir = ROOT / "data" / "ARC-AGI" / "data" / "training"

    def get(entries):
        return [load_task(tdir / f"{e['task_id']}.json") for e in entries]

    return get(data["learn"]), get(data["holdout"])


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


def solve_task(args) -> dict:
    """Worker: one task under one library; enumerator then optional G4."""
    task, lib_path, budget, order, g4_frac, seed, lam_depth, donors = args
    _set_lam_depth(lam_depth)
    lib = backend.Library.load(lib_path)
    train = _pairs(task.train)
    test = _pairs(task.test)
    g4_budget = int(budget * g4_frac)
    t0 = time.perf_counter()
    res = backend.solve(train, lib, budget - g4_budget, order)
    nodes = res.nodes
    program, source = res.program, "enum"
    if program is None and g4_budget > 0:
        donor_progs = [pg.from_json(d) for d in donors]
        program, used, _ = evolve(task.task_id, train, list(res.near), lib,
                                  g4_budget, seed, donor_progs)
        nodes += used
        source = "g4"
    train_ok = program is not None and _check(program, train, lib)
    test_ok = train_ok and _check(program, test, lib)
    return {
        "task_id": task.task_id,
        "program": pg.to_json(program) if program is not None else None,
        "source": source if program is not None else None,
        "train_ok": train_ok,
        "test_ok": test_ok,
        "nodes": nodes,
        "nodes_to_first": res.nodes_to_first,
        "seconds": round(time.perf_counter() - t0, 3),
    }


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


def auc_l(rows: list[dict]) -> int:
    return sum(int(r["solved_L"]) for r in rows if int(r["pass"]) >= 1)


def run_curve(cfg: Config, out_dir: Path, lib_dir: Path, log=print) -> list[dict]:
    """Run the pass loop; write curve.csv, solutions.jsonl and blocks.json."""
    learn_set, hold_set = load_taskset()
    tasks = learn_set + hold_set
    learn_ids = {t.task_id for t in learn_set}
    out_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)
    assert lib_dir.resolve() != (ROOT / "aos" / "seedlib").resolve()
    lib_path = lib_dir / "blocks.json"
    params = g1.Params(m=cfg.knobs.m, k=cfg.knobs.k, max_holes=cfg.knobs.max_holes)
    g4_frac = cfg.knobs.g4_frac if cfg.g4 else 0.0
    blocks: list[dict] = []
    uses: dict[str, int] = {}
    rows: list[dict] = []
    sols_log = (out_dir / "solutions.jsonl").open("w")
    cache: dict[str, tuple[list[dict], float]] = {}
    n_prims = len(getattr(backend._seed, "PRIMS", {})) if hasattr(
        backend, "_seed") else 0
    with ProcessPoolExecutor(max_workers=cfg.workers) as pool:
        for pass_no in range(cfg.passes):
            _save_lib(blocks, lib_path)
            order = g1.order_from_uses(uses) if (
                cfg.learn and cfg.knobs.order == "prior" and uses) else None
            donors = sorted({json.dumps(s["program"]) for s in
                             (rows[-1]["_sols"] if rows else []) if s["test_ok"]
                             and s["task_id"] in learn_ids})
            ckey = hashlib.sha1(json.dumps(
                [lib_path.read_text(), order, g4_frac, cfg.seed, cfg.budget,
                 cfg.knobs.lam_depth, donors], sort_keys=True).encode()).hexdigest()
            t0 = time.perf_counter()
            if ckey in cache:  # identical inputs -> identical (deterministic) output
                sols, wall = cache[ckey]
            else:
                jobs = [(t, str(lib_path), cfg.budget, order, g4_frac, cfg.seed,
                         cfg.knobs.lam_depth, [json.loads(d) for d in donors])
                        for t in tasks]
                sols = list(pool.map(solve_task, jobs))
                wall = time.perf_counter() - t0
                cache[ckey] = (sols, wall)
            solved_l = {s["task_id"]: pg.from_json(s["program"]) for s in sols
                        if s["test_ok"] and s["task_id"] in learn_ids}
            solved_h = [s for s in sols
                        if s["test_ok"] and s["task_id"] not in learn_ids]
            sizes = [pg.size(p) for p in solved_l.values()]
            row = {
                "pass": pass_no, "solved_L": len(solved_l), "solved_H": len(solved_h),
                "wall_s": round(wall, 2), "nodes": sum(s["nodes"] for s in sols),
                "llm_calls": 0, "lib_size": len(blocks),
                "lib_bits": g1.lib_bits(blocks, n_prims),
                "mean_prog_nodes": round(sum(sizes) / len(sizes), 3) if sizes else None,
                "_sols": sols,
            }
            rows.append(row)
            for s in sols:
                row_json = json.dumps({"pass": pass_no, **s}, sort_keys=True)
                sols_log.write(row_json + "\n")
            log(f"[{cfg.tree} s{cfg.seed}] pass {pass_no}: L={row['solved_L']} "
                f"H={row['solved_H']} lib={len(blocks)} wall={wall:.1f}s")
            if cfg.learn:
                for p in solved_l.values():
                    for name in pg.ops(p):
                        uses[name] = uses.get(name, 0) + 1
                blocks, _ = g1.update(blocks, solved_l, params, pass_no)
    sols_log.close()
    _save_lib(blocks, lib_path)
    _save_lib(blocks, out_dir / "blocks.json")
    write_csv(rows, out_dir / "curve.csv")
    for r in rows:
        r.pop("_sols", None)
    return rows


def _save_lib(blocks: list[dict], path: Path) -> None:
    out = [{**b, "body": pg.to_json(b["body"])} for b in blocks]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
