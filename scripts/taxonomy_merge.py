"""Merge subagent label batches into ``docs/taxonomy/labels.csv`` and validate them.

Checks: every one of the 800 task ids labelled exactly once, and every
subcategory id appears in ``docs/taxonomy/categories.csv`` under its category.
Applies ``docs/taxonomy/overrides.csv`` last. Also writes ``labels-detail.csv``
(with confidence and rule) next to the batches.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "docs/taxonomy/categories.csv"


def known_subcategories() -> set[str]:
    return {r["subcategory"] for r in csv.DictReader(TABLE.open())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--labels-dir", type=Path, default=ROOT / "reports/taxonomy-r04/labels"
    )
    ap.add_argument("--out", type=Path, default=ROOT / "docs/taxonomy/labels.csv")
    args = ap.parse_args()
    subs = known_subcategories()
    ids = {
        p.stem
        for s in ("training", "evaluation")
        for p in (ROOT / "data/ARC-AGI/data" / s).glob("*.json")
    }
    rows, problems = {}, []
    for path in sorted(args.labels_dir.glob("batch_*.csv")):
        for r in csv.DictReader(path.open()):
            tid = r["task_id"].strip()
            sub = r["subcategory"].strip()
            cat = r["category"].strip()
            if "." not in sub:
                sub = f"{cat}.{sub}"
            if tid in rows:
                problems.append(f"duplicate {tid} in {path.name}")
            if sub not in subs or sub.split(".")[0] != cat:
                problems.append(f"bad label {tid}: {cat}/{sub} ({path.name})")
            rows[tid] = {
                "task_id": tid,
                "category": cat,
                "subcategory": sub,
                "confidence": r.get("confidence", "").strip(),
                "rule": (r.get("rule") or "").strip(),
            }
    overrides = ROOT / "docs/taxonomy/overrides.csv"
    if overrides.exists():
        for r in csv.DictReader(overrides.open()):
            if r["task_id"] in rows:
                rows[r["task_id"]].update(
                    category=r["category"], subcategory=r["subcategory"]
                )
                if r["subcategory"] not in subs:
                    problems.append(f"bad override {r['task_id']}: {r['subcategory']}")
            else:
                problems.append(f"override for unlabelled {r['task_id']}")
    missing = sorted(ids - rows.keys())
    extra = sorted(rows.keys() - ids)
    problems += [f"missing {t}" for t in missing] + [f"unknown id {t}" for t in extra]
    order = sorted(rows.values(), key=lambda r: r["task_id"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=("task_id", "category", "subcategory"), extrasaction="ignore"
        )
        w.writeheader()
        w.writerows(order)
    with (args.labels_dir.parent / "labels-detail.csv").open("w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=("task_id", "category", "subcategory", "confidence", "rule")
        )
        w.writeheader()
        w.writerows(order)
    print(f"{len(rows)} labelled; {len(missing)} missing; {len(problems)} problems")
    for p in problems[:40]:
        print(" ", p)
    print(Counter(r["category"] for r in order).most_common())
    print(Counter(r["confidence"] for r in order))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
