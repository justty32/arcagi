"""r08 practice pool helpers: task sets, budgets, the G1 gate and logcost_L.

* P (practice) is searched every pass with an iterative-deepening budget and
  feeds G1, never AUC_L; H24 is measured only (D-r8-9).
* G1 gate (D-r8-6): no test answers, no S5 pairs. A train-correct program
  passes when its size < total train output cells (MDL gate, D-r8-19;
  the first r08 runs used / 4) and, if the
  task has >= 3 train pairs, every leave-one-out re-search (budget / 4 on the
  other pairs) finds a program that is right on the held-out pair. Test and S5
  results are kept only as audit columns (false_pos, synth_ok).
* logcost_L (D-r8-10): per task log2(min(nodes_to_first, B)), unsolved
  log2(B); a task already solved at pass 0 may gain at most 2 bits.
"""

import hashlib
import json
import math
import random
from pathlib import Path

from . import prog as pg

ROOT = Path(__file__).resolve().parents[3]
SYNTH = ROOT / "data_synth"
SPEEDUP_CAP = 2.0  # bits a pass-0 solved task may still gain (D-r8-10)
MDL_DIV = 1.0  # D-r8-19 (was 4: wrongly rejected small-output tasks)
BOOT_N = 1000
BOOT_SEED = "r08-boot"


def subset(ids: list[str], seed: int, frac: float) -> list[str]:
    """CRN practice subset: order by sha1(task_id + str(seed)), keep frac."""
    if frac >= 1.0:
        return sorted(ids)
    ranked = sorted(ids, key=lambda t: hashlib.sha1(
        (t + str(seed)).encode()).hexdigest())
    return sorted(ranked[:int(frac * len(ids))])


def practice_ids(taskset: Path, which: str, seed: int, frac: float) -> list[str]:
    """``which``: "" (no pool), "all" (themed P32, D-r8-14), "rand32"
    or "foot32" (foothold themes, D-r8-18)."""
    if not which:
        return []
    data = json.loads(taskset.read_text())
    key = {"rand32": "rand32", "foot32": "pool_foot32"}.get(which, "practice")
    ids = [e["task_id"] for e in data[key]]
    return subset(ids, seed, frac)


def h24_ids(taskset: Path) -> list[str]:
    data = json.loads(taskset.read_text())
    return [e["task_id"] for e in data.get("holdout24", [])]


def budget(b0: int, mult: float, cap: int, pass_no: int) -> int:
    """Iterative deepening: b0 * mult**pass, capped."""
    return min(cap, int(round(b0 * mult ** pass_no)))


def synth_n_original() -> dict[str, int]:
    man = json.loads((SYNTH / "manifest.json").read_text())
    return {tid: int(v["n_original"]) for tid, v in man["tasks"].items()}


def synth_pairs(task_id: str, n_original: int) -> list:
    """S5 synthetic pairs of a task (its train list after the original ones)."""
    path = SYNTH / "training" / f"{task_id}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [([list(r) for r in e["input"]], [list(r) for r in e["output"]])
            for e in data["train"][n_original:]]


def out_cells(train) -> int:
    return sum(len(y) * (len(y[0]) if y and isinstance(y[0], list) else 1)
               for _, y in train)


def mdl_ok(program, train, div: float = MDL_DIV) -> bool:
    """MDL gate: program size < total train output cells / div."""
    return pg.size(program) < out_cells(train) / div


def loo_ok(train, research, check) -> tuple[bool, int]:
    """Leave-one-out: ``research(pairs)`` -> (program | None, nodes)."""
    if len(train) < 3:
        return True, 0
    nodes = 0
    for i in range(len(train)):
        rest = train[:i] + train[i + 1:]
        prog, n = research(rest)
        nodes += n
        if prog is None or not check(prog, [train[i]]):
            return False, nodes
    return True, nodes


def task_cost(nodes_first: int | None, solved: bool, b: int) -> float:
    if not solved or nodes_first is None:
        return math.log2(b)
    return math.log2(max(1, min(nodes_first, b)))


def capped(cost: float, cost0: float | None, b: int) -> float:
    """Speed-up of a task solved at pass 0 counts at most SPEEDUP_CAP bits."""
    if cost0 is None or cost0 >= math.log2(b):
        return cost
    return max(cost, cost0 - SPEEDUP_CAP)


def bootstrap(before: dict[str, float], after: dict[str, float],
              n: int = BOOT_N) -> tuple[float, float]:
    """Paired task-level bootstrap of sum(before - after): (drop, SE)."""
    ids = sorted(before)
    d = [before[t] - after[t] for t in ids]
    drop = sum(d)
    rng = random.Random(BOOT_SEED)
    sums = []
    for _ in range(n):
        sums.append(sum(d[rng.randrange(len(d))] for _ in d))
    mean = sum(sums) / n
    se = math.sqrt(sum((s - mean) ** 2 for s in sums) / (n - 1))
    return drop, se
