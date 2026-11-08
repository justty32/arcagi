"""Stall judge: ok / starve / saturate / stop over the last ``window`` epochs.

02-規劃-fable.md §1 step 5 (definitions written down before any replay):

* starve   : the G1 gate got 0 programs in every one of the last ``window``
             epochs (nothing to compress).
* saturate : solved_L, solved_H24 and lib_bits did not move over the window.
* stop     : saturated and the best ``near`` score among unsolved L16 tasks
             did not move either (only then is a wax request allowed).
* ok       : anything else, or fewer than ``window`` epoch rows.

Starve is checked first: a starving tree is also saturated, but the cure is
different (feed the gate, rt_pool), so starve wins.

Ledger fields read (A line's epoch rows, ``kind == "epoch"``). Each field is
looked up in ``row``, then ``row["after"]``, then ``row["metrics"]``:

    solved_L, solved_H24, lib_bits   ints / floats
    gate_in                          programs that entered the G1 gate
                                     (``row["gate"]["in"]`` also accepted)
    near_best_L                      best near score over unsolved L16

A field that is missing (None) in a row is skipped for "did it move"; if a
field is missing in every row of the window it does not count as moved.
``gate_in`` missing in any window row means starve cannot be judged (False).

Wiring for epoch.py (step ⑤):  ``state = judge_stall(load_ledger(root))``
then ``append_ledger(root, stall_row(n, state, rows))``.

Replay adapters for r08 (acceptance, reports/curve-r09/stall-replay/):
``r08_curve_rows(csv)`` and ``r08_meta_rows(rounds.json)``.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

WINDOW = 3
EPS = 1e-9


def _get(row: dict, key: str):
    for src in (row, row.get("after") or {}, row.get("metrics") or {}):
        if isinstance(src, dict) and src.get(key) is not None:
            return src[key]
    if key == "gate_in" and isinstance(row.get("gate"), dict):
        return row["gate"].get("in")
    return None


def _flat(vals) -> bool:
    """True when the non-None values do not move."""
    v = [x for x in vals if x is not None]
    return len(v) < 2 or max(v) - min(v) <= EPS


def epoch_rows(ledger_rows: list[dict]) -> list[dict]:
    """Epoch rows only, last occurrence per epoch (a rolled-back rerun wins)."""
    by = {}
    for r in ledger_rows:
        if r.get("kind") == "epoch" and isinstance(r.get("epoch"), int) \
                and r["epoch"] >= 0:
            by[r["epoch"]] = r
    return [by[k] for k in sorted(by)]


def judge_stall(ledger_rows: list[dict], window: int = WINDOW) -> str:
    """"ok" | "starve" | "saturate" | "stop" from ledger rows (any kinds)."""
    rows = epoch_rows(ledger_rows)[-window:]
    if len(rows) < window:
        return "ok"
    gate = [_get(r, "gate_in") for r in rows]
    if all(g is not None for g in gate) and all(g == 0 for g in gate):
        return "starve"
    if not all(_flat([_get(r, k) for r in rows])
               for k in ("solved_L", "solved_H24", "lib_bits")):
        return "ok"
    near = [_get(r, "near_best_L") for r in rows]
    if all(x is not None for x in near) and _flat(near):
        return "stop"
    return "saturate"


def stall_row(epoch: int, state: str, ledger_rows: list[dict],
              window: int = WINDOW) -> dict:
    """The ``kind: stall`` ledger row for one judgement."""
    rows = epoch_rows(ledger_rows)[-window:]
    return {"kind": "stall", "epoch": epoch, "layer": 1, "by": "stall",
            "op_ids": [], "state": state, "window": window,
            "seen_epochs": [r["epoch"] for r in rows]}


# ---------------------------------------------------------------- r08 replay

def r08_curve_rows(path: Path) -> list[dict]:
    """r08 curve.csv -> epoch ledger rows. gate_in = clean_P (the pool tree
    only compressed clean practice solutions); r08 had no near score."""
    def num(x, cast):
        return cast(x) if x not in (None, "") else None

    out = []
    with open(path) as f:
        for r in csv.DictReader(f):
            out.append({"kind": "epoch", "epoch": int(r["pass"]),
                        "after": {"solved_L": num(r["solved_L"], int),
                                  "solved_H24": num(r.get("solved_H24"), int),
                                  "lib_bits": num(r["lib_bits"], float),
                                  "gate_in": num(r.get("clean_P"), int)}})
    return out


def r08_meta_rows(path: Path) -> list[dict]:
    """r08 meta rounds.json -> one epoch row per meta round.

    solved_L = mean AUC after the round (the meta layer's own score),
    lib_bits stands in for logcost after (mean over seeds); H24 and the gate
    feed were not recorded per round (None: skipped, not starve)."""
    rounds = json.loads(Path(path).read_text())
    out = []
    for r in rounds:
        auc = r["auc_after_seeds"] if r.get("accepted") else r["auc_before_seeds"]
        lc = r["logcost_after_seeds"] if r.get("accepted") \
            else r["logcost_before_seeds"]
        out.append({"kind": "epoch", "epoch": int(r["round"]),
                    "after": {"solved_L": sum(auc) / len(auc),
                              "solved_H24": None,
                              "lib_bits": round(sum(lc) / len(lc), 3),
                              "gate_in": None}})
    return out


def replay(rows: list[dict], window: int = WINDOW) -> list[tuple[int, str]]:
    """Judgement after each epoch prefix."""
    return [(rows[i]["epoch"], judge_stall(rows[: i + 1], window))
            for i in range(len(rows))]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kind", choices=("curve", "meta", "ledger"))
    ap.add_argument("path")
    ap.add_argument("--window", type=int, default=WINDOW)
    a = ap.parse_args(argv)
    if a.kind == "curve":
        rows = r08_curve_rows(Path(a.path))
    elif a.kind == "meta":
        rows = r08_meta_rows(Path(a.path))
    else:
        rows = [json.loads(x) for x in Path(a.path).read_text().splitlines()
                if x.strip()]
    for ep, st in replay(rows, a.window):
        print(f"{ep}\t{st}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
