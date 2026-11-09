# usage: python3 -I analyze.py RAWDIR  -> prints markdown tables (copied into report.md)
import json, statistics as st, sys
O = sys.argv[1]
def load(n):
    try: return {r['task_id']: r for r in map(json.loads, open(f'{O}/{n}.jsonl')) if 'task_id' in r}
    except FileNotFoundError: return None
wall = {}
for l in open(f'{O}/wall.txt'):
    a, b, s = l.split(); wall[f'{a}-{b}'] = float(s)
def strip(r): return {k: v for k, v in r.items() if k != 'seconds'}
idr, b6 = load('id-1000000'), load('base-1000000')
if idr and b6:
    mm = [t for t in b6 if strip(b6[t]) != strip(idr.get(t, {}))]
    print(f'identity (no costs) vs arcbatch @1e6: {len(b6)} rows, {len(mm)} mismatches (all fields except seconds) {mm[:5]}')
print('| budget | engine | solved (train_ok) | test_ok | nodes-to-first median | nodes-to-first sorted | wall s | sum task s |')
print('|---|---|---:|---:|---:|---|---:|---:|')
for B in ('1000000', '10000000'):
    res = {}
    for e in ('base', 'r1', 'lam2'):
        d = load(f'{e}-{B}')
        if not d: continue
        res[e] = d
        sol = sorted(r['nodes_to_first'] for r in d.values() if r['train_ok'])
        med = st.median(sol) if sol else None
        print(f"| {B} | {e} | {len(sol)} | {sum(r['test_ok'] for r in d.values())} | {med} | {', '.join(map(str, sol))} | "
              f"{wall.get(f'{e}-{B}', float('nan')):.1f} | {sum(r['seconds'] for r in d.values()):.1f} |")
    for e2 in [e for e in ('r1', 'lam2') if e in res]:
      if 'base' in res:
        sb = {t for t, r in res['base'].items() if r['train_ok']}; sr = {t for t, r in res[e2].items() if r['train_ok']}
        tb = {t for t, r in res['base'].items() if r['test_ok']}; tr = {t for t, r in res[e2].items() if r['test_ok']}
        both = sorted(sb & sr)
        rat = [res[e2][t]['nodes_to_first'] / res['base'][t]['nodes_to_first'] for t in both]
        print(f'\n@{B}: solved only base {sorted(sb - sr)}, only {e2} {sorted(sr - sb)}; test_ok only base {sorted(tb - tr)}, only {e2} {sorted(tr - tb)}')
        print(f'@{B}: per-task {e2}/base nodes-to-first on {len(both)} common: ' +
              ', '.join(f"{t}:{res['base'][t]['nodes_to_first']}->{res[e2][t]['nodes_to_first']}" for t in both) +
              (f'; median ratio {st.median(rat):.3f}' if rat else ''))
        for t in both:
            if res['base'][t]['program'] != res[e2][t]['program']:
                print(f"   {t} program differs: base {json.dumps(res['base'][t]['program'])} | {e2} {json.dumps(res[e2][t]['program'])}")
        print()
