"""Sample unsolved TRAINING tasks for per-task failure analysis (S4).

Stratified by category (proportional to unsolved count, at least 1 per category
with unsolved tasks), fixed seed. Evaluation is never sampled: per-task failure
mechanisms drive solver design, so they must come from training only.
Writes ``reports/taxonomy-<run>/failsample.json`` with each task's label, rule and
the solver's top near misses from the traces.
"""

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", default="r04")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=4)
    args = ap.parse_args()
    base = ROOT / "artifacts" / args.run
    report = json.loads((base / "dsl-training.json").read_text())
    unsolved = {t["task_id"] for t in report["tasks"] if not t["correct"]}
    near: dict[str, list] = {}
    sols: dict[str, int] = {}
    for line in (base / "dsl-training-traces.jsonl").open():
        r = json.loads(line)
        tr = r.get("trace") or {}
        sols[r["task_id"]] = (tr.get("metadata") or {}).get("solutions", 0) or 0
        ms = [a for a in tr.get("attempts", []) if a.get("kind") == "near_miss"]
        ms.sort(key=lambda a: -a.get("data", {}).get("pixel_acc", 0.0))
        near[r["task_id"]] = [
            {
                "program": a["program"],
                "pixel_acc": a.get("data", {}).get("pixel_acc"),
                "train_correct": f"{a.get('train_correct')}/{a.get('train_total')}",
            }
            for a in ms[:3]
        ]
    detail = ROOT / f"reports/taxonomy-{args.run}/labels-detail.csv"
    labels = {r["task_id"]: r for r in csv.DictReader(detail.open())}
    by_cat: dict[str, list[str]] = defaultdict(list)
    for tid in sorted(unsolved):
        by_cat[labels[tid]["category"]].append(tid)
    total = sum(len(v) for v in by_cat.values())
    rng = random.Random(args.seed)
    quota = {c: max(1, round(args.n * len(v) / total)) for c, v in by_cat.items()}
    while sum(quota.values()) > args.n:
        c = max(quota, key=lambda k: quota[k])
        quota[c] -= 1
    while sum(quota.values()) < args.n:
        c = max(by_cat, key=lambda k: len(by_cat[k]) - quota[k])
        quota[c] += 1
    picked = []
    for c in sorted(by_cat):
        for tid in rng.sample(by_cat[c], min(quota[c], len(by_cat[c]))):
            lab = labels[tid]
            picked.append(
                {
                    "task_id": tid,
                    "category": c,
                    "subcategory": lab["subcategory"],
                    "rule": lab["rule"],
                    "train_pass_wrong": sols.get(tid, 0) > 0,
                    "near_misses": near.get(tid, []),
                }
            )
    out = ROOT / f"reports/taxonomy-{args.run}/failsample.json"
    out.write_text(
        json.dumps(
            {
                "run": args.run,
                "split": "training",
                "seed": args.seed,
                "quota": quota,
                "tasks": picked,
            },
            indent=1,
        )
    )
    print(f"{len(picked)} tasks -> {out}; quota {quota}")


if __name__ == "__main__":
    main()
