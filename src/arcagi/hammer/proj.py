"""Three-projection residual fingerprint of a task (train pairs only).

fingerprint(task) -> {"pairs": [per-pair dict], "agg": {feature: mean}}.
Projections (per train pair, input grid I, output grid O, bg = most common
colour of a grid, ties -> smaller colour):
  proj_shape   : same (1/0), log2(Oh/Ih), log2(Ow/Iw), O area / I area capped
                 at 16 then scaled /16.
  proj_palette : added = |colours(O) - colours(I)|, removed = |colours(I) -
                 colours(O)| (both capped at 5, scaled /5), bg_changed (1/0).
  proj_fg_mask : fg_frac_out = fraction of O cells != bg(O); fg_iou = IoU of
                 the foreground masks when shapes are equal, else 0 and
                 fg_iou_valid = 0.
Each projection is stored under its name in the pair dict. "agg" is the mean
over train pairs of the flat feature vector.

distance(fp_a, fp_b) = sum over features f of |agg_a[f] - agg_b[f]| (L1 over
the 12 aggregated features, no weights). Deterministic, symmetric, pure stdlib.
"""

import math

FEATURES = (
    "same_shape", "log_h", "log_w", "area_ratio",
    "added", "removed", "bg_changed",
    "fg_frac_out", "fg_iou", "fg_iou_valid",
    "same_palette", "n_colors_out",
)


def _bg(g):
    cnt = {}
    for row in g:
        for v in row:
            cnt[v] = cnt.get(v, 0) + 1
    return min(cnt, key=lambda c: (-cnt[c], c)) if cnt else 0


def _colors(g):
    return {v for row in g for v in row}


def _pair(i, o):
    ih, iw, oh, ow = len(i), len(i[0]), len(o), len(o[0])
    same = int((ih, iw) == (oh, ow))
    shape = {"same_shape": same, "log_h": math.log2(oh / ih),
             "log_w": math.log2(ow / iw),
             "area_ratio": min(oh * ow / (ih * iw), 16.0) / 16.0}
    ci, co = _colors(i), _colors(o)
    bi, bo = _bg(i), _bg(o)
    pal = {"added": min(len(co - ci), 5) / 5, "removed": min(len(ci - co), 5) / 5,
           "bg_changed": int(bi != bo), "same_palette": int(ci == co),
           "n_colors_out": min(len(co), 10) / 10}
    fo = sum(v != bo for row in o for v in row)
    fg = {"fg_frac_out": fo / (oh * ow), "fg_iou": 0.0, "fg_iou_valid": 0}
    if same:
        inter = union = 0
        for r in range(ih):
            for c in range(iw):
                a, b = i[r][c] != bi, o[r][c] != bo
                inter += a and b
                union += a or b
        fg["fg_iou"] = inter / union if union else 1.0
        fg["fg_iou_valid"] = 1
    return {"proj_shape": shape, "proj_palette": pal, "proj_fg_mask": fg}


def fingerprint(task: dict) -> dict:
    pairs = [_pair(p["input"], p["output"]) for p in task["train"]]
    agg = {f: 0.0 for f in FEATURES}
    for p in pairs:
        for proj in p.values():
            for k, v in proj.items():
                agg[k] += v / len(pairs)
    return {"pairs": pairs, "agg": agg}


def distance(fp_a: dict, fp_b: dict) -> float:
    return sum(abs(fp_a["agg"][f] - fp_b["agg"][f]) for f in FEATURES)
