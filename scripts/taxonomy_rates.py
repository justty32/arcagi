"""Per-category solve rates for the S4 taxonomy against arcagi eval reports.

Reads ``docs/taxonomy/labels.csv`` and one eval report + traces per split, and
writes ``rates.csv`` (``wf-table/1``) with, per split x level x label: task count,
solved, rate, train-passing-but-wrong, and how many unsolved tasks have a near
miss with pixel accuracy >= 0.9, and ``half_fixed``: unsolved tasks whose best near
miss fixes >= half of the pixels that copying the input gets wrong (a fairer
"close to solvable" signal for same-size tasks, where copying already scores high;
for shape-changing tasks it falls back to pixel accuracy >= 0.9).
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = (
    "split",
    "level",
    "label",
    "tasks",
    "solved",
    "rate",
    "train_pass_wrong",
    "near90",
    "near_mean",
    "half_fixed",
)


def identity_acc(task_path: Path) -> float:
    """Mean train pixel accuracy of copying the input (0 when shapes differ)."""
    pairs = json.loads(task_path.read_text())["train"]
    accs = []
    for p in pairs:
        a, b = p["input"], p["output"]
        if (len(a), len(a[0])) != (len(b), len(b[0])):
            return 0.0
        cells = [x == y for ra, rb in zip(a, b) for x, y in zip(ra, rb)]
        accs.append(sum(cells) / len(cells))
    return sum(accs) / len(accs)


def load_split(report: Path, traces: Path | None) -> dict[str, dict]:
    tasks = {
        t["task_id"]: {"correct": bool(t["correct"]), "sols": 0, "best": 0.0}
        for t in json.loads(report.read_text())["tasks"]
    }
    if traces and traces.exists():
        for line in traces.open():
            r = json.loads(line)
            tr = r.get("trace") or {}
            info = tasks.get(r["task_id"])
            if info is None:
                continue
            info["sols"] = (tr.get("metadata") or {}).get("solutions", 0) or 0
            accs = [
                a.get("data", {}).get("pixel_acc", 0.0)
                for a in tr.get("attempts", [])
                if a.get("kind") == "near_miss"
            ]
            info["best"] = max(accs, default=0.0)
    return tasks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", type=Path, default=ROOT / "docs/taxonomy/labels.csv")
    ap.add_argument("--run", default="r04", help="artifacts/<run>/dsl-<split>.json")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or ROOT / f"reports/taxonomy-{args.run}/rates.csv"
    labels = list(csv.DictReader(args.labels.open()))
    split_of = {}
    for split in ("training", "evaluation"):
        for p in (ROOT / "data/ARC-AGI/data" / split).glob("*.json"):
            split_of[p.stem] = split
    data = {}
    for split in ("training", "evaluation"):
        base = ROOT / "artifacts" / args.run
        data[split] = load_split(
            base / f"dsl-{split}.json", base / f"dsl-{split}-traces.jsonl"
        )
    agg: dict[tuple, list] = defaultdict(list)
    for row in labels:
        split = split_of[row["task_id"]]
        info = data[split].get(row["task_id"])
        if info is None:
            continue
        ida = identity_acc(
            ROOT / "data/ARC-AGI/data" / split / f"{row['task_id']}.json"
        )
        if ida > 0:  # same shape: share of copy-errors the best near miss fixes
            info["fixed"] = (info["best"] - ida) / (1 - ida) if ida < 1 else 0.0
        else:  # shape changes: half_fixed means pixel accuracy >= 0.9
            info["fixed"] = max(0.0, (info["best"] - 0.8) / 0.2)
        for level, label in (
            ("category", row["category"]),
            ("subcategory", row["subcategory"]),
        ):
            for s in (split, "all"):
                agg[(s, level, label)].append(info)
    rows = []
    for (split, level, label), infos in sorted(agg.items()):
        n = len(infos)
        solved = sum(i["correct"] for i in infos)
        unsolved = [i for i in infos if not i["correct"]]
        rows.append(
            {
                "split": split,
                "level": level,
                "label": label,
                "tasks": n,
                "solved": solved,
                "rate": f"{solved / n:.3f}",
                "train_pass_wrong": sum(1 for i in unsolved if i["sols"] > 0),
                "near90": sum(1 for i in unsolved if i["best"] >= 0.9),
                "near_mean": f"{sum(i['best'] for i in unsolved) / len(unsolved):.3f}"
                if unsolved
                else "",
                "half_fixed": sum(1 for i in unsolved if i["fixed"] >= 0.5),
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
