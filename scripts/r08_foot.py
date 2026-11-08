"""Foothold probe for the D-r8-18 practice pool -> data/r08/foot_pass0.json.

One pass-0 search (empty library, DEFAULT splits, 100k nodes) over every
training task outside L16 / H8 / H24. Only ``train_ok`` is recorded: no test
answers, no S5 pairs. ``scripts/r08_taskset.py`` turns it into pool_foot32.

    nice -n 19 systemd-run --user --scope -q -p MemoryMax=16G \
        uv run python scripts/r08_foot.py
"""

import json
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from arcagi.grow import backend, curve

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "r08" / "foot_pass0.json"
BUDGET = 100_000


def _one(args) -> dict:
    task, lib_path = args
    lib = backend.Library.load(lib_path)
    train = curve._pairs(task.train)
    res = backend.solve_with(train, lib, BUDGET, None, True)
    ok = res.program is not None and curve._check(res.program, train, lib)
    return {"task_id": task.task_id, "train_ok": ok, "nodes": res.nodes}


def main() -> None:
    data = json.loads(curve.TASKSET_R08.read_text())
    used = {e["task_id"] for k in ("learn", "holdout", "holdout24") for e in data[k]}
    tdir = ROOT / "data/ARC-AGI/data/training"
    ids = sorted(p.stem for p in tdir.glob("*.json") if p.stem not in used)
    tasks = curve._get_tasks(ids)
    with tempfile.TemporaryDirectory() as tmp:
        lib_path = Path(tmp) / "blocks.json"
        lib_path.write_text("[]\n")
        with ProcessPoolExecutor(max_workers=8) as ex:
            rows = list(ex.map(_one, [(t, str(lib_path)) for t in tasks],
                               chunksize=1))
    OUT.write_text(json.dumps({"budget": BUDGET, "splits": "default",
                               "tasks": rows}, indent=1, sort_keys=True) + "\n")
    print(OUT, len(rows), sum(r["train_ok"] for r in rows))


if __name__ == "__main__":
    main()
