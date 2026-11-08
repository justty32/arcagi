"""Differential tests: C++ seed mode (arcbatch --mode seed / seed-run) against
the Python reference src/arcagi/seed (read-only).

    # Python side of a solve run (same fields as arcbatch --mode seed)
    python native/tools/seed_parity.py solve --tasks IDS.txt --budget 100000 \
        [--decomp] [--lam-depth 2] [--exclude transpose] [--lib blocks.json] \
        [--workers 6] --out py.jsonl
    python native/tools/seed_parity.py compare py.jsonl cpp.jsonl

    # evaluator: Python enumerator bank programs x every train/test input
    python native/tools/seed_parity.py evalgen --tasks IDS.txt --per-task 400 \
        --out jobs.jsonl --expect expect.jsonl
    native/bin/arcbatch --mode seed-run --programs jobs.jsonl --out got.jsonl
    python native/tools/seed_parity.py evalcmp expect.jsonl got.jsonl

IDS.txt: one training task id per line. ``ids`` writes the standard sets
(r07 taskset learn+holdout, and the rest of training as the pool).
"""

import argparse
import json
import multiprocessing
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from arcagi.seed import enum as S_enum  # noqa: E402
from arcagi.seed import interp, lam, prims  # noqa: E402
from arcagi.seed.library import Library  # noqa: E402

DATA = ROOT / "data" / "ARC-AGI" / "data" / "training"
if not DATA.is_dir():  # a git worktree without the data submodule
    DATA = Path.home() / "repo" / "arcagi" / "data" / "ARC-AGI" / "data" / "training"


def load(tid):
    return json.loads((DATA / f"{tid}.json").read_text())


def read_ids(path):
    return [w.split()[0] for w in Path(path).read_text().splitlines()
            if w.strip() and not w.startswith("#")]


def _pairs(exs):
    return [(e["input"], e.get("output")) for e in exs]


def _check(prog, exs, lib):
    if not exs:
        return False
    for x, y in exs:
        if y is None:
            return False
        try:
            if interp.run(prog, x, lib) != interp.to_value(y):
                return False
        except interp.EvalError:
            return False
    return True


def _solve_one(job):
    tid, budget, decomp, lam_depth, exclude, lib_path, order = job
    lam.LAM_DEPTH = lam_depth
    lib = Library.load(lib_path) if lib_path else Library()
    t = load(tid)
    train, test = _pairs(t["train"]), _pairs(t["test"])
    t0 = time.perf_counter()
    err = None
    try:
        with prims.without(*exclude):
            res = S_enum.solve(train, lib, budget, order, decompose=decomp)
    except Exception as e:  # noqa: BLE001 - recorded, compared with C++ "error"
        err = f"{type(e).__name__}: {e}"
        res = None
    secs = time.perf_counter() - t0
    if res is None:
        return {"task_id": tid, "program": None, "error": err, "seconds": secs}
    prog = res.program
    ok_train = prog is not None and _check(prog, train, lib)
    ok_test = ok_train and _check(prog, test, lib)
    return {
        "task_id": tid,
        "program": interp.to_json(prog) if prog is not None else None,
        "train_ok": ok_train, "test_ok": ok_test,
        "nodes": res.nodes, "nodes_to_first": res.nodes_to_first,
        "near": [[interp.to_json(p), s] for p, s in res.near],
        "seconds": secs,
    }


def cmd_solve(a):
    ids = read_ids(a.tasks)
    order = json.loads(a.order) if a.order else None
    jobs = [(t, a.budget, a.decomp, a.lam_depth, tuple(a.exclude), a.lib, order) for t in ids]
    t0 = time.perf_counter()
    with multiprocessing.get_context("fork").Pool(a.workers) as pool:
        rows = pool.map(_solve_one, jobs, chunksize=1)
    wall = time.perf_counter() - t0
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        f.write(json.dumps({"summary": True, "wall_seconds": wall, "workers": a.workers,
                            "solved": sum(bool(r.get("test_ok")) for r in rows),
                            "nodes": sum(r.get("nodes") or 0 for r in rows),
                            "task_seconds": sum(r["seconds"] for r in rows)}) + "\n")
    print(f"python: {len(rows)} tasks, wall {wall:.2f}s, workers {a.workers}")


FIELDS = ("program", "train_ok", "test_ok", "nodes", "nodes_to_first", "near")


def _rows(path, config=None):
    out = {}
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        if r.get("summary") or (config and r.get("config") not in (None, config)):
            continue
        out[r["task_id"]] = r
    return out


