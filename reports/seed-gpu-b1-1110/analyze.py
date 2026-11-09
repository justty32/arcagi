import json, glob, statistics as st, sys, collections
D = sys.argv[1]
wall = collections.defaultdict(list)
for l in open(f"{D}/wall.txt"):
    b, m, r, w = l.split()[:4]; wall[(b, m)].append(float(w))
def rows(f):
    R = {}; S = None
    for l in open(f):
        j = json.loads(l)
        if j.get("summary"): S = j
        else: R[j["task_id"]] = j
    return R, S
KEYS = ["program", "train_ok", "test_ok", "nodes", "nodes_to_first", "near"]
for b in ["1000000", "10000000"]:
    ref = None
    print(f"\n## budget {b}")
    print("| mode | runs | wall s median (min..max) | task_seconds median | nodes | nodes/s (wall) | train_ok | test_ok | to-first s (solved, sum med) | row mismatches vs cpu run1 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for m in ["cpu", "gpu", "b1", "b1hi"]:
        fs = sorted(glob.glob(f"{D}/res-{b}-{m}-*.jsonl"))
        if not fs: continue
        ts, mism, tf = [], 0, []
        for f in fs:
            R, S = rows(f)
            if ref is None: ref = R
            ts.append(S["task_seconds"])
            for k, r in R.items():
                if any(r.get(x) != ref[k].get(x) for x in KEYS): mism += 1; print("MISMATCH", m, f, k, file=sys.stderr)
            tf.append(sum(r["seconds"] for r in R.values() if r["train_ok"]))
        w = wall[(b, m)]
        print(f"| {m} | {len(fs)} | {st.median(w):.1f} ({min(w):.1f}..{max(w):.1f}) | {st.median(ts):.1f} | {S['nodes']:.0f} | {S['nodes']/st.median(w)/1e6:.2f}M | {S['train_ok']} | {S['solved']} | {st.median(tf):.2f} | {mism} |")
    if ref: print("train_ok tasks:", sorted(k for k, r in ref.items() if r["train_ok"]), "test_ok:", sorted(k for k, r in ref.items() if r["test_ok"]))
# --seed-prof runs (prof-<budget>-<mode>.err): upload / launch counters
for f in sorted(glob.glob(f"{D}/prof-*.err")):
    for l in open(f):
        if l.startswith("{"): print(f.split("/")[-1], l.strip())
