#!/usr/bin/env python3
"""Print median wall times, ranges, speedups and exactness for bench.sh output."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", type=Path)
    args = parser.parse_args()
    groups = defaultdict(list)
    loads = []
    for line in (args.outdir / "wall.txt").read_text().splitlines():
        budget, binary, rep, seconds, load = line.split()
        groups[int(budget), binary].append(float(seconds))
        loads.append(float(load))
    mismatches = defaultdict(list)
    cmp_file = args.outdir / "cmp.txt"
    if cmp_file.exists():
        for line in cmp_file.read_text().splitlines():
            result = json.loads(line)
            budget, rest = Path(result["candidate"]).stem.split("-", 1)
            binary, _ = rest.rsplit("-r", 1)
            mismatches[int(budget), binary].append(result["mismatches"])
    print("| budget | bin | wall median (min..max), s | speedup | mismatches |")
    print("|---:|---|---:|---:|---:|")
    for budget in sorted({b for b, _ in groups}):
        baseline = groups.get((budget, "arcbatch"))
        for binary in ("arcbatch", "arcbatch-hot-a", "arcbatch-hot"):
            walls = groups.get((budget, binary))
            if not walls:
                continue
            middle = median(walls)
            speedup = f"{median(baseline) / middle:.3f}x" if baseline else "pending"
            counts = mismatches[budget, binary]
            count = "reference" if binary == "arcbatch" else (
                str(sum(counts)) if len(counts) == len(walls) else "incomplete")
            print(f"| {budget} | {binary} | {middle:.3f} ({min(walls):.3f}..{max(walls):.3f}) | {speedup} | {count} |")
    if loads:
        print(f"\nObserved loadavg1 at run start: {min(loads):.2f}..{max(loads):.2f}.")
    if not (args.outdir / "DONE").exists():
        print("\nPartial run: DONE is absent.")


if __name__ == "__main__":
    main()