def cmd_compare(a):
    py, cc = _rows(a.py), _rows(a.cpp, a.config)
    bad = 0
    for tid, r in py.items():
        c = cc.get(tid)
        if c is None:
            print(f"{tid}: missing in C++")
            bad += 1
            continue
        if r.get("error") or c.get("error"):
            if bool(r.get("error")) != bool(c.get("error")):
                print(f"{tid}: error py={r.get('error')} cpp={c.get('error')}")
                bad += 1
            continue
        diffs = [k for k in FIELDS if r.get(k) != c.get(k)]
        if diffs:
            bad += 1
            print(f"{tid}: differs in {diffs}")
            for k in diffs[:2]:
                print(f"   py : {json.dumps(r.get(k))[:300]}")
                print(f"   cpp: {json.dumps(c.get(k))[:300]}")
    print(f"compared {len(py)} tasks: {len(py) - bad} identical, {bad} differ")
    return 1 if bad else 0


def cmd_evalgen(a):
    """Bank programs of the plain Python enumerator (first K and a random
    sample of the rest), with every train/test input of the task."""
    rng = random.Random(0)
    ids = read_ids(a.tasks)
    jobs = open(a.out, "w")
    exp = open(a.expect, "w")
    n = 0
    for tid in ids:
        t = load(tid)
        train = _pairs(t["train"])
        en = S_enum.Enumerator(train, Library(), a.budget)
        S_enum.search(en)
        progs = [e.prog for level in en.bank for es in level.values() for e in es]
        pick = progs[: a.per_task // 2]
        rest = progs[a.per_task // 2:]
        pick += rng.sample(rest, min(len(rest), a.per_task - len(pick)))
        inputs = [e["input"] for e in t["train"] + t["test"]]
        for p in pick:
            vals = []
            for x in inputs:
                try:
                    vals.append(_norm(interp.run(p, x)))
                except interp.EvalError:
                    vals.append("ERR")
            jid = f"{tid}:{n}"
            n += 1
            jobs.write(json.dumps({"id": jid, "program": interp.to_json(p), "inputs": inputs}) + "\n")
            exp.write(json.dumps({"id": jid, "values": vals}) + "\n")
    print(f"{n} programs from {len(ids)} tasks")


def _norm(v):
    if isinstance(v, tuple):
        return [_norm(x) for x in v]
    if callable(v):
        return "<function>"
    return v


def cmd_evalcmp(a):
    exp = {json.loads(x)["id"]: json.loads(x)["values"] for x in Path(a.expect).read_text().splitlines()}
    got = {json.loads(x)["id"]: json.loads(x)["values"] for x in Path(a.got).read_text().splitlines()}
    bad = cells = 0
    for k, v in exp.items():
        g = got.get(k)
        cells += len(v)
        if g != v or any(type(x) is not type(y) for x, y in zip(_flat(v), _flat(g or []))):
            bad += 1
            if bad <= 10:
                print(f"{k}: py {json.dumps(v)[:200]} cpp {json.dumps(g)[:200]}")
    print(f"{len(exp)} programs, {cells} (program, input) values: {bad} programs differ")
    return 1 if bad else 0


def _flat(v):
    if isinstance(v, list):
        for x in v:
            yield from _flat(x)
    else:
        yield v


def cmd_ids(a):
    ts = json.loads((ROOT / "data" / "r07" / "taskset.json").read_text())
    lh = [e["task_id"] for e in ts["learn"] + ts["holdout"]]
    pool = sorted(p.stem for p in DATA.glob("*.json") if p.stem not in set(lh))
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    (Path(a.out_dir) / "lh24.txt").write_text("\n".join(lh) + "\n")
    (Path(a.out_dir) / "pool.txt").write_text("\n".join(pool) + "\n")
    print(f"lh24 {len(lh)}, pool {len(pool)}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solve")
    s.add_argument("--tasks", required=True)
    s.add_argument("--budget", type=int, default=100000)
    s.add_argument("--decomp", action="store_true")
    s.add_argument("--lam-depth", type=int, default=2)
    s.add_argument("--exclude", nargs="*", default=[])
    s.add_argument("--lib", default="")
    s.add_argument("--order", default="")
    s.add_argument("--workers", type=int, default=6)
    s.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("py")
    c.add_argument("cpp")
    c.add_argument("--config")
    g = sub.add_parser("evalgen")
    g.add_argument("--tasks", required=True)
    g.add_argument("--per-task", type=int, default=400)
    g.add_argument("--budget", type=int, default=20000)
    g.add_argument("--out", required=True)
    g.add_argument("--expect", required=True)
    e = sub.add_parser("evalcmp")
    e.add_argument("expect")
    e.add_argument("got")
    i = sub.add_parser("ids")
    i.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    if getattr(a, "workers", 1) > 6:
        sys.exit("workers <= 6")
    return {"solve": cmd_solve, "compare": cmd_compare, "evalgen": cmd_evalgen,
            "evalcmp": cmd_evalcmp, "ids": cmd_ids}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
