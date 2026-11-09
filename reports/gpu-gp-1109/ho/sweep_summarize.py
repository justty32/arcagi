"""n3e sweep table: per lambda x task set, mean +- range over seeds. Usage: sweep_summarize.py OUTDIR [status]"""
import json, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path
O = Path(sys.argv[1]); status = sys.argv[2] if len(sys.argv) > 2 else '?'

def load(p):
    d = {}
    if p.exists():
        for l in open(p):
            if l.startswith('{') and '"task"' in l:
                try: j = json.loads(l)
                except ValueError: continue
                d[j['task']] = j
    return d

runs = defaultdict(dict)  # (set, lam) -> seed -> metrics
for f in sorted(O.glob('*-l*-s*.jsonl')):
    m = re.fullmatch(r'(\w+)-l([\d.]+)-s(\d+)\.jsonl', f.name)
    if not m: continue
    s, lam, seed = m.group(1), m.group(2), int(m.group(3))
    R = {k: j for k, j in load(f).items() if 'skipped' not in j}
    V = load(f.with_name(f.stem + '-verify.jsonl'))
    sol = [k for k, j in R.items() if j.get('solved')]
    ok = [k for k in sol if V.get(k, {}).get('test_ok')]
    lens = [R[k]['best']['depth'] for k in sol]
    runs[(s, lam)][seed] = dict(n=len(R), sol=len(sol), ok=len(ok), fake=(len(sol) - len(ok)) / len(sol) if sol else None,
                                med=st.median(lens) if lens else None, done=f.with_suffix('.done').exists(),
                                solved=sorted(sol), okset=sorted(ok))

def agg(vals, pct=False):
    v = [x for x in vals if x is not None]
    if not v: return '—'
    f = (lambda x: f'{x:.0%}') if pct else (lambda x: f'{x:.1f}' if x != int(x) else f'{int(x)}')
    return f'{f(st.mean(v))} ({f(min(v))}–{f(max(v))})'

print(f'# gpgp-ho MDL λ 掃描（n3e）\n\n狀態：{status}。每格＝各 seed 平均（最小–最大）；`--simplify min`、無 holdout、每題 20 s；real-40 預設 pop，on40 pop 524288。\n')
print('| 題組 | λ | seeds（完整/有資料） | 跑完題數 | train solved | Python test 對 | 假 solved 比例 | 中位長度 |')
print('|---|---|---|---|---|---|---|---|')
for (s, lam) in sorted(runs, key=lambda k: (k[0], float(k[1]))):
    r = runs[(s, lam)]; v = list(r.values())
    print(f"| {s} | {lam} | {sum(x['done'] for x in v)}/{len(v)} | {agg([x['n'] for x in v])} | {agg([x['sol'] for x in v])} | "
          f"{agg([x['ok'] for x in v])} | {agg([x['fake'] for x in v], True)} | {agg([x['med'] for x in v])} |")
print('\n## 各 run 明細（solved / test 對）\n')
for (s, lam) in sorted(runs, key=lambda k: (k[0], float(k[1]))):
    for seed, x in sorted(runs[(s, lam)].items()):
        print(f"- {s} λ={lam} s{seed}{'' if x['done'] else '（未完）'}: solved {','.join(t[:8] for t in x['solved']) or '—'}；test 對 {','.join(t[:8] for t in x['okset']) or '—'}")
print()
