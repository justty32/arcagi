"""Offline guard evaluation on r06 reports (r07 line C, D-r7-3).

Reads ``artifacts/<run>/<split>.json`` (each task's trace lists up to 30
train-consistent programs in rank order), re-runs those programs with
``arcagi.solvers.gated.evaluate`` (test inputs, plus 4 ``data_synth`` pairs on
training), then applies ``guard.judge`` under every gate set of interest.
No solver search is re-run.

Outputs (``--out``, default ``reports/gate-r07``):

* ``<split>-tasks.csv``: one row per task with candidates: baseline, outcome
  under all gates (block / pass / switch), per-gate single outcomes, reasons;
* ``<split>-summary.json``: counts per gate set.

Usage: ``uv run python scripts/r07_gate_eval.py --split training``
"""

import argparse
import csv
import json
import sys
from itertools import combinations
from pathlib import Path

from arcagi.solvers import gated, guard
from arcagi.tasks import load_task

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ARC-AGI" / "data"

# Outcome labels (per task, relative to the r06 top-1):
#   pass          answer unchanged
#   block_wrong   wrong answer removed (abstain)          -> 擋錯
#   switch_wrong  wrong answer replaced by another wrong  -> 擋錯 (still wrong)
#   switch_right  wrong answer replaced by the right one  -> 改判對 (+1)
#   block_right   right answer removed or replaced        -> 誤擋 (-1)


def outcome(base_ok: bool, verdict: guard.Verdict, base_pred, expected) -> str:
    new_ok = not verdict.abstained and _norm(verdict.predictions) == _norm(expected)
    if verdict.abstained:
        return "block_right" if base_ok else "block_wrong"
    same = _norm(verdict.predictions) == _norm(base_pred)
    if same:
        return "pass"
    if base_ok:
        return "pass" if new_ok else "block_right"
    return "switch_right" if new_ok else "switch_wrong"


def _norm(grids):
    return [[list(row) for row in g] for g in grids]


def gate_sets() -> dict[str, tuple[tuple[str, ...], dict]]:
    """Gate set name -> (gates, extra ``judge`` kwargs)."""
    sets = {"none": ((), {})}
    for g in guard.GATES:
        sets[g] = ((g,), {"synth_demote": False})
    sets["synth(demote)"] = (("synth",), {"synth_demote": True})
    for a, b in combinations(guard.GATES, 2):
        sets[f"{a}+{b}"] = ((a, b), {"synth_demote": False})
    sets["support+unseen+synth"] = (
        ("support", "unseen", "synth"),
        {"synth_demote": False},
    )
    sets["support+unseen+table+synth(demote)"] = (
        ("support", "unseen", "synth", "table"),
        {"synth_demote": True},
    )
    sets["default"] = (
        guard.DEFAULT_GATES,
        {"synth_demote": guard.DEFAULT_SYNTH_DEMOTE},
    )
    sets["all"] = (guard.GATES, {"synth_demote": False})
    return sets


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split", choices=["training", "evaluation"], required=True)
    p.add_argument("--run", default="dsl-search-r06")
    p.add_argument("--out", type=Path, default=ROOT / "reports" / "gate-r07")
    p.add_argument(
        "--primary", default="default", help="gate set for the main CSV column"
    )
    args = p.parse_args(argv)
    report = json.loads(
        (ROOT / "artifacts" / args.run / f"{args.split}.json").read_text()
    )
    sets = gate_sets()
    tally = {name: {} for name in sets}
    rows = []
    no_info = []
    for entry in report["tasks"]:
        tid = entry["task_id"]
        programs = gated.trace_programs(entry.get("trace"))
        if not programs:
            continue
        task = load_task(DATA / args.split / f"{tid}.json")
        solver_task = task.to_solver_task()
        expected = [e.output for e in task.test]
        base_pred = [t["prediction"] for t in entry["tests"]]
        base_ok = bool(entry["correct"])
        synth = gated.synth_pairs(tid) if args.split == "training" else []
        cands = gated.evaluate(solver_task, programs, synth)
        train = [(e.input, e.output) for e in task.train]
        top_ok = (
            bool(cands)
            and cands[0].tests is not None
            and _norm(cands[0].tests) == _norm(base_pred)
        )
        if not top_ok:
            # Re-run does not reproduce the recorded top-1: guard has no
            # faithful view of this task; keep the r06 answer (pass).
            no_info.append(tid)
        results = {}
        for name, (gs, kw) in sets.items():
            if top_ok:
                v = guard.judge(cands, train, solver_task.test, gates=gs, **kw)
                results[name] = (outcome(base_ok, v, base_pred, expected), v)
            else:
                results[name] = ("pass", None)
            tally[name][results[name][0]] = tally[name].get(results[name][0], 0) + 1
        main_out, v = results[args.primary]
        rows.append(
            {
                "task_id": tid,
                "source": entry["trace"]["metadata"].get("source"),
                "base_correct": int(base_ok),
                "programs": len(programs),
                "rerun": len(cands),
                "faithful": int(top_ok),
                "top1_support": guard.support_counts(cands).get(
                    guard._key(cands[0].tests), 0
                )
                if top_ok
                else "",
                "top1_synth": f"{cands[0].synth_ok}/{cands[0].synth_total}"
                if top_ok
                else "",
                "outcome": main_out,
                "verdict": "pass"
                if main_out == "pass"
                else "block"
                if v is not None and v.abstained
                else "switch",
                "reason": v.reason if v else "re-run not faithful; r06 answer kept",
                **{f"only_{g}": results[g][0] for g in guard.GATES},
            }
        )
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / f"{args.split}-tasks.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    base_correct = report["tasks_correct"]
    summary = {
        "split": args.split,
        "run": args.run,
        "base_correct": base_correct,
        "tasks_with_candidates": len(rows),
        "base_wrong_with_answer": sum(1 for r in rows if not r["base_correct"]),
        "not_faithful": no_info,
        "sets": {},
    }
    for name, t in tally.items():
        blocked = (
            t.get("block_wrong", 0)
            + t.get("switch_wrong", 0)
            + t.get("switch_right", 0)
        )
        summary["sets"][name] = {
            "gates": list(sets[name][0]),
            **sets[name][1],
            **t,
            "stopped_wrong": blocked,
            "false_blocks": t.get("block_right", 0),
            "net_correct": base_correct
            - t.get("block_right", 0)
            + t.get("switch_right", 0),
        }
    (args.out / f"{args.split}-summary.json").write_text(
        json.dumps(summary, indent=1) + "\n"
    )
    w = sys.stdout.write
    w(
        f"{args.split}: base {base_correct}, candidates {len(rows)}, "
        f"not faithful {len(no_info)}\n"
    )
    for name, s in summary["sets"].items():
        w(
            f"  {name:24s} stopped_wrong {s['stopped_wrong']:3d}  false_blocks "
            f"{s['false_blocks']:3d}  switch_right {s.get('switch_right', 0):2d}  "
            f"net {s['net_correct']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
