"""Meta-optimisation over the six knobs.

Layer 1: each round changes one knob to a neighbouring value, runs one curve
(G1 + G4, fixed seed) and keeps the change only if AUC_L improves.
Layer 2: the knob to change is chosen by Thompson sampling over per-knob
Beta(1 + accepted, 1 + tried - accepted), counts read back from the ledger.
Every attempt appends one line to aos/meta/ledger.jsonl (kind=r07).
"""

import json
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


def run_meta(rounds: int, passes: int, out_root: Path, lib_root: Path,
             seed: int = 0, workers: int = 6, ledger: Path = LEDGER,
             start: kn.Knobs | None = None, log=print) -> list[dict]:
    rng = random.Random(f"r07-meta-{seed}")
    current = start or kn.load()

    def score(knobs: kn.Knobs, tag: str) -> tuple[int, float, list[dict]]:
        cfg = curve.Config(tree="g1g4", knobs=knobs, seed=seed, passes=passes,
                           workers=workers)
        t0 = time.perf_counter()
        rows = curve.run_curve(cfg, out_root / tag, lib_root / tag, log=log)
        return curve.auc_l(rows), time.perf_counter() - t0, rows

    auc_cur, _, _ = score(current, "r0-base")
    history = []
    for r in range(1, rounds + 1):
        knob = pick_knob(rng, knob_stats(ledger), current)
        options = kn.neighbours(current, knob)
        new_val = options[rng.randrange(len(options))]
        trial = current.with_(**{knob: new_val})
        auc_new, cost, _ = score(trial, f"r{r}-{knob}")
        accepted = auc_new > auc_cur
        row = {
            "kind": "r07", "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "round": r, "knob": knob, "before": getattr(current, knob),
            "after": new_val, "auc_before": auc_cur, "auc_after": auc_new,
            "cost_s": round(cost, 1), "accepted": accepted, "passes": passes,
            "seed": seed, "note": "r07 line B meta layer 1+2 (Thompson)",
        }
        append_ledger(row, ledger)
        history.append(row)
        log(f"[meta] round {r}: {knob} {row['before']} -> {new_val} "
            f"AUC {auc_cur} -> {auc_new} {'ACCEPT' if accepted else 'reject'}")
        if accepted:
            current, auc_cur = trial, auc_new
    return history
