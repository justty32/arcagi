"""Old-tree control curve: read-only calls into ``arcagi.solvers.search``.

pass 0 = a scratch blocks root holding only ``kind=primitive`` block folders
(``ARCAGI_BLOCKS``) and an empty pool (``ARCAGI_POOL``); pass >= 1 = a scratch
copy of the real ``aos/blocks/``. The registry is built at import time, so each
pass runs in a fresh subprocess. The old tree does not learn between passes.
search has a node cap (MAX_NODES = 100k) and a seconds budget; it does not
report a node count, so ``nodes`` and ``mean_prog_nodes`` stay empty.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BLOCKS = ROOT / "aos" / "blocks"


def primitive_root(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for meta in sorted(BLOCKS.glob("*/_metainfo.json")):
        if json.loads(meta.read_text()).get("kind") == "primitive":
            shutil.copytree(meta.parent, dest / meta.parent.name)
    return dest


def full_root(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(BLOCKS, dest)
    return dest


def _one(task_id: str) -> dict:
    from arcagi.solvers.search import solve
    from arcagi.tasks.io import load_task

    task = load_task(ROOT / "data/ARC-AGI/data/training" / f"{task_id}.json")
    t0 = time.perf_counter()
    res = solve(task.to_solver_task())
    trace = res.trace or {}
    train_ok = trace.get("selected") is not None
    preds = [tuple(tuple(r) for r in p) for p in res.predictions]
    want = [e.output for e in task.test]
    return {"task_id": task_id, "train_ok": train_ok,
            "test_ok": train_ok and preds == want,
            "seconds": round(time.perf_counter() - t0, 3)}


def worker_main(task_ids: list[str], workers: int) -> list[dict]:
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, task_ids))


def run_pass(task_ids: list[str], blocks_root: Path, pool_dir: Path | None,
             workers: int) -> tuple[list[dict], float]:
    env = dict(os.environ, ARCAGI_BLOCKS=str(blocks_root))
    if pool_dir is not None:
        env["ARCAGI_POOL"] = str(pool_dir)
    t0 = time.perf_counter()
    out = subprocess.run(
        [sys.executable, "-m", "arcagi.grow.oldtree", str(workers), *task_ids],
        env=env, check=True, capture_output=True, text=True,
    )
    wall = time.perf_counter() - t0
    return json.loads(out.stdout.strip().splitlines()[-1]), wall


if __name__ == "__main__":
    print(json.dumps(worker_main(sys.argv[2:], int(sys.argv[1]))))
