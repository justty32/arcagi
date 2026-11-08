"""C++-only top-1 check on tasks with known test outputs (training dev loop).

Runs ``arcsearch`` per task, executes the cheapest solution on the test inputs
with ``arcsearch --run`` and compares with the stored outputs. No Python
verification, so primitives not yet in the Python registry (``--ext``) work.

    python native/tools/cpp_only.py IDS.txt --split training --budget 12 [--ext] \
        --out R.json
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcsearch"


def task_background(grids):
    total, border = {}, {}
    for grid in grids:
        h, w = len(grid), len(grid[0])
        for y, row in enumerate(grid):
            for x, c in enumerate(row):
                total[c] = total.get(c, 0) + 1
                if y in (0, h - 1) or x in (0, w - 1):
                    border[c] = border.get(c, 0) + 1
    top = max(total.values())
    tied = [c for c, n in total.items() if n == top]
    return max(tied, key=lambda c: (border.get(c, 0), c == 0, -c))


def solve(task_id, split, budget, depth, ext, spec=None):
    task = json.loads(
        (ROOT / "data/ARC-AGI/data" / split / f"{task_id}.json").read_text()
    )
    request = {
        "task_id": task_id,
        "task": {
            "train": task["train"],
            "test": [{"input": t["input"]} for t in task["test"]],
        },
    }
    flags = ["--ext"] if ext else []
    if spec:
        flags += ["--spec", spec]
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        req, out = Path(tmp, "r.json"), Path(tmp, "o.json")
        req.write_text(json.dumps(request))
        subprocess.run(
            [
                str(BIN),
                *flags,
                "--request",
                str(req),
                "--out",
                str(out),
                "--budget",
                str(budget),
                "--max-depth",
                str(depth),
            ],
            check=True,
            timeout=budget + 30,
        )
        result = json.loads(out.read_text())
    sols = sorted(result["solutions"], key=lambda s: s["cost"])
    record = {
        "task_id": task_id,
        "correct": False,
        "program": None,
        "n_solutions": len(sols),
        "elapsed": time.perf_counter() - started,
        "depth": result["stats"]["depth_reached"],
    }
    if not sols:
        return record
    bg = task_background([g for e in task["train"] for g in (e["input"], e["output"])])
    lines = "".join(
        json.dumps({"program": sols[0]["program"], "grid": t["input"], "bg": bg}) + "\n"
        for t in task["test"]
    )
    ran = subprocess.run(
        [str(BIN), *flags, "--run"],
        input=lines,
        capture_output=True,
        text=True,
        check=True,
    )
    outs = [json.loads(line).get("out") for line in ran.stdout.splitlines()]
    record["program"] = sols[0]["program"]
    record["correct"] = all(
        o == t["output"] for o, t in zip(outs, task["test"], strict=True)
    )
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids")
    parser.add_argument("--split", default="training")
    parser.add_argument("--budget", type=float, default=12.0)
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--ext", action="store_true")
    parser.add_argument("--spec", help="spec.json to use instead of native/spec.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    ids = [
        line.split()[0]
        for line in Path(args.ids).read_text().splitlines()
        if line.strip()
    ]
    with ThreadPoolExecutor(args.workers) as pool:
        records = list(
            pool.map(
                lambda t: solve(
                    t, args.split, args.budget, args.max_depth, args.ext, args.spec
                ),
                ids,
            )
        )
    Path(args.out).write_text(json.dumps(records, indent=1) + "\n")
    print(
        f"{sum(r['correct'] for r in records)}/{len(records)} correct, "
        f"{sum(r['n_solutions'] > 0 for r in records)} with a train-fitting program",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
