"""The body: solve a batch of tasks under one library (arcbatch or Python).

``solve_batch`` returns one row per task with the fields of r08
``grow.curve.solve_task`` (task_id, program, source, train_ok, test_ok, nodes,
nodes_to_first, near_top, seconds, and gate_ok / mdl_ok / gate_nodes for
gated tasks). The native backend runs ``native/bin/arcbatch --mode seed``
(decomposition = the C++ port of the r07 seven splits); train_ok / test_ok
are always re-checked with the Python interpreter (``seed.interp``), so a
native mismatch can only lose a solve, never add one (counted in
``native_mismatch``). The leave-one-out gate re-search also runs through
arcbatch, one temporary task file per held-out pair.

The Python backend (``grow.curve.solve_task`` in a process pool) is needed
for the r08 split sets (halves / nest) and as the reference.
"""

import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from arcagi.grow import backend as gb
from arcagi.grow import curve as gc
from arcagi.grow import pool as pl
from arcagi.grow import prog as pg

ROOT = Path(__file__).resolve().parents[3]
ARCBATCH = ROOT / "native" / "bin" / "arcbatch"
TRAINING = ROOT / "data" / "ARC-AGI" / "data" / "training"
MAX_THREADS = 8
MAX_WORKERS = 6


@dataclass(frozen=True)
class BodyCfg:
    backend: str = "native"  # "native" | "python"
    decomp: bool = True  # r07 seven splits (C++ and Python alike)
    decomp_set: str = "default"  # python backend only: "default+halves" ...
    sub_lam_depth: int | None = None  # python backend only
    lam_depth: int = 2
    exclude: tuple[str, ...] = ()
    threads: int = 6
    gate: dict | None = None  # {"mdl_div", "loo_frac", "loo_min_pairs"}
    tmp_dir: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def load_tasks(ids) -> list:
    return gc._get_tasks(ids)


def _check(program, examples, lib) -> bool:
    return gc._check(program, examples, lib)


def _row(task, res: dict, lib) -> dict:
    """arcbatch output line -> r08 solve_task row, re-checked in Python."""
    train, test = gc._pairs(task.train), gc._pairs(task.test)
    program = pg.from_json(res["program"]) if res.get("program") is not None \
        else None
    train_ok = program is not None and _check(program, train, lib)
    test_ok = train_ok and _check(program, test, lib)
    mismatch = (program is not None and (train_ok != bool(res.get("train_ok"))
                                         or test_ok != bool(res.get("test_ok"))))
    near = res.get("near") or []
    out = {
        "task_id": task.task_id,
        "program": pg.to_json(program) if program is not None else None,
        "source": "enum" if program is not None else None,
        "train_ok": train_ok, "test_ok": test_ok,
        "nodes": int(res["nodes"]),
        "nodes_to_first": None if res.get("nodes_to_first") is None
        else int(res["nodes_to_first"]),
        "near_top": near[0][0] if near else None,
        "near_score": near[0][1] if near else None,
        "seconds": round(float(res.get("seconds", 0.0)), 3),
    }
    if mismatch:
        out["native_mismatch"] = True
    if res.get("error"):
        out["error"] = res["error"]
    return out


def _arcbatch(task_files: list[Path], cfg: BodyCfg, lib_path: Path, budget: int,
              order: dict | None, work: Path, tag: str) -> dict[str, dict]:
    """One arcbatch call; returns {task file stem: result line}."""
    lst = work / f"{tag}.list"
    lst.write_text("".join(f"{p}\n" for p in task_files))
    conf = work / f"{tag}.configs.jsonl"
    conf.write_text(json.dumps({
        "name": tag, "lib": str(lib_path), "budget": int(budget),
        "decomp": bool(cfg.decomp), "lam_depth": cfg.lam_depth,
        "exclude": list(cfg.exclude), "order": order or {}}) + "\n")
    out = work / f"{tag}.out.jsonl"
    threads = max(1, min(cfg.threads, MAX_THREADS))
    subprocess.run([str(ARCBATCH), "--mode", "seed", "--tasks", str(lst),
                    "--configs", str(conf), "--threads", str(threads),
                    "--out", str(out)], check=True, cwd=ROOT,
                   stdout=subprocess.DEVNULL)
    res = {}
    for ln in out.read_text().splitlines():
        r = json.loads(ln)
        if not r.get("summary"):
            res[r["task_id"]] = r
    return res


def _write_task(path: Path, train: list, test: list) -> Path:
    path.write_text(json.dumps({
        "train": [{"input": x, "output": y} for x, y in train],
        "test": [{"input": x, "output": y} for x, y in test]}))
    return path


def _native(tasks: list, lib_path: Path, budgets: dict[str, int], cfg: BodyCfg,
            order: dict | None, gate_ids: set[str]) -> list[dict]:
    lib = gb.Library.load(lib_path)
    tmp = Path(cfg.tmp_dir) if cfg.tmp_dir else None
    if tmp:
        tmp.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp) as wd:
        work = Path(wd)
        groups: dict[int, list] = {}
        for t in tasks:
            groups.setdefault(budgets[t.task_id], []).append(t)
        rows: dict[str, dict] = {}
        for b, ts in sorted(groups.items()):
            res = _arcbatch([TRAINING / f"{t.task_id}.json" for t in ts], cfg,
                            lib_path, b, order, work, f"main{b}")
            for t in ts:
                rows[t.task_id] = _row(t, res[t.task_id], lib)
        if cfg.gate is not None:
            _native_gate(tasks, rows, lib, lib_path, budgets, cfg, order,
                         gate_ids, work)
    return [rows[t.task_id] for t in tasks]


