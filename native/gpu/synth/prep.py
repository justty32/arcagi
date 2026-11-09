"""E11 prototype: dump ARC training input grids (train+test inputs) to a flat binary for gpusynth.
usage: python3 -I prep.py <data/ARC-AGI/data/training> <out.bin> <out_index.json>
format: int32 count, then per grid: int32 task_idx, int16 ex_idx, uint8 h, uint8 w, h*w int8 cells."""
import json, os, struct, sys
src, out, idx = sys.argv[1:4]
names = sorted(f[:-5] for f in os.listdir(src) if f.endswith('.json'))
recs = []
for ti, nm in enumerate(names):
    t = json.load(open(os.path.join(src, nm + '.json')))
    for ei, ex in enumerate(t['train'] + t['test']):
        g = ex['input']
        recs.append(struct.pack('<ihBB', ti, ei, len(g), len(g[0])) + bytes((c & 255) for r in g for c in r))
with open(out, 'wb') as f:
    f.write(struct.pack('<i', len(recs)))
    for r in recs: f.write(r)
json.dump(names, open(idx, 'w'))
print(len(names), 'tasks', len(recs), 'grids')
