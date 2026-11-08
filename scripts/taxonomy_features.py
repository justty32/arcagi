"""Compute coarse per-task features for the S4 taxonomy (training + evaluation).

Writes ``reports/taxonomy-r04/features.csv`` (``wf-table/1`` CSV). The ``rough``
column is a first-pass guess of the top-level category; subagents refine it.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "ARC-AGI" / "data"
OUT = ROOT / "reports" / "taxonomy-r04" / "features.csv"

Grid = list[list[int]]

COLUMNS = (
    "task_id",
    "split",
    "n_train",
    "size_rel",
    "in_hw",
    "out_hw",
    "in_colors",
    "out_colors",
    "new_colors",
    "changed_ratio",
    "edit_kind",
    "objects_in",
    "objects_out",
    "out_sym",
    "in_sep",
    "out_in_input",
    "out_is_dihedral",
    "rough",
)


def dihedral(g: Grid) -> list[Grid]:
    rows = [list(r) for r in g]
    cols = [list(c) for c in zip(*rows)]
    return [
        [r[::-1] for r in rows],
        rows[::-1],
        [r[::-1] for r in rows[::-1]],
        cols,
        [list(r) for r in zip(*rows[::-1])],
        [list(r) for r in zip(*rows)][::-1],
        [r[::-1] for r in cols[::-1]],
    ]


def bg(g: Grid) -> int:
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def colors(g: Grid) -> set[int]:
    return {v for r in g for v in r}


def n_objects(g: Grid) -> int:
    """Count 4-connected single-colour components that are not the background."""
    b, h, w = bg(g), len(g), len(g[0])
    seen = [[False] * w for _ in range(h)]
    n = 0
    for i in range(h):
        for j in range(w):
            if seen[i][j] or g[i][j] == b:
                continue
            n += 1
            stack = [(i, j)]
            seen[i][j] = True
            while stack:
                y, x = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = y + dy, x + dx
                    if (
                        0 <= yy < h
                        and 0 <= xx < w
                        and not seen[yy][xx]
                        and g[yy][xx] == g[y][x]
                    ):
                        seen[yy][xx] = True
                        stack.append((yy, xx))
    return n


def symmetric(g: Grid) -> bool:
    lr = all(r == r[::-1] for r in g)
    ud = g == g[::-1]
    return lr or ud


def has_separator(g: Grid) -> bool:
    """True if some full row or column (not on the border only) is one non-bg colour."""
    b, h, w = bg(g), len(g), len(g[0])
    rows = [i for i in range(h) if len(set(g[i])) == 1 and g[i][0] != b]
    cols = [
        j for j in range(w) if len({g[i][j] for i in range(h)}) == 1 and g[0][j] != b
    ]
    return bool(rows or cols)


def is_subgrid(small: Grid, big: Grid) -> bool:
    sh, sw, bh, bw = len(small), len(small[0]), len(big), len(big[0])
    if sh > bh or sw > bw or (sh, sw) == (bh, bw):
        return False
    return any(
        all(big[i + y][j : j + sw] == small[y] for y in range(sh))
        for i in range(bh - sh + 1)
        for j in range(bw - sw + 1)
    )


def size_rel(pairs: list[tuple[Grid, Grid]]) -> str:
    rels = set()
    for a, b in pairs:
        (ih, iw), (oh, ow) = (len(a), len(a[0])), (len(b), len(b[0]))
        if (ih, iw) == (oh, ow):
            rels.add("same")
        elif oh % ih == 0 and ow % iw == 0:
            rels.add("multiple")
        elif ih % oh == 0 and iw % ow == 0:
            rels.add("divisor")
        elif oh <= ih and ow <= iw:
            rels.add("smaller")
        elif oh >= ih and ow >= iw:
            rels.add("larger")
        else:
            rels.add("mixed")
    return rels.pop() if len(rels) == 1 else "varies"


def edit_kind(pairs: list[tuple[Grid, Grid]]) -> tuple[str, str]:
    """Same-size tasks: changed-pixel ratio and edit kinds (add/remove/recolor)."""
    total = changed = 0
    kinds = set()
    for a, b in pairs:
        ba = bg(a)
        for ra, rb in zip(a, b):
            for x, y in zip(ra, rb):
                total += 1
                if x != y:
                    changed += 1
                    kinds.add("add" if x == ba else "remove" if y == ba else "recolor")
    return f"{changed / total:.3f}", "+".join(sorted(kinds)) or "none"


def rough(f: dict) -> str:
    rel = f["size_rel"]
    if f["out_is_dihedral"] == "1":
        return "geometry"
    if rel == "multiple":
        return "scale_tile"
    if f["out_in_input"] == "1":
        return "crop"
    if rel in ("divisor", "smaller") and f["in_sep"] == "1":
        return "split_overlay"
    if (
        rel in ("divisor", "smaller", "varies")
        and f["out_hw"] in ("1x1", "1x?", "?x1")
        or (
            rel != "same"
            and f["out_colors"] in ("1", "2")
            and f["objects_out"] in ("0", "1")
        )
    ):
        return "summary"
    if rel != "same":
        return "reshape_other"
    k = f["edit_kind"]
    if k == "add":
        return "fill" if f["new_colors"] != "0" else "draw_extend"
    if k == "remove":
        return "remove"
    if k == "recolor":
        return "recolor"
    if f["out_sym"] == "1":
        return "symmetry"
    return "same_mixed"


def features(task_id: str, split: str, task: dict) -> dict:
    pairs = [(p["input"], p["output"]) for p in task["train"]]
    f = {"task_id": task_id, "split": split, "n_train": str(len(pairs))}
    f["size_rel"] = size_rel(pairs)
    ins = {f"{len(a)}x{len(a[0])}" for a, _ in pairs}
    outs = {f"{len(b)}x{len(b[0])}" for _, b in pairs}
    f["in_hw"] = ins.pop() if len(ins) == 1 else "var"
    f["out_hw"] = (
        outs.pop()
        if len(outs) == 1
        else (
            "1x?"
            if all(len(b) == 1 for _, b in pairs)
            else "?x1"
            if all(len(b[0]) == 1 for _, b in pairs)
            else "var"
        )
    )
    f["in_colors"] = str(max(len(colors(a)) for a, _ in pairs))
    f["out_colors"] = str(max(len(colors(b)) for _, b in pairs))
    f["new_colors"] = str(len(set().union(*(colors(b) - colors(a) for a, b in pairs))))
    if f["size_rel"] == "same":
        f["changed_ratio"], f["edit_kind"] = edit_kind(pairs)
    else:
        f["changed_ratio"], f["edit_kind"] = "", ""
    f["objects_in"] = f"{sum(n_objects(a) for a, _ in pairs) / len(pairs):.1f}"
    f["objects_out"] = str(round(sum(n_objects(b) for _, b in pairs) / len(pairs)))
    f["out_sym"] = "1" if all(symmetric(b) for _, b in pairs) else "0"
    f["in_sep"] = "1" if all(has_separator(a) for a, _ in pairs) else "0"
    f["out_in_input"] = "1" if all(is_subgrid(b, a) for a, b in pairs) else "0"
    f["out_is_dihedral"] = "1" if all(b in dihedral(a) for a, b in pairs) else "0"
    f["rough"] = rough(f)
    return f


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    rows = []
    for split in ("training", "evaluation"):
        for path in sorted((args.data / split).glob("*.json")):
            rows.append(features(path.stem, split, json.loads(path.read_text())))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} tasks -> {args.out}")
    print(Counter((r["split"], r["rough"]) for r in rows).most_common())


if __name__ == "__main__":
    main()
