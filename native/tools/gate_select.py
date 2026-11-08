"""Re-select the native support gate from training data only (D-r7-18).

Steps (all on ARC training + S5 synthetic pairs, never evaluation):

1. ``prepare``: write one task file per training task whose test list is the
   real test pairs and whose ``synth`` list holds the S5 synthetic pairs
   (those in ``data_synth/training/<id>.json`` that are not original train
   pairs). The search only sees train; synth pairs only label candidates.
2. ``run``: ``arcbatch`` with the support gate off and ``--dump`` (every
   train-consistent candidate with its test hits and an output key).
3. ``select``: replay the top-1 choice of ``batch.cpp`` offline for every
   setting (guarded learner set x support_alone x support_after) and apply
   the rule fixed before looking at results:

   * population P = training tasks the r06 hybrid entry left to native
     (trace metadata source != "python"); the gate only acts there;
   * feasible = no task whose ungated top-1 is correct loses it
     (mis-blocks 0 on P);
   * among feasible settings minimise wrong answers on P; ties: fewer guarded
     kinds, then smaller (support_alone, support_after) (least intrusive).

   Wrong/correct use the real test pairs; synthetic pairs are reported as a
   second label (top-1 right on > half of them).

    python native/tools/gate_select.py prepare --out DIR
    nice -n 19 native/bin/arcbatch --tasks DIR/list.txt --configs DIR/configs.jsonl \
        --threads 6 --dump --out DIR/dump.jsonl
    python native/tools/gate_select.py select --dump DIR/dump.jsonl
"""

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path.home() / "repo/arcagi/data/ARC-AGI/data/training"
SYNTH = Path.home() / "repo/arcagi/data_synth/training"
TRACES = Path.home() / "repo/arcagi/artifacts/dsl-search-r06/training-traces.jsonl"
LEARNERS = ("colormap", "object_colormap", "local_rule", "x_vrule")
PENALIZED = ("local_rule", "x_vrule")
ALONE = (0, 1, 2, 3, 4, 6, 8, 12, 16)
AFTER = (0, 4, 8, 12, 16, 20, 24, 32, 48)
CURRENT = (("local_rule", "x_vrule"), 4, 16)  # native ee869e5 / hybrid.py


def prepare(out: Path) -> None:
    tasks = out / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    names = []
    for f in sorted(DATA.glob("*.json")):
        t = json.loads(f.read_text())
        extra = []
        sf = SYNTH / f.name
        if sf.exists():
            seen = {json.dumps(p) for p in t["train"]}
            extra = [p for p in json.loads(sf.read_text())["train"]
                     if json.dumps(p) not in seen]
        t2 = {"train": t["train"], "test": t["test"], "synth": extra}
        (tasks / f.name).write_text(json.dumps(t2))
        names.append(f"tasks/{f.name}")
    (out / "list.txt").write_text("\n".join(names) + "\n")
    cfg = {"name": "nogate", "max_nodes": 200000,
           "gate": {"support_alone": 0, "support_after": 0}}
    (out / "configs.jsonl").write_text(json.dumps(cfg) + "\n")
    print(f"{len(names)} tasks -> {out}")


def rows(step) -> int:
    n = step[0]
    if n in PENALIZED:
        return len(step[2])
    if n == "colormap":
        return len(step[1])
    if n == "object_colormap":
        return len(step[1][2])
    return 0


def top1(sols, cells, guard, a, b):
    kept = []
    votes: dict = {}
    for i, s in enumerate(sols):
        p = s["program"]
        last = p[-1]
        if last[0] in guard:
            r = rows(last)
            if r and cells / r < (a if len(p) == 1 else b):
                continue
        w = 0.5 if any(st[0] in LEARNERS for st in p) else 1.0
        votes[s["out_key"]] = votes.get(s["out_key"], 0.0) + w
        kept.append((any(st[0] in PENALIZED for st in p), s["cost"], i, s))
    if not kept:
        return None
    kept.sort(key=lambda k: (k[0], k[1], -votes[k[3]["out_key"]], k[2]))
    return kept[0][3]


def load(dump: Path):
    tasks = {}
    for line in dump.read_text().splitlines():
        r = json.loads(line)
        if r.get("summary"):
            continue
        tid = r["task_id"]
        t = json.loads((DATA / f"{tid}.json").read_text())
        cells = sum(len(e["output"]) * len(e["output"][0]) for e in t["train"])
        tasks[tid] = (cells, len(t["test"]), r.get("solutions", []))
    return tasks


def score(tasks, ids, guard, a, b):
    wrong = right = synth_bad = 0
    lost = []
    for tid in ids:
        cells, nt, sols = tasks[tid]
        base = top1(sols, cells, (), 0, 0)
        got = top1(sols, cells, guard, a, b)
        ok = got is not None and all(got["test_hits"][:nt])
        if base is not None and all(base["test_hits"][:nt]) and not ok:
            lost.append(tid)
        if got is None:
            continue
        if ok:
            right += 1
        else:
            wrong += 1
        syn = got.get("synth_hits", [])
        if syn and sum(syn) * 2 <= len(syn):
            synth_bad += 1
    return {"right": right, "wrong": wrong, "lost": lost, "synth_bad": synth_bad}


def native_population():
    ids = set()
    for line in TRACES.read_text().splitlines():
        r = json.loads(line)
        src = (r.get("trace") or {}).get("metadata", {}).get("source")
        if src != "python":
            ids.add(r["task_id"])
    return ids


def select(dump: Path) -> None:
    tasks = load(dump)
    pop = sorted(native_population() & tasks.keys())
    every = sorted(tasks)
    results = []
    for k in range(len(LEARNERS) + 1):
        for guard in itertools.combinations(LEARNERS, k):
            grid = [(0, 0)] if not guard else itertools.product(ALONE, AFTER)
            for a, b in grid:
                s = score(tasks, pop, guard, a, b)
                results.append((guard, a, b, s))
    feas = [r for r in results if not r[3]["lost"]]
    best = min(feas, key=lambda r: (r[3]["wrong"], len(r[0]), r[1], r[2]))
    guard, a, b, s = best
    print(json.dumps({"population": len(pop), "all": len(every)}))
    print("off       P:", score(tasks, pop, (), 0, 0))
    print("current   P:", score(tasks, pop, *CURRENT))
    print("selected  P:", {"guard": guard, "alone": a, "after": b, **s})
    print("off       400:", score(tasks, every, (), 0, 0))
    print("current   400:", score(tasks, every, *CURRENT))
    print("selected  400:", score(tasks, every, guard, a, b))
    ties = [r for r in feas if r[3]["wrong"] == s["wrong"]]
    print(f"settings with the same wrong count on P: {len(ties)}; guard sets:",
          sorted({r[0] for r in ties}, key=len)[:8])
    for g in [(), ("local_rule", "x_vrule"), ("colormap", "local_rule", "x_vrule"),
              LEARNERS]:
        fg = [r for r in feas if r[0] == g]
        if fg:
            r = min(fg, key=lambda r: (r[3]["wrong"], r[1], r[2]))
            print(f"best feasible for {g}: alone={r[1]} after={r[2]} "
                  f"wrong={r[3]['wrong']} right={r[3]['right']}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("select")
    s.add_argument("--dump", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "prepare":
        prepare(a.out)
    else:
        select(a.dump)


if __name__ == "__main__":
    sys.exit(main())
