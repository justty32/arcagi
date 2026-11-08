"""Summarise an r09 tree's curves as markdown tables.

    uv run python scripts/r09_report.py reports/curve-r09/<tree>

Reads <dir>/curve.csv if present, else concatenates <dir>/epochs/<n>/curve.csv;
and <dir>/ops.jsonl, <dir>/ledger.jsonl when present. Column names are looked
up leniently (first match of several aliases); missing ones print "-".
"""

import csv
import json
import sys
from pathlib import Path

ALIASES = {
    "epoch": ("epoch", "pass"),
    "L": ("solved_L", "L"), "H": ("solved_H", "solved_H8", "H8"),
    "H24": ("solved_H24", "H24"), "P": ("solved_P", "clean_P", "P"),
    "lib": ("lib_size", "lib"),
}


def _rows(d: Path) -> list[dict]:
    if (d / "curve.csv").exists():
        return list(csv.DictReader((d / "curve.csv").read_text().splitlines()))
    rows: list[dict] = []
    eps = sorted((p for p in (d / "epochs").glob("*") if p.name.isdigit()),
                 key=lambda p: int(p.name)) if (d / "epochs").exists() else []
    for e in eps:
        if (e / "curve.csv").exists():
            for r in csv.DictReader((e / "curve.csv").read_text().splitlines()):
                r.setdefault("epoch", e.name)
                rows.append(r)
    return rows


def _jl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _get(r: dict, key: str) -> str:
    for a in ALIASES[key]:
        if a in r and r[a] != "":
            return r[a]
    return "-"


def main() -> None:
    d = Path(sys.argv[1])
    rows = _rows(d)
    ops = _jl(d / "ops.jsonl")
    ledger = _jl(d / "ledger.jsonl")
    roll = sum(1 for r in ledger if r.get("kind") == "rollback")
    cnt: dict[str, int] = {}
    for o in ops:
        cnt[o["status"]] = cnt.get(o["status"], 0) + 1
    print(f"## {d}\n")
    print("| epoch | solved_L | solved_H | solved_H24 | solved_P | lib |")
    print("|---|---|---|---|---|---|")
    auc = 0
    for r in rows:
        print("| " + " | ".join(_get(r, k) for k in
                               ("epoch", "L", "H", "H24", "P", "lib")) + " |")
        try:
            auc += int(_get(r, "L"))
        except ValueError:
            pass
    print(f"\nAUC_L (sum of solved_L over rows) = {auc}")
    print(f"\nops: live={cnt.get('live', 0)} incubating={cnt.get('incubating', 0)} "
          f"dormant={cnt.get('dormant', 0)}; rollbacks={roll}")


if __name__ == "__main__":
    main()
