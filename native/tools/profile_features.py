"""Build the per-task feature table (wf-table/1 CSV) from gpuprofile JSONL.

Usage: profile_features.py PROFILE.jsonl [MORE.jsonl ...] --out features.csv
                           [--data-root data/ARC-AGI/data] [--solved LIST ...]

Later JSONL files override earlier ones per task when they reach a higher
best score or a deeper search (used to merge the deeper overnight pass).
Input/output grid features are computed here on the CPU from the task JSON.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

OPS = ["flip_lr", "flip_ud", "transpose", "rot90", "rot180", "rot270", "anti_transpose",
       "upscale", "tile", "downscale", "mirror_tile", "crop_bbox", "gravity",
       "fill_enclosed", "split_overlay", "self_tile", "colormap"]
MAXD = 6


def bg_of(g):
    cnt = Counter(c for row in g for c in row)
    return max(cnt, key=lambda c: (cnt[c], c == 0, -c))


def objects(g):
    """4-connected same-colour components that are not background."""
    h, w = len(g), len(g[0])
    bg = bg_of(g)
    seen = [[False] * w for _ in range(h)]
    n = 0
    for y in range(h):
        for x in range(w):
            if seen[y][x] or g[y][x] == bg:
                continue
            n += 1
            stack = [(y, x)]
            seen[y][x] = True
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny][nx] and g[ny][nx] == g[cy][cx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
    return n


def identity_score(train):
    """gpuprofile's score for the empty program (cells after best colormap)."""
    cnt: Counter = Counter()
    denom = 0
    for e in train:
        a, b = e["input"], e["output"]
        denom += max(len(a) * len(a[0]), len(b) * len(b[0]))
        for y in range(min(len(a), len(b))):
            for x in range(min(len(a[0]), len(b[0]))):
                cnt[(a[y][x], b[y][x])] += 1
    best: dict = {}
    for (s, t), n in cnt.items():
        best[s] = max(best.get(s, 0), n)
    return sum(best.values()) / denom if denom else 0.0


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def grid_features(task):
    tr = task["train"]
    ins = [e["input"] for e in tr]
    outs = [e["output"] for e in tr]
    shp = lambda g: (len(g), len(g[0]))
    cols = lambda gs: set(c for g in gs for row in g for c in row)
    same_shape = all(shp(a) == shp(b) for a, b in zip(ins, outs))
    ry = {shp(b)[0] / shp(a)[0] for a, b in zip(ins, outs)}
    rx = {shp(b)[1] / shp(a)[1] for a, b in zip(ins, outs)}
    diff = [sum(a[y][x] != b[y][x] for y in range(len(a)) for x in range(len(a[0]))) / (len(a) * len(a[0]))
            for a, b in zip(ins, outs) if shp(a) == shp(b)]
    cin, cout = cols(ins), cols(outs)
    return {
        "n_train": len(tr), "n_test": len(task["test"]),
        "in_h_mean": round(mean([shp(g)[0] for g in ins]), 2), "in_w_mean": round(mean([shp(g)[1] for g in ins]), 2),
        "out_h_mean": round(mean([shp(g)[0] for g in outs]), 2), "out_w_mean": round(mean([shp(g)[1] for g in outs]), 2),
        "same_shape": int(same_shape),
        "out_shape_const": int(len({shp(g) for g in outs}) == 1),
        "size_ratio_y": round(ry.pop(), 4) if len(ry) == 1 else "",
        "size_ratio_x": round(rx.pop(), 4) if len(rx) == 1 else "",
        "area_ratio_mean": round(mean([shp(b)[0] * shp(b)[1] / (shp(a)[0] * shp(a)[1]) for a, b in zip(ins, outs)]), 4),
        "colors_in": len(cin), "colors_out": len(cout),
        "colors_new": len(cout - cin), "colors_dropped": len(cin - cout),
        "objects_in_mean": round(mean([objects(g) for g in ins]), 2),
        "objects_out_mean": round(mean([objects(g) for g in outs]), 2),
        "changed_cell_frac": round(mean(diff), 4) if diff else "",
        "identity_score": round(identity_score(tr), 4),
    }


def prog_str(p):
    return ">".join(s[0] if isinstance(s, list) else str(s) for s in p)


def profile_features(rec):
    depths = rec.get("depths", [])
    tops = [t for d in depths for t in d.get("top", [])]
    tops.sort(key=lambda t: (-t["score"], -t["raw"], len(t["ops"])))
    f = {
        "alphabet": rec.get("alphabet", ""), "dedup": rec.get("dedup", ""), "max_depth": rec.get("max_depth", ""),
        "depth_reached": max([d["d"] for d in depths if d.get("complete")], default=0),
        "seconds": round(rec.get("seconds", 0), 2),
        "space_total": int(sum(d.get("space", 0) for d in depths)),
        "valid_total": int(sum(d.get("valid", 0) for d in depths)),
        "best": round(rec.get("best", 0), 4), "best_depth": rec.get("best_depth", 0),
        "perfect_depth": rec.get("perfect_depth", 0),
        "perfect_total": int(sum(d.get("perfect", 0) for d in depths)),
        "ge90_total": int(sum(d.get("ge", {}).get("90", 0) for d in depths)),
        "top1_score": round(tops[0]["score"], 4) if tops else "",
        "top1_raw": round(tops[0]["raw"], 4) if tops else "",
        "top1_program": prog_str(tops[0]["program"]) if tops else "",
        "n_top": len(tops),
    }
    for k in range(1, MAXD + 1):
        d = next((x for x in depths if x["d"] == k), None)
        f[f"best_d{k}"] = round(d["best"], 4) if d else ""
    for op in OPS:
        f[f"prim_{op}"] = round(sum(op in t["ops"] for t in tops) / len(tops), 4) if tops else ""
    return f


def better(new, old):
    key = lambda r: (r.get("best", 0), max([d["d"] for d in r.get("depths", []) if d.get("complete")], default=0))
    return key(new) >= key(old)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profiles", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-root", default="data/ARC-AGI/data")
    ap.add_argument("--solved", nargs="*", default=[], help="task-id lists solved by the main line")
    a = ap.parse_args()
    recs: dict = {}
    for p in a.profiles:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if "depths" not in r and r["task"] in recs:
                continue
            if r["task"] not in recs or better(r, recs[r["task"]]):
                recs[r["task"]] = r
    solved = set()
    for s in a.solved:
        solved |= {l.split()[0] for l in Path(s).read_text().splitlines() if l.strip() and not l.startswith("#")}
    root = Path(a.data_root)
    rows = []
    for split in ("training", "evaluation"):
        for f in sorted((root / split).glob("*.json")):
            tid = f.stem
            row = {"task": tid, "split": split, "mainline_solved": int(tid in solved) if a.solved else ""}
            row.update(grid_features(json.loads(f.read_text())))
            r = recs.get(tid)
            row["profiled"] = int(bool(r and "depths" in r))
            if r and "depths" in r:
                row.update(profile_features(r))
            rows.append(row)
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"rows": len(rows), "profiled": sum(r["profiled"] for r in rows), "columns": len(cols)}))


if __name__ == "__main__":
    main()
