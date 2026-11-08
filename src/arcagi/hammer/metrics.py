"""Report-only metrics: ΔAUC_total and LTO-SCF∪ (02 §5, 03 §4).

* ``delta_auc(tree_rows, control_csv, key)``: area between the tree's blind
  curve and the non-learning dec-g1 control on x = log10(cumulative evals),
  evals = body + shadow + meta + foundry + LLM tax. ``key`` = "solved_H8" or
  "solved_H24" (reported separately). Step curves; the area is taken over
  the x range both curves cover.
* ``lto_scf(root_a, ids_b, ...)``: leave-tree-out speed-up on P48's B fold,
  with the library the tree grew on the A fold (``sha1(task_id+"r09AB")``
  halves). On U = Solved_base ∪ Solved_+A, unsolved tasks count B_max; the
  geometric-mean speed-up and a bootstrap 90% lower bound are printed with
  |U| and the number of base solves the A library lost.

    uv run python -m arcagi.hammer.metrics <tree_root> [--control CSV]
"""

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path

from arcagi.grow import curve as gc

from . import body
from . import formats as fm
from . import grow as gw

ROOT = Path(__file__).resolve().parents[3]
CONTROL = ROOT / "reports" / "curve-r09" / "dec-g1" / "curve.csv"
B_MAX = 100_000


def folds(ids: list[str]) -> dict[str, str]:
    """A/B halves: sort by sha1(task_id + "r09AB"), first half A (= the
    ``fold`` field of data/r09/taskset.json, scripts/r09_taskset.py)."""
    order = sorted(ids, key=lambda t: hashlib.sha1((t + "r09AB").encode())
                   .hexdigest())
    return {t: "A" if i < len(order) // 2 else "B" for i, t in enumerate(order)}


def _steps(xs, ys):
    pts = []
    tot = 0.0
    for x, y in zip(xs, ys, strict=True):
        tot += x
        pts.append((math.log10(max(1.0, tot)), float(y)))
    return pts


def _at(pts, x):
    y = pts[0][1]
    for px, py in pts:
        if px <= x:
            y = py
    return y


def area(pts, lo, hi):
    xs = sorted({lo, hi, *[p[0] for p in pts if lo < p[0] < hi]})
    return sum((b - a) * _at(pts, a) for a, b in zip(xs, xs[1:], strict=False))


def tree_points(rows: list[dict], key: str, llm_tax: int = 0):
    ev = [int(r.get("evals_body") or 0) + int(r.get("evals_shadow") or 0)
          + int(r.get("evals_meta") or 0) + int(r.get("evals_foundry") or 0)
          + llm_tax * int(r.get("llm_calls") or 0) for r in rows]
    return _steps(ev, [r.get(key) or 0 for r in rows])


def control_points(path: Path, key: str):
    rows = list(csv.DictReader(path.open()))
    col = {"solved_H8": "solved_H", "solved_H24": "solved_H24"}[key]
    return _steps([int(r["nodes_total"]) for r in rows],
                  [int(r[col] or 0) for r in rows])


def delta_auc(rows: list[dict], control: Path = CONTROL, key: str = "solved_H8",
              llm_tax: int = fm.LLM_TAX_EVALS) -> dict:
    t, c = tree_points(rows, key, llm_tax), control_points(control, key)
    lo, hi = max(t[0][0], c[0][0]), min(t[-1][0], c[-1][0])
    if hi <= lo:
        return {"key": key, "delta": None, "range": [lo, hi]}
    return {"key": key, "delta": round(area(t, lo, hi) - area(c, lo, hi), 4),
            "range": [round(lo, 3), round(hi, 3)]}


def _cost(s) -> float:
    return float(min(s["nodes_to_first"] or B_MAX, B_MAX)) if s["train_ok"] \
        else float(B_MAX)


def lto_scf(root_a: Path, ids_b: list[str], backend: str = "native",
            threads: int = 6, boot: int = 1000) -> dict:
    """B-fold 1 pass: empty library vs the live comb library of ``root_a``."""
    tasks = body.load_tasks(ids_b)
    cfg = body.BodyCfg(backend=backend, threads=threads,
                       tmp_dir=str(Path(root_a) / "tmp"))
    base_lib = Path(root_a) / "lto_base_blocks.json"
    plus_lib = Path(root_a) / "lto_plus_blocks.json"
    gc._save_lib([], base_lib)
    gc._save_lib(gw.lib_from_ops(fm.load_ops(root_a)), plus_lib)
    base = {s["task_id"]: s for s in body.solve_batch(tasks, base_lib, B_MAX, cfg)}
    plus = {s["task_id"]: s for s in body.solve_batch(tasks, plus_lib, B_MAX, cfg)}
    u = sorted(t for t in ids_b if base[t]["train_ok"] or plus[t]["train_ok"])
    lost = [t for t in u if base[t]["train_ok"] and not plus[t]["train_ok"]]
    logs = [math.log(_cost(base[t]) / _cost(plus[t])) for t in u]
    out = {"U": len(u), "lost": lost, "n_B": len(ids_b),
           "speedup": round(math.exp(sum(logs) / len(logs)), 4) if logs else None}
    if logs:
        rng = random.Random("r09-lto")
        means = sorted(sum(logs[rng.randrange(len(logs))] for _ in logs) / len(logs)
                       for _ in range(boot))
        out["lb90"] = round(math.exp(means[int(0.05 * boot)]), 4)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--control", type=Path, default=CONTROL)
    a = ap.parse_args(argv)
    rows = []
    for d in sorted((a.root / "epochs").glob("*/"), key=lambda p: int(p.name)):
        st = fm.read_json(d / "status.json")
        if st:
            rows.append(st)
    print(json.dumps({k: delta_auc(rows, a.control, k)
                      for k in ("solved_H8", "solved_H24")}))


if __name__ == "__main__":
    main()
