#!/usr/bin/env python3
"""Summarize hammer search curves or compare two think-1 summaries."""

import argparse
import csv
import json
import math
import os
from pathlib import Path
import sys

RULES = {
    "first_scored_epoch": 1,
    "speed_digits": 3,
    "wall_digits": 2,
    "eff_digits": 4,
    "cost_unit": 1_000_000,
    "significance_sigma": 2,
}
OUTPUT_DIR = Path("/home/lorkhan/code/playground-arc1/ws/hammer/think1/meta")
EVAL_FIELDS = ("evals_body", "evals_shadow", "evals_meta", "evals_foundry")


def check_stop() -> None:
    if (Path.home() / "arcagi-STOP").exists():
        raise SystemExit("STOP: ~/arcagi-STOP exists")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def completed_epochs(root: Path) -> list[int]:
    return sorted(
        int(path.name)
        for path in (root / "epochs").iterdir()
        if path.is_dir() and path.name.isascii() and path.name.isdecimal()
        and (path / "status.json").exists()
    )


def summarize(root: Path) -> dict:
    epochs = completed_epochs(root)
    if not epochs or 0 not in epochs:
        raise ValueError("tree must include completed epoch 0 as the empty-library baseline")
    curves = {}
    per_epoch = []
    for epoch in epochs:
        check_stop()
        path = root / "epochs" / str(epoch) / "curve.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 1:
            raise ValueError(f"{path}: expected exactly one data row")
        row = rows[0]
        if int(row["epoch"]) != epoch:
            raise ValueError(f"{path}: epoch does not match directory")
        curves[epoch] = row
        per_epoch.append({
            "epoch": epoch,
            "solved_L": int(row["solved_L"]),
            "solved_P": int(row["solved_P"]),
            "solved_H24": int(row["solved_H24"]),
            "logcost_L": float(row["logcost_L"]),
            "evals": sum(int(row[field]) for field in EVAL_FIELDS),
            "wall_s": float(row["wall_s"]),
            "stall": row["stall"],
        })
    scored = [epoch for epoch in epochs if epoch >= RULES["first_scored_epoch"]]
    base = float(curves[0]["logcost_L"])
    final = curves[epochs[-1]]
    auc_l = sum(int(curves[e]["solved_L"]) for e in scored)
    cost = sum(row["evals"] for row in per_epoch)
    return {
        "schema": "think1-curve/1",
        "tree_root": str(root),
        "epochs": len(epochs),
        "scored_epochs": len(scored),
        "auc_L": auc_l,
        "auc_P": sum(int(curves[e]["solved_P"]) for e in scored),
        "auc_H24": sum(int(curves[e]["solved_H24"]) for e in scored),
        "auc_H8": sum(int(curves[e]["solved_H8"]) for e in scored),
        "logcost_L_base": base,
        "logcost_L_final": float(final["logcost_L"]),
        "auc_speed_L": round(sum(base - float(curves[e]["logcost_L"])
                                 for e in scored), RULES["speed_digits"]),
        "cost": cost,
        "wall_s_total": round(sum(row["wall_s"] for row in per_epoch), RULES["wall_digits"]),
        "llm_calls": sum(int(curves[e]["llm_calls"]) for e in epochs),
        "eff": round(auc_l / (cost / RULES["cost_unit"]), RULES["eff_digits"]),
        "lib_size_final": int(final["lib_size"]),
        "lib_bits_final": float(final["lib_bits"]),
        "stall_final": final["stall"],
        "arm_final": final["arm"],
        "per_epoch": per_epoch,
    }


def compare(path_a: Path, path_b: Path) -> dict:
    a, b = read_json(path_a), read_json(path_b)
    result = {f"d_{key}": b[key] - a[key]
              for key in ("auc_L", "auc_speed_L", "cost", "eff")}
    noise_path = path_a.parent / "noise.json"
    sigma = significant = None
    if noise_path.exists():
        sigma = float(read_json(noise_path)["sigma_auc_L"])
        if not math.isfinite(sigma) or sigma < 0:
            raise ValueError(f"{noise_path}: sigma_auc_L must be finite and nonnegative")
        significant = abs(result["d_auc_L"]) > RULES["significance_sigma"] * sigma
    else:
        print("WARN: noise.json missing; significance unknown", file=sys.stderr)
    result.update(sigma_auc_L=sigma, significant=significant)
    return result


def write_summary(out: Path, payload: str) -> None:
    """Only publish within the authorized directory, using atomic replacement."""
    check_stop()
    tmp = out.with_name(out.name + ".tmp")
    if out.parent.resolve() != OUTPUT_DIR or tmp.is_symlink() or out.is_symlink():
        raise ValueError(f"output must stay in {OUTPUT_DIR} without file symlinks")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(payload + "\n", encoding="utf-8")
    check_stop()
    os.replace(tmp, out)


def main() -> None:
    check_stop()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree_root", type=Path, nargs="?")
    parser.add_argument("--compare", type=Path, nargs=2, metavar=("A", "B"))
    args = parser.parse_args()
    if (args.tree_root is None) == (args.compare is None):
        parser.error("provide either tree_root or --compare A B")
    try:
        if args.compare is not None:
            result = compare(*args.compare)
        else:
            result = summarize(args.tree_root.resolve())
        payload = json.dumps(result, ensure_ascii=False)
        if args.compare is None:
            out = args.tree_root.resolve() / "think1" / "meta" / "curve-summary.json"
            write_summary(out, payload)
        print(payload)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
