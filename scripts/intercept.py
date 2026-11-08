"""C++-only re-run of the tasks Python claims to solve: count interceptions.

Usage: uv run python scripts/intercept.py <eval report.json> [traces.jsonl]
           --split {training,evaluation} [--budget 12] [--max-depth 4]
           [--workers 3] [--limit N] [--ext] > intercept.csv

Takes a native-hybrid (or plain search) eval report, picks the tasks whose
selected program came from Python (``scripts/attribution.py`` solver
``search``/``rewrite``) and runs only ``native/bin/arcsearch`` on them through
``native/tools/cpp_only.py`` (read-only use; its top-1 is the cheapest C++
solution, without the hybrid's vote or Python re-verification). Prints one CSV
row per task and, on stderr, how many Python-wrong tasks C++ gets right (the
interceptions), how many Python-right tasks C++ also gets right (overlap) and
how many it would break. ``attribution.py --cpp intercept.csv`` merges the
rows into its overlap summary.
"""

import argparse
import csv
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from attribution import load  # noqa: E402

FIELDS = [
    "task_id",
    "py_solver",
    "py_correct",
    "cpp_found",
    "cpp_correct",
    "cpp_program",
]


def _cpp_only():
    path = ROOT / "native" / "tools" / "cpp_only.py"
    spec = importlib.util.spec_from_file_location("cpp_only", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(rows, split, budget, depth, ext, workers):
    cpp = _cpp_only()

    def one(row):
        try:
            rec = cpp.solve(row["task_id"], split, budget, depth, ext)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            rec = {"n_solutions": 0, "correct": False, "program": f"error: {exc}"}
        return {
            "task_id": row["task_id"],
            "py_solver": row["solver"],
            "py_correct": row["correct"],
            "cpp_found": str(int(rec["n_solutions"] > 0)),
            "cpp_correct": str(int(bool(rec["correct"]))),
            "cpp_program": json.dumps(rec["program"]) if rec["program"] else "",
        }

    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, rows))


def summary(out) -> list[str]:
    def n(py, cpp):
        return sum(r["py_correct"] == py and r["cpp_correct"] == cpp for r in out)

    return [
        f"python-solved tasks rerun on C++: {len(out)}",
        f"python wrong: {sum(r['py_correct'] == '0' for r in out)}, "
        f"of which C++ right (interceptions): {n('0', '1')}",
        f"python right: {sum(r['py_correct'] == '1' for r in out)}, "
        f"C++ also right (overlap): {n('1', '1')}, C++ wrong: {n('1', '0')}",
        f"C++ found a train-fitting program: {sum(r['cpp_found'] == '1' for r in out)}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("report")
    parser.add_argument("traces", nargs="?")
    parser.add_argument("--split", required=True, choices=["training", "evaluation"])
    parser.add_argument("--budget", type=float, default=12.0)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ext", action="store_true")
    args = parser.parse_args(argv)
    rows = [
        r
        for r in load(args.report, args.traces)
        if r["solver"] in ("search", "rewrite")
    ]
    rows = rows[: args.limit] if args.limit else rows
    out = run(rows, args.split, args.budget, args.max_depth, args.ext, args.workers)
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(out)
    print("\n".join(summary(out)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
