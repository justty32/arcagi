"""Meta-optimisation over the six knobs.

Layer 1: each round changes one knob to a neighbouring value, runs one curve
per paired seed (G1 + G4, common random numbers) and keeps the change only on
a real gain (``real_gain``: >= 80% seeds not worse, mean AUC_L gain >= 1).
Layer 2: the knob to change is chosen by Thompson sampling over per-knob
Beta(1 + accepted, 1 + tried - accepted), counts read back from the ledger.
Every attempt appends one line to aos/meta/ledger.jsonl (kind=r07).
"""

import json
import math
import random
import time
from pathlib import Path

from . import curve
from . import knobs as kn

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "aos" / "meta" / "ledger.jsonl"


def knob_stats(ledger: Path = LEDGER) -> dict[str, tuple[int, int]]:
    """{knob: (tried, accepted)} over kind=r07 ledger rows."""
    stats = {k: (0, 0) for k in kn.CHOICES}
    if not ledger.exists():
        return stats
    for line in ledger.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") != "r07" or row.get("knob") not in stats:
            continue
        t, a = stats[row["knob"]]
        stats[row["knob"]] = (t + 1, a + int(bool(row.get("accepted"))))
    return stats


def pick_knob(rng: random.Random, stats: dict[str, tuple[int, int]],
              current: kn.Knobs) -> str:
    best, best_draw = None, -1.0
    for name in sorted(stats):
        if not kn.neighbours(current, name):
            continue
        tried, acc = stats[name]
        draw = rng.betavariate(1 + acc, 1 + tried - acc)
        if draw > best_draw:
            best, best_draw = name, draw
    assert best is not None
    return best


def append_ledger(row: dict, ledger: Path = LEDGER) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def real_gain(before: list[int], after: list[int]) -> bool:
    """CRN rule: >= 80% of paired seeds not worse and mean gain >= 1 task."""
    n = len(before)
    not_worse = sum(a >= b for a, b in zip(after, before, strict=True))
    gain = (sum(after) - sum(before)) / n
    return not_worse >= math.ceil(0.8 * n) and gain >= 1.0


def run_meta(rounds: int, passes: int, out_root: Path, lib_root: Path,
             seeds: tuple[int, ...] = (0, 1, 2), workers: int = 6,
             ledger: Path = LEDGER, start: kn.Knobs | None = None,
             log=print) -> list[dict]:
    rng = random.Random("r07-meta")
    current = start or kn.load()

    def score(knobs: kn.Knobs, tag: str) -> tuple[list[int], float]:
        t0 = time.perf_counter()
        aucs = []
        for s in seeds:  # common random numbers: same seeds for every variant
            cfg = curve.Config(tree="g1g4", knobs=knobs, seed=s, passes=passes,
                               workers=workers)
            rows = curve.run_curve(cfg, out_root / tag / f"seed{s}",
                                   lib_root / tag / f"seed{s}", log=log)
            aucs.append(curve.auc_l(rows))
        return aucs, time.perf_counter() - t0

    auc_cur, _ = score(current, "r0-base")
    history = []
    for r in range(1, rounds + 1):
        knob = pick_knob(rng, knob_stats(ledger), current)
        options = kn.neighbours(current, knob)
        new_val = options[rng.randrange(len(options))]
        trial = current.with_(**{knob: new_val})
        auc_new, cost = score(trial, f"r{r}-{knob}")
        accepted = real_gain(auc_cur, auc_new)
        row = {
            "kind": "r07", "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "round": r, "knob": knob, "before": getattr(current, knob),
            "after": new_val,
            "auc_before": round(sum(auc_cur) / len(auc_cur), 3),
            "auc_after": round(sum(auc_new) / len(auc_new), 3),
            "auc_before_seeds": auc_cur, "auc_after_seeds": auc_new,
            "cost_s": round(cost, 1), "accepted": accepted, "passes": passes,
            "seeds": list(seeds),
            "note": "r07 line B meta layer 1+2 (Thompson, CRN seeds, D-r7-11)",
        }
        append_ledger(row, ledger)
        history.append(row)
        log(f"[meta] round {r}: {knob} {row['before']} -> {new_val} "
            f"AUC {auc_cur} -> {auc_new} {'ACCEPT' if accepted else 'reject'}")
        if accepted:
            current, auc_cur = trial, auc_new
    return history
