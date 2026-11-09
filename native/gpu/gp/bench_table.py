"""Markdown table for native/gpu/gp/bench.sh output directories.

Usage: python native/gpu/gp/bench_table.py BENCH_DIR [BENCH_DIR ...]
Per method (gp / random / exhaustive): tasks run, solved by C++, solve depths,
Python-verified train / test counts, and tasks only that method solved.
"""
import json
import sys
from collections import Counter
from pathlib import Path

METHODS = ("gp", "random", "exhaustive")


def load(path: Path) -> list[dict]:
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def depth(best: dict) -> int:
    if "depth" in best:
        return int(best["depth"])
    return sum(1 for s in best["program"] if s and s[0] != "colormap")


def table(d: Path) -> str:
    solved: dict[str, dict[str, int]] = {}
    lines = [f"### {d.name}", "", "| 方法 | 題數 | C++ 解出 | 解深度分布 | Python train 全過 | Python test 全過 | 只有它解出 |",
             "|---|---|---|---|---|---|---|"]
    stats = {}
    for m in METHODS:
        recs = [r for r in load(d / f"{m}.jsonl") if "task" in r and "skipped" not in r]
        sol = {r["task"]: depth(r["best"]) for r in recs if r.get("best")}
        solved[m] = sol
        ver = [r for r in load(d / f"{m}-verify.jsonl") if "task" in r]
        tr = sum(bool(r.get("train_ok")) for r in ver)
        te = sum(bool(r.get("test_ok")) for r in ver)
        dist = ", ".join(f"d{k}×{v}" for k, v in sorted(Counter(sol.values()).items())) or "—"
        stats[m] = (len(recs), len(sol), dist, tr, te)
    for m in METHODS:
        others = set().union(*(set(solved[o]) for o in METHODS if o != m))
        only = sorted(set(solved[m]) - others)
        n, s, dist, tr, te = stats[m]
        lines.append(f"| {m} | {n} | {s} | {dist} | {tr} | {te} | {len(only)} {' '.join(only)} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print("\n".join(table(Path(a)) for a in sys.argv[1:]))
