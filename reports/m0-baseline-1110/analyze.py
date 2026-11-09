"""M0: raw m0prof outputs -> buckets.csv, nodes_to_first.csv, summary on stdout.
usage: python3 -I analyze.py RAWDIR OUTDIR [REFDIR]   (REFDIR: n5c res-<B>-cpu-1.jsonl for a row cross-check)"""
import csv, json, os, statistics as st, sys
raw, out = sys.argv[1], sys.argv[2]; ref = sys.argv[3] if len(sys.argv) > 3 else None
SIX = {"eval_fo": "1 first-order eval", "eval_lambda": "2 lambda eval (map/zipwith/filter/fold)",
       "lam_pool": "2 lambda eval (map/zipwith/filter/fold)", "eval_if": "3 if eval", "eval_lib": "4 library block",
       "choose_unify": "5 unify/combinatorics bookkeeping", "bank_offer": "5 unify/combinatorics bookkeeping",
       "dedup_hash": "6 dedup hash", "cond": "other (cond_witness)"}
B = [1000000, 10000000]
def rows(p): return [r for r in map(json.loads, open(p)) if "task_id" in r]
brows, per = [], {}
for b in B:
    prof = [json.loads(l) for l in open(f"{raw}/m0-{b}.err") if l.startswith('{"m0prof"')][-1]
    tot = sum(prof["sec"].values())
    for k, v in prof["sec"].items():
        brows.append({"budget": b, "bucket": k, "six_bucket": SIX[k], "cpu_seconds": round(v, 3),
                      "share": round(v / tot, 4), "eval_calls": prof["calls"][k]})
    six = {}
    for k, v in prof["sec"].items(): six[SIX[k]] = six.get(SIX[k], 0) + v
    R = rows(f"{raw}/m0-{b}.jsonl")
    ntf = [r["nodes_to_first"] for r in R if r["nodes_to_first"] is not None]
    print(f"## budget {b}: wall {prof['wall_s']:.1f}s, enum cpu {tot:.1f}s, nodes {prof['nodes']:.3g}, segs {prof['segs']}")
    for k in sorted(six): print(f"  {k:45s} {six[k]:9.2f}s {100*six[k]/tot:5.1f}%")
    print(f"  solved(train_ok) {sum(r['train_ok'] for r in R)}, test_ok {sum(r['test_ok'] for r in R)}, "
          f"nodes_to_first n={len(ntf)} median {st.median(ntf) if ntf else None}")
    h = prof["seg_hist_log2"]; nz = [i for i, x in enumerate(h) if x]
    print("  segment-size hist (bit length of nodes per (op,split) segment):", {i: h[i] for i in nz})
    print("  nodes per program size:", {i: x for i, x in enumerate(prof["size_nodes"]) if x})
    for r in R: per.setdefault(r["task_id"], {})[b] = r
    if ref and os.path.exists(f"{ref}/res-{b}-cpu-1.jsonl"):
        strip = lambda r: {k: v for k, v in r.items() if k not in ("seconds", "eval_steps")}
        Q = {r["task_id"]: strip(r) for r in rows(f"{ref}/res-{b}-cpu-1.jsonl")}
        print(f"  row mismatch vs plain arcbatch ({ref}/res-{b}-cpu-1.jsonl): {sum(strip(r) != Q.get(r['task_id']) for r in R)}")
with open(f"{out}/buckets.csv", "w", newline="") as f:
    w = csv.DictWriter(f, ["budget", "bucket", "six_bucket", "cpu_seconds", "share", "eval_calls"]); w.writeheader(); w.writerows(brows)
with open(f"{out}/nodes_to_first.csv", "w", newline="") as f:
    cols = ["task_id"] + [f"{k}_{b:.0e}".replace("+0", "") for b in B for k in ("nodes_to_first", "nodes", "train_ok", "test_ok", "seconds")]
    w = csv.writer(f); w.writerow(cols)
    for t in sorted(per):
        line = [t]
        for b in B:
            r = per[t].get(b, {})
            line += [r.get("nodes_to_first") if r.get("nodes_to_first") is not None else "", r.get("nodes", ""),
                     r.get("train_ok", ""), r.get("test_ok", ""), round(r["seconds"], 3) if "seconds" in r else ""]
        w.writerow(line)
