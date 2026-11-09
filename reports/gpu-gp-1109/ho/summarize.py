"""Original gpgp vs gpgp-ho table for reports/gpu-gp-1109/holdout.md."""
import json, statistics as st, sys
from pathlib import Path
H = Path(__file__).resolve().parent
B = H.parent / 'bench/real'

def load(p):
    d = {}
    if not Path(p).exists(): return d
    for l in open(p):
        if l.startswith('{') and '"task"' in l:
            j = json.loads(l); d[j['task']] = j
    return d

rows = [('real-40', 'orig', B/'gp.jsonl', B/'gp-verify.jsonl')]
rows += [('real-40', c, H/f'real-{c}.jsonl', H/f'real-{c}-verify.jsonl') for c in ('mdl', 'ho')]
rows += [('on40', 'orig', H/'on40-orig.jsonl', H/'on40-orig-verify.jsonl')]
rows += [('on40', c, H/f'on40-{c}.jsonl', H/f'on40-{c}-verify.jsonl') for c in ('mdl', 'ho')]
print('| 題組 | 版本 | 跑完題數 | train solved | Python test 對 | 假 solved（train 對 test 錯） | 假 solved 比例 | solved 程式長度（中位／各題） | solve 中位秒 | 總秒 | host 拒（holdout 擋下） |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for s, c, rp, vp in rows:
    R, V = load(rp), load(vp)
    R = {k: j for k, j in R.items() if 'skipped' not in j}
    sol = [k for k, j in R.items() if j.get('solved')]
    ok = [k for k in sol if V.get(k, {}).get('test_ok')]
    lens = [R[k]['best']['depth'] for k in sol]
    ts = [R[k]['solve_seconds'] for k in sol]
    rej = sum(j.get('host_rejects', 0) for j in R.values())
    fake = len(sol) - len(ok)
    per = ','.join(f'{k[:4]}:{d}' for k, d in zip(sol, lens))
    print(f"| {s} | {c} | {len(R)} | {len(sol)} | {len(ok)} | {fake} | {fake/len(sol):.0%} | {st.median(lens) if lens else '—'} ／ {per} | {st.median(ts) if ts else '—':.3} | {sum(j['seconds'] for j in R.values()):.0f} | {rej if c=='ho' else '—'} |"
          if sol else f"| {s} | {c} | {len(R)} | 0 | 0 | 0 | — | — | — | {sum(j['seconds'] for j in R.values()):.0f} | {rej if c=='ho' else '—'} |")
    if '-v' in sys.argv:
        print('   ', c, s, 'solved', sorted(sol), 'test_ok', sorted(ok))
