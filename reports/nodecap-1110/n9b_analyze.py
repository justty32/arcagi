"""N9b: summarise sweep outputs. usage: python n9b_analyze.py OUTDIR"""
import json, sys
from pathlib import Path

out = Path(sys.argv[1])

def load(d):
    p = out / f"d{d}-traces.jsonl"
    return {r["task_id"]: r for r in map(json.loads, p.open())} if p.is_file() else None

def info(r):
    t = r.get("trace") or {}
    m = t.get("metadata") or {}
    g = m.get("guard") or {}
    a = m.get("arcsearch") or {}
    return dict(ans=(t != {} and not g.get("abstained", True)), ok=bool(r["correct"]),
                sel=json.dumps(t.get("selected"), sort_keys=True), depth=a.get("depth_reached"),
                oob=a.get("out_of_budget"), origin=m.get("top1_origin"), el=r.get("elapsed_seconds") or 0,
                err=r.get("error"), src=m.get("source"))

base = load(19)
B = {k: info(v) for k, v in base.items()} if base else {}
print("| deadline | 題數 | 作答(train過) | test對 | 假解 | 新增作答 vs d19 | 新增test對 vs d19 | 新增假解 vs d19 | 與d19衝突 | 錯誤/逾時 | 仍oob | 耗時和(s) | 新增test對的深度/來源 |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for d in (19, 40, 55, 120):
    R = load(d)
    if R is None:
        continue
    I = {k: info(v) for k, v in R.items()}
    ans = [k for k, v in I.items() if v["ans"]]
    ok = [k for k in ans if I[k]["ok"]]
    new = [k for k in ans if not B.get(k, {}).get("ans")]
    newok = [k for k in new if I[k]["ok"]]
    newfalse = [k for k in new if not I[k]["ok"]]
    conf = [k for k in ans if B.get(k, {}).get("ans") and B[k]["sel"] != I[k]["sel"]]
    errs = sum(1 for v in I.values() if v["err"])
    oob = sum(1 for v in I.values() if v["oob"])
    el = sum(v["el"] for v in I.values())
    src = ", ".join(f"{k}:d{I[k]['depth']}/{I[k]['origin']}" for k in newok)
    print(f"| {d} | {len(I)} | {len(ans)} | {len(ok)} | {len(ans)-len(ok)} | {len(new)} | {len(newok)} | {len(newfalse)} | {len(conf)} | {errs} | {oob} | {el:.0f} | {src} |")
    if newfalse or conf:
        print(f"<!-- d{d} newfalse={newfalse} conflict={conf} -->")
