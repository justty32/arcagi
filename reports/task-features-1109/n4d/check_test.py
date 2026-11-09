"""N4d: run GPU-profile top1 (and all perfect top-K) programs on test with the Python DSL.

Score=1.0 in the profile allows one consistent colormap fitted over all train pairs;
we fit that map on train outputs and apply it to test outputs.
Usage: python reports/task-features-1109/n4d/check_test.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "native/tools"))
from gpu_verify import find, DEFAULT_DATA  # noqa: E402
from arcagi.dsl import background as bgc, program  # noqa: E402
from arcagi.tasks import load_task  # noqa: E402

TASKS = "2013d3e2 25d8a9c8 a79310a0 aabf363d 66e6c45b be03b35f".split()
PROF = ROOT / "reports/task-features-1109/profile"

def grid(g):
    return [list(r) for r in (g.tolist() if hasattr(g, "tolist") else g)]

def run_one(task, steps):
    prog = program.from_json(json.dumps(steps))
    gs = [e.input for e in task.train] + [e.output for e in task.train]
    outs = {"train": [], "test": []}
    with bgc.task_context(bgc.task_background(gs)):
        for k in ("train", "test"):
            for e in getattr(task, k):
                try:
                    outs[k].append(grid(program.run(prog, e.input)))
                except Exception as ex:  # noqa: BLE001
                    outs[k].append(None)
    return outs

def fit_map(pairs):
    m = {}
    for o, t in pairs:
        if o is None or len(o) != len(t) or len(o[0]) != len(t[0]):
            return None
        for ro, rt in zip(o, t):
            for a, b in zip(ro, rt):
                if m.setdefault(a, b) != b:
                    return None
    return m

def judge(task, steps):
    outs = run_one(task, steps)
    tr = [(o, grid(e.output)) for o, e in zip(outs["train"], task.train)]
    exact_train = all(o == t for o, t in tr)
    m = fit_map(tr)
    res = []
    for o, e in zip(outs["test"], task.test):
        t = grid(e.output)
        if o is None:
            res.append("err"); continue
        if o == t:
            res.append("exact"); continue
        if m is not None:
            mo = [[m.get(c, c) for c in r] for r in o]
            if mo == t:
                res.append("cmap"); continue
        same = len(o) == len(t) and len(o[0]) == len(t[0])
        diff = sum(a != b for ro, rt in zip(o, t) for a, b in zip(ro, rt)) if same else None
        res.append(f"wrong(shape={len(o)}x{len(o[0])} vs {len(t)}x{len(t[0])}, diff={diff})")
    return exact_train, m is not None, res

recs = {}
for f in PROF.glob("*-d5.jsonl"):
    for line in f.read_text().splitlines():
        r = json.loads(line)
        if r.get("task") in TASKS:
            recs[r["task"]] = r
for tid in TASKS:
    r = recs[tid]
    task = load_task(find(tid, DEFAULT_DATA))
    tops = [t for d in r["depths"] for t in d["top"]]
    tops.sort(key=lambda t: (-t["score"], -t["raw"], len(t["program"])))
    perf = [t for t in tops if t["score"] >= 1.0 - 1e-9]
    print(f"== {tid} n_test={len(task.test)} perfect_in_topK={len(perf)}")
    for i, t in enumerate(perf):
        ex, cm, res = judge(task, t["program"])
        tag = "TOP1" if i == 0 else f"#{i}"
        print(f"  {tag} raw={t['raw']:.3f} prog={json.dumps(t['program'])} train_exact={ex} train_cmap_ok={cm} test={res}")
