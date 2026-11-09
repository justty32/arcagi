"""N4e: GPU exhaustive results as a gated candidate source -- offline measurement only.

Sources: reports/native-cuda-1109/overnight/phase-A.jsonl (depth5 dedup3 budget120),
filler/{train,eval}-open-d6.jsonl and overnight/phase-B.jsonl (depth 6, open tasks).
Per task the GPU programs (``best`` first, then ``samples``; samples are capped at 5
by gpusearch, so support counts are lower bounds) are re-run with the mainline's own
``arcagi.solvers.gated.evaluate`` (drops programs that fail train on the Python DSL,
computes test outputs and table stats) and judged with ``arcagi.solvers.guard.judge``.

Rules:
  R0  gates=()                      -> top-1 = first train-passing GPU program
  R1  gates={"table","unseen"}      -> guard as mainline r07 minus synth (GPU has no synth
                                       pairs here; mainline synth only demotes anyway)
  R2  R1, then the chosen test output must be produced by >=2 distinct GPU programs
      (guard.support_counts over all re-run candidates); first trusted candidate with
      support>=2 is taken, else abstain.
Mainline: training = artifacts/gated-r07/training-traces.jsonl, evaluation =
artifacts/gated-r08/evaluation-traces.jsonl (per-test ``tests_correct``).
Usage: uv run --no-sync python reports/task-features-1109/n4e/gated_rules.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
from arcagi.solvers import gated, guard
from arcagi.tasks import load_task

NC = ROOT / "reports/native-cuda-1109"
SRC = [NC / "overnight/phase-A.jsonl", NC / "filler/train-open-d6.jsonl",
       NC / "filler/eval-open-d6.jsonl", NC / "overnight/phase-B.jsonl"]
DATA = ROOT / "data/ARC-AGI/data"
MAIN = {"training": ROOT / "artifacts/gated-r07/training-traces.jsonl",
        "evaluation": ROOT / "artifacts/gated-r08/evaluation-traces.jsonl"}
OUT = Path(__file__).with_name("per_task.jsonl")

def split_of(tid):
    for s in ("training", "evaluation"):
        if (DATA / s / f"{tid}.json").exists():
            return s
    raise FileNotFoundError(tid)

progs: dict[str, list[str]] = {}
srcs: dict[str, list[str]] = {}
for f in SRC:
    for line in f.read_text().splitlines():
        r = json.loads(line)
        ps = ([r["best"]["program"]] if "best" in r else []) + list(r.get("samples", []))
        if not ps:
            continue
        lst = progs.setdefault(r["task"], [])
        srcs.setdefault(r["task"], []).append(f.stem)
        for p in ps:
            t = json.dumps(p)
            if t not in lst:
                lst.append(t)

main = {}
for s, f in MAIN.items():
    for line in f.read_text().splitlines():
        r = json.loads(line)
        main[r["task_id"]] = r["tests_correct"]

def lists(g):
    return [list(r) for r in g]

def pick(verdict, cands, rule):
    if rule == "R2":
        counts = guard.support_counts(cands)
        for j in verdict.ranked:
            if j.trusted and j.candidate.tests is not None and counts.get(guard._key(j.candidate.tests), 0) >= 2:
                return j
        return None
    return None if verdict.abstained else verdict.chosen

rows = []
for tid, plist in sorted(progs.items()):
    split = split_of(tid)
    full = load_task(DATA / split / f"{tid}.json")
    st = gated.SolverTask(tid, full.train, tuple(e.input for e in full.test))
    truth = [lists(e.output) for e in full.test]
    cands = gated.evaluate(st, [(p, "gpu") for p in plist])
    train = [(e.input, e.output) for e in full.train]
    rec = {"task": tid, "split": split, "src": srcs[tid], "n_gpu": len(plist), "n_pass": len(cands),
           "main": main.get(tid), "cands": []}
    counts = guard.support_counts(cands)
    for c in cands:
        ok = None if c.tests is None else [lists(a) == b for a, b in zip(c.tests, truth)]
        rec["cands"].append({"program": c.program, "test_ok": ok, "table": c.table,
                             "support": counts.get(guard._key(c.tests), 0) if c.tests is not None else 0})
    for rule, gates in (("R0", ()), ("R1", ("table", "unseen")), ("R2", ("table", "unseen"))):
        v = guard.judge(cands, train, st.test, gates=set(gates))
        j = pick(v, cands, rule)
        if j is None or j.candidate.tests is None:
            rec[rule] = None
        else:
            rec[rule] = [lists(a) == b for a, b in zip(j.candidate.tests, truth)]
        rec[rule + "_reasons"] = [r for x in v.ranked for r in x.reasons][:6]
    rows.append(rec)
OUT.write_text("".join(json.dumps(r) + "\n" for r in rows))

def summarize(split):
    print(f"\n== {split}")
    rs = [r for r in rows if r["split"] == split]
    print(f"tasks with GPU programs={len(rs)}  with >=1 Python-verified train-pass={sum(r['n_pass']>0 for r in rs)}")
    for rule in ("R0", "R1", "R2"):
        new_t = new_tasks = false_t = false_tasks = confl = confl_t = answered = 0
        newl, falsel, confll = [], [], []
        for r in rs:
            a, m = r[rule], r["main"]
            if a is None:
                continue
            answered += 1
            if m is None:
                m = [False] * len(a)
            solved = all(m)
            if not solved:
                gain = sum(x and not y for x, y in zip(a, m))
                bad = sum((not x) and (not y) for x, y in zip(a, m))
                new_t += gain; false_t += bad
                if all(a): new_tasks += 1; newl.append(r["task"])
                if not all(a): false_tasks += 1; falsel.append(r["task"])
            else:
                c = sum(not x for x in a)
                if c: confl += 1; confl_t += c; confll.append(r["task"])
        print(f"{rule}: answered={answered} | mainline-unsolved: +tests_right={new_t} (+tasks={new_tasks} {newl}) "
              f"false(train ok,test wrong) tasks={false_tasks} tests={false_t} {falsel} | "
              f"mainline-solved conflicts tasks={confl} tests={confl_t} {confll}")

for s in ("training", "evaluation"):
    summarize(s)