def _native_gate(tasks, rows, lib, lib_path, budgets, cfg, order, gate_ids, work):
    """MDL + leave-one-out gate (D-r8-6) with arcbatch re-searches.

    Same accounting as ``pool.loo_ok``: held-out pairs are tried in order and
    gate_nodes stops at the first failure.
    """
    g = cfg.gate
    pending: dict[int, list] = {}
    plan: dict[str, list] = {}
    for t in tasks:
        r = rows[t.task_id]
        if t.task_id not in gate_ids or not r["train_ok"]:
            continue
        train = gc._pairs(t.train)
        prog = pg.from_json(r["program"])
        mdl = pl.mdl_ok(prog, train, g["mdl_div"])
        r.update(mdl_ok=mdl, gate_ok=mdl, gate_nodes=0)
        if not mdl or len(train) < g["loo_min_pairs"]:
            continue
        b = int(budgets[t.task_id] * g["loo_frac"])
        plan[t.task_id] = []
        for i in range(len(train)):
            name = f"{t.task_id}__loo{i}"
            f = _write_task(work / f"{name}.json", train[:i] + train[i + 1:],
                            [train[i]])
            pending.setdefault(b, []).append(f)
            plan[t.task_id].append((name, train[i]))
    res: dict[str, dict] = {}
    for b, files in sorted(pending.items()):
        res.update(_arcbatch(files, cfg, lib_path, b, order, work, f"loo{b}"))
    for tid, items in plan.items():
        nodes, ok = 0, True
        for name, held in items:
            x = res[name]
            nodes += int(x["nodes"])
            p = pg.from_json(x["program"]) if x.get("program") is not None else None
            if p is None or not _check(p, [held], lib):
                ok = False
                break
        rows[tid].update(gate_ok=ok, gate_nodes=nodes)


def _python(tasks: list, lib_path: Path, budgets: dict[str, int], cfg: BodyCfg,
            order: dict | None, gate_ids: set[str]) -> list[dict]:
    base = {"lib_path": str(lib_path), "seed": 0, "lam_depth": cfg.lam_depth,
            "exclude": tuple(cfg.exclude), "decomp": cfg.decomp,
            "decomp_set": cfg.decomp_set, "sub_lam_depth": cfg.sub_lam_depth,
            "mdl_div": (cfg.gate or {}).get("mdl_div", pl.MDL_DIV),
            "order": order, "g4_frac": 0.0, "donors": [], "n_orig": None}
    jobs = [{**base, "task": t, "budget": budgets[t.task_id],
             "gate": cfg.gate is not None and t.task_id in gate_ids}
            for t in tasks]
    workers = max(1, min(cfg.threads, MAX_WORKERS))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(gc.solve_task, jobs, chunksize=1))


def solve_batch(tasks: list, lib_path: Path, budget, cfg: BodyCfg,
                order: dict | None = None, gate_ids=()) -> list[dict]:
    """Solve ``tasks`` (Task objects) under ``lib_path``.

    ``budget``: int, or {task_id: int}. ``gate_ids``: tasks that get the
    MDL + LOO gate (only when ``cfg.gate`` is set).
    """
    budgets = budget if isinstance(budget, dict) else \
        {t.task_id: int(budget) for t in tasks}
    if not tasks:
        return []
    fn = _native if cfg.backend == "native" else _python
    return fn(tasks, Path(lib_path), budgets, cfg, order, set(gate_ids))


def run(rows: list[dict]) -> list[dict]:
    """Node entry (``arcagi.hammer.body:run``): job rows -> solution rows.

    A job row: {"task_id", "budget", "lib", "cfg": BodyCfg fields,
    "order": {...} | null, "gate": bool}. Rows with the same lib / cfg /
    order run as one batch; output keeps the input order.
    """
    groups: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        k = json.dumps([r["lib"], r.get("cfg", {}), r.get("order")], sort_keys=True)
        groups.setdefault(k, []).append(i)
    out: list[dict | None] = [None] * len(rows)
    for idx in groups.values():
        r0 = rows[idx[0]]
        c = dict(r0.get("cfg", {}))
        c["exclude"] = tuple(c.get("exclude", ()))
        cfg = BodyCfg(**c)
        tasks = load_tasks([rows[i]["task_id"] for i in idx])
        budgets = {rows[i]["task_id"]: int(rows[i]["budget"]) for i in idx}
        gate = {rows[i]["task_id"] for i in idx if rows[i].get("gate")}
        res = solve_batch(tasks, Path(r0["lib"]), budgets, cfg, r0.get("order"),
                          gate)
        for i, s in zip(idx, res, strict=True):
            out[i] = s
    return [o for o in out if o is not None]


def timed(fn, *a, **kw):
    t0 = time.perf_counter()
    out = fn(*a, **kw)
    return out, time.perf_counter() - t0


__all__ = ["BodyCfg", "solve_batch", "run", "load_tasks", "os"]
