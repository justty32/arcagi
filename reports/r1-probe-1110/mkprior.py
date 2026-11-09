# R1 probe: P(prim | return class, depth) from gpusynth v2 rows (streamed), plus integer costs.
# usage: python3 -I mkprior.py <synth.jsonl> <prior.json> <costs.txt>
import json, math, sys
from collections import Counter, defaultdict
RET = {  # declared return class of each seed prim (seed_value.cpp PRIM_SIGS)
 **{p: 'int' for p in 'add sub mul neg mod max min len count'.split()},
 **{p: 'bool' for p in 'eq lt and or not'.split()},
 **{p: 'list' for p in 'take drop reverse cons append concat range repeat sort map filter zipwith transpose'.split()},
 **{p: 'poly' for p in 'if nth head last fold'.split()}}
NOGEN = {'map', 'filter', 'zipwith', 'fold'}  # gpusynth is first-order: no evidence either way -> neutral cost 1
WMAX, BASE = 3, 4.0                            # cost = 1 + round(log4(pmax_class / p)), clipped to [1, 3]
cnt = defaultdict(Counter)                     # (class, depth) -> prim counts
rows = 0
def walk(p, d):
    if isinstance(p, list) and p and isinstance(p[0], str) and p[0] in RET:
        cnt[(RET[p[0]], min(d, 6))][p[0]] += 1
        for k in p[1:]: walk(k, d + 1)
with open(sys.argv[1]) as f:
    for line in f:
        rows += 1
        walk(json.loads(line)['prog'], 0)
classes = sorted(set(RET.values()))
def smooth(c, cls):
    ops = [p for p in RET if RET[p] == cls]; tot = sum(c[p] for p in ops) + len(ops)
    return {p: (c[p] + 1) / tot for p in ops}
by_cd = {cls: {str(d): smooth(cnt[(cls, d)], cls) for d in range(7) if sum(cnt[(cls, d)].values())} for cls in classes}
marg = {cls: smooth(sum((cnt[(cls, d)] for d in range(7)), Counter()), cls) for cls in classes}
costs = {}
for cls in classes:
    pm = max(v for p, v in marg[cls].items() if p not in NOGEN)
    for p, v in marg[cls].items():
        costs[p] = 1 if p in NOGEN else max(1, min(WMAX, 1 + round(math.log(pm / v, BASE))))
raw = {f'{c}|{d}': dict(cnt[(c, d)]) for (c, d) in sorted(cnt)}
json.dump({'source': sys.argv[1], 'rows': rows, 'smoothing': 'add-one within return class',
           'depth': 'distance from root, 6 = 6+', 'p_by_class_depth': by_cd, 'p_by_class': marg,
           'cost_rule': 'w = 1 + round(log4(max_p_class / p_class)) clipped [1,3]; map/filter/zipwith/fold = 1 (not generated)',
           'costs': costs, 'counts': raw}, open(sys.argv[2], 'w'), indent=1)
open(sys.argv[3], 'w').write(''.join(f'{p} {w}\n' for p, w in sorted(costs.items())))
print(rows, costs)
