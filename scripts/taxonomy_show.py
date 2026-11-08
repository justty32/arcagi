"""Print ARC tasks as compact text grids for labelling (one digit per cell, '.' for 0).

Usage: python3 scripts/taxonomy_show.py TASK_ID [TASK_ID ...] [--max-pairs N]
Test outputs are never printed.
"""

import argparse
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "ARC-AGI" / "data"


def find(task_id: str) -> tuple[str, dict]:
    for split in ("training", "evaluation"):
        p = DATA / split / f"{task_id}.json"
        if p.exists():
            return split, json.loads(p.read_text())
    raise SystemExit(f"unknown task {task_id}")


def render(g: list[list[int]]) -> list[str]:
    return ["".join("." if v == 0 else str(v) for v in row) for row in g]


def side_by_side(a: list[str], b: list[str]) -> str:
    wa = max(len(r) for r in a)
    lines = []
    for i in range(max(len(a), len(b))):
        left = a[i] if i < len(a) else ""
        right = b[i] if i < len(b) else ""
        lines.append(f"{left.ljust(wa)}   {right}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--max-pairs", type=int, default=4)
    args = ap.parse_args()
    for tid in args.ids:
        split, task = find(tid)
        print(
            f"=== {tid} ({split}) train={len(task['train'])} test={len(task['test'])}"
        )
        for k, p in enumerate(task["train"][: args.max_pairs]):
            a, b = p["input"], p["output"]
            print(f"-- pair {k}: {len(a)}x{len(a[0])} -> {len(b)}x{len(b[0])}")
            print(side_by_side(render(a), render(b)))
        for k, p in enumerate(task["test"]):
            a = p["input"]
            print(f"-- test {k} input: {len(a)}x{len(a[0])}")
            print("\n".join(render(a)))
        print()


if __name__ == "__main__":
    main()
