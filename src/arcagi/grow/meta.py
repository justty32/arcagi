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
from . import pool as pl

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


# --- r08: continuous judge (capped logcost_L, paired task bootstrap) -------

REWARD_CLIP = 3.0


def crn_judge(before: dict, after: dict) -> dict:
    """D-r8-3 / D-r8-10 rule on two ``score_r08`` results (same CRN seeds).

    * >= 80% of seeds: L16 logcost (sum over passes 1..N) not worse;
    * mean drop (L16 + H24 task costs, averaged over seeds) >= max(1, 2 SE),
      SE from a paired task-level bootstrap;
    * mean AUC_L not lower.
    """
    n = len(before["logcost"])
    not_worse = sum(a <= b for a, b in
                    zip(after["logcost"], before["logcost"], strict=True))
    tb = {t: sum(v) / n for t, v in before["task"].items()}
    ta = {t: sum(v) / n for t, v in after["task"].items()}
    drop, se = pl.bootstrap(tb, ta)
    auc_ok = sum(after["auc"]) >= sum(before["auc"])
    if se == 0.0:
        z = 0.0 if drop == 0 else math.copysign(REWARD_CLIP, drop)
    else:
        z = max(-REWARD_CLIP, min(REWARD_CLIP, drop / se))
    ok = not_worse >= math.ceil(0.8 * n) and drop >= max(1.0, 2 * se) and auc_ok
    return {"accepted": ok, "mean_drop": round(drop, 3), "se": round(se, 3),
            "reward": round(z, 3), "not_worse": not_worse}


def knob_rewards(ledger: Path = LEDGER) -> dict[str, list[float]]:
    """{knob: [reward, ...]} over kind=r08 ledger rows."""
    out: dict[str, list[float]] = {k: [] for k in kn.CHOICES}
    if not ledger.exists():
        return out
    for line in ledger.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "r08" and row.get("knob") in out:
            out[row["knob"]].append(float(row.get("reward", 0.0)))
    return out


def pick_knob_gauss(rng: random.Random, rewards: dict[str, list[float]],
                    current: kn.Knobs, allowed) -> str:
    """Gaussian Thompson: draw N(sum r / (n+1), 1/sqrt(n+1)) per knob."""
    best, best_draw = None, -math.inf
    for name in sorted(allowed):
        if not kn.neighbours(current, name):
            continue
        r = rewards.get(name, [])
        n = len(r)
        draw = rng.gauss(sum(r) / (n + 1), 1 / math.sqrt(n + 1))
        if draw > best_draw:
            best, best_draw = name, draw
    assert best is not None
    return best


def score_r08(cfg_for, knobs: kn.Knobs, tag: str, seeds, out_root: Path,
              lib_root: Path, log=print) -> dict:
    """One short curve per CRN seed; costs summed over passes 1..N."""
    t0 = time.perf_counter()
    lc, auc = [], []
    task: dict[str, list[float]] = {}
    for s in seeds:
        rows = curve.run_curve(cfg_for(knobs, s), out_root / tag / f"seed{s}",
                               lib_root / tag / f"seed{s}", log=log)
        late = [r for r in rows if int(r["pass"]) >= 1]
        lc.append(round(sum(float(r["logcost_L"]) for r in late), 3))
        auc.append(curve.auc_l(rows))
        for t in late[0]["_tcost"]:
            task.setdefault(t, []).append(round(sum(r["_tcost"][t] for r in late), 4))
    return {"logcost": lc, "auc": auc, "task": task,
            "cost_s": round(time.perf_counter() - t0, 1)}


def r08_row(kind: str, before: dict, after: dict, **kw) -> dict:
    return {
        "kind": kind, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), **kw,
        "logcost_before_seeds": before["logcost"],
        "logcost_after_seeds": after["logcost"],
        "auc_before_seeds": before["auc"], "auc_after_seeds": after["auc"],
        **crn_judge(before, after), "cost_s": after["cost_s"],
    }


def run_meta_r08(rounds: int, cfg_for, start: kn.Knobs, out_root: Path,
                 lib_root: Path, seeds=(1, 2, 3, 4, 5), allowed=None,
                 ledger: Path = LEDGER, log=print, base: dict | None = None,
                 ) -> tuple[list[dict], kn.Knobs, dict]:
    """Layer 1 (one knob per round, CRN judge) + layer 2 (Gaussian Thompson
    on bootstrap-z rewards). Appends kind=r08 ledger rows; returns (history,
    final knobs, final score)."""
    rng = random.Random("r08-meta")
    allowed = sorted(allowed or kn.CHOICES)
    current = start
    if base is None:
        base = score_r08(cfg_for, current, "r0-base", seeds, out_root, lib_root,
                         log)
    history = []
    for r in range(1, rounds + 1):
        knob = pick_knob_gauss(rng, knob_rewards(ledger), current, allowed)
        options = kn.neighbours(current, knob)
        new_val = options[rng.randrange(len(options))]
        trial = current.with_(**{knob: new_val})
        after = score_r08(cfg_for, trial, f"r{r}-{knob}", seeds, out_root,
                          lib_root, log)
        row = r08_row("r08", base, after, round=r, knob=knob,
                      before=getattr(current, knob), after=new_val,
                      seeds=list(seeds),
                      note="r08 line B meta: CRN capped logcost_L, paired task "
                           "bootstrap, Gaussian Thompson (D-r8-3, D-r8-10)")
        append_ledger(row, ledger)
        history.append(row)
        log(f"[meta] round {r}: {knob} {row['before']} -> {new_val} logcost "
            f"{base['logcost']} -> {after['logcost']} z={row['reward']} "
            f"{'ACCEPT' if row['accepted'] else 'reject'}")
        if row["accepted"]:
            current, base = trial, after
    return history, current, base
