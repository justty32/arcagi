"""Determinism checks and paired task bootstrap for quick runs."""

import itertools
import random
import statistics
from pathlib import Path

from arcagi.hammer.formats import read_json

from . import boundary


def _load(directory: Path) -> dict:
    boundary.check_stop()
    result = read_json(Path(directory) / "quick.json")
    if result["schema"] != "think2-quick/1":
        raise ValueError("unsupported quick schema")
    return result


def _paired(a: dict, b: dict, n_boot: int, rng: random.Random) -> dict:
    tasks = sorted(a["per_task"].keys() & b["per_task"].keys())
    if not tasks:
        raise ValueError("quick runs have no common L16 tasks")
    differences = [b["per_task"][t]["auc"] - a["per_task"][t]["auc"] for t in tasks]
    degenerate = all(d == 0 for d in differences)
    samples = []
    if not degenerate:
        for _ in range(n_boot):
            boundary.check_stop()
            samples.append(sum(rng.choices(differences, k=len(tasks))))
    return {
        "sigma_auc_L": statistics.pstdev(samples) if samples else 0.0,
        "mean_delta_auc_L": sum(differences),
        "degenerate": degenerate,
        "n_tasks": len(tasks),
    }


def _mismatches(a: dict, b: dict) -> set[str]:
    left, right = a["per_task"], b["per_task"]
    return {
        t
        for t in left.keys() | right.keys()
        if t not in left or t not in right or left[t]["solved"] != right[t]["solved"]
    }


def noise(dirs: list[Path], n_boot: int = 1000, seed: int = 0) -> dict:
    """Compare all run pairs, reporting the largest paired bootstrap spread."""
    if len(dirs) < 2:
        raise ValueError("noise needs at least two quick directories")
    if n_boot < 2:
        raise ValueError("n_boot must be at least two")
    runs = [_load(directory) for directory in dirs]
    rng = random.Random(seed)
    pairs, mismatches = [], set()
    delta = {"auc_L": 0, "cost": 0}
    for i, j in itertools.combinations(range(len(runs)), 2):
        a, b = runs[i], runs[j]
        mismatches.update(_mismatches(a, b))
        for key in delta:
            delta[key] = max(delta[key], abs(b[key] - a[key]))
        pairs.append({"i": i, "j": j, **_paired(a, b, n_boot, rng)})
    return {
        "schema": "think2-noise/1",
        "n_boot": n_boot,
        "seed": seed,
        "runs": [str(directory) for directory in dirs],
        "determinism_delta": delta,
        "per_task_mismatch": len(mismatches),
        "deterministic": not mismatches and not any(delta.values()),
        "sigma_run_auc_L": statistics.pstdev(run["auc_L"] for run in runs),
        "sigma_auc_L": max(pair["sigma_auc_L"] for pair in pairs),
        "mean_delta_auc_L": statistics.mean(pair["mean_delta_auc_L"] for pair in pairs),
        "degenerate": all(pair["degenerate"] for pair in pairs),
        "pairs": pairs,
    }


def compare(a: Path, b: Path, n_boot: int = 1000, seed: int = 0) -> dict:
    """Return B minus A and its paired task bootstrap uncertainty."""
    if n_boot < 2:
        raise ValueError("n_boot must be at least two")
    left, right = _load(a), _load(b)
    paired = _paired(left, right, n_boot, random.Random(seed))
    delta = right["auc_L"] - left["auc_L"]
    sigma = paired["sigma_auc_L"]
    return {
        **paired,
        "delta_auc_L": delta,
        "z": delta / sigma if sigma else None,
        "n_tasks_differ": len(_mismatches(left, right)),
    }
