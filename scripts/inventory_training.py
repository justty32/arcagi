"""Build the ARC-AGI-1 training inventory: per-task features CSV and an HTML report."""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "ARC-AGI" / "data" / "training"
DEFAULT_REARC = ROOT / "vendor" / "re-arc"
DEFAULT_OUT = ROOT / "docs" / "inventory"

Grid = list[list[int]]

# Category ids in detection priority order; labels live in inventory_render.py.
CATEGORIES = (
    "geometry",
    "colormap",
    "scale_tile",
    "crop",
    "symmetry",
    "fill",
    "remove",
    "recolor",
    "move",
    "same_mixed",
    "split_overlay",
    "summary",
    "shrink_other",
    "grow_other",
)

COLUMNS = (
    "task_id",
    "category",
    "detail",
    "symbolic",
    "n_train",
    "n_test",
    "in_h_max",
    "in_w_max",
    "out_h_max",
    "out_w_max",
    "size_relation",
    "in_colors",
    "out_colors",
    "new_out_colors",
    "changed_ratio",
    "objects_mean",
    "rearc_verifier_lines",
    "rearc_generator_lines",
)


def transforms(grid: Grid) -> dict[str, Grid]:
    """Return the eight dihedral transforms of a grid keyed by name."""
    rows = [list(r) for r in grid]
    cols = [list(c) for c in zip(*rows, strict=True)]
    return {
        "identity": rows,
        "rot90": [list(r) for r in zip(*rows[::-1], strict=True)],
        "rot180": [r[::-1] for r in rows[::-1]],
        "rot270": [list(r) for r in zip(*rows, strict=True)][::-1],
        "flip_lr": [r[::-1] for r in rows],
        "flip_ud": rows[::-1],
        "transpose": cols,
        "anti_transpose": [r[::-1] for r in cols[::-1]],
    }


def shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0])


def background(grid: Grid) -> int:
    return Counter(v for row in grid for v in row).most_common(1)[0][0]


def colors(grid: Grid) -> set[int]:
    return {v for row in grid for v in row}


def is_geometry(pairs: list[tuple[Grid, Grid]]) -> str | None:
    for name in transforms(pairs[0][0]):
        if name == "identity":
            continue
        if all(transforms(i)[name] == o for i, o in pairs):
            return name
    return None


def is_colormap(pairs: list[tuple[Grid, Grid]]) -> str | None:
    mapping: dict[int, int] = {}
    for i, o in pairs:
        if shape(i) != shape(o):
            return None
        for ri, ro in zip(i, o, strict=True):
            for a, b in zip(ri, ro, strict=True):
                if mapping.setdefault(a, b) != b:
                    return None
    changed = {a: b for a, b in mapping.items() if a != b}
    if not changed:
        return None
    return " ".join(f"{a}>{b}" for a, b in sorted(changed.items()))


def blocks(out: Grid, h: int, w: int) -> list[Grid]:
    oh, ow = shape(out)
    return [
        [row[c : c + w] for row in out[r : r + h]]
        for r in range(0, oh, h)
        for c in range(0, ow, w)
    ]


def is_scale_tile(pairs: list[tuple[Grid, Grid]]) -> str | None:
    kinds = set()
    for i, o in pairs:
        (h, w), (oh, ow) = shape(i), shape(o)
        if oh % h or ow % w or (oh, ow) == (h, w):
            return None
        kh, kw = oh // h, ow // w
        scaled = [[v for v in row for _ in range(kw)] for row in i for _ in range(kh)]
        if scaled == o:
            kinds.add("scale")
            continue
        options = [t for t in transforms(i).values() if shape(t) == (h, w)]
        parts = blocks(o, h, w)
        if all(b in options for b in parts):
            kinds.add("tile")
            continue
        if all(b in options or len(colors(b)) == 1 for b in parts):
            kinds.add("masked tile")
            continue
        return None
    return "+".join(sorted(kinds))


def contains(big: Grid, small: Grid) -> bool:
    (bh, bw), (sh, sw) = shape(big), shape(small)
    if sh > bh or sw > bw:
        return False
    for r in range(bh - sh + 1):
        for c in range(bw - sw + 1):
            if all(big[r + k][c : c + sw] == small[k] for k in range(sh)):
                return True
    return False


def is_crop(pairs: list[tuple[Grid, Grid]]) -> bool:
    return all(shape(o) != shape(i) and contains(i, o) for i, o in pairs)


def symmetric(grid: Grid) -> bool:
    if len(colors(grid)) == 1:
        return False
    t = transforms(grid)
    return any(
        t[name] == grid
        for name in ("flip_lr", "flip_ud", "rot180", "transpose")
        if shape(t[name]) == shape(grid)
    )


def fills_enclosed(i: Grid, o: Grid) -> bool:
    """True when every changed cell is background not reachable from the border."""
    h, w = shape(i)
    bg = background(i)
    outside = set()
    stack = [
        (r, c)
        for r in range(h)
        for c in range(w)
        if (r in (0, h - 1) or c in (0, w - 1)) and i[r][c] == bg
    ]
    while stack:
        cell = stack.pop()
        if cell in outside:
            continue
        outside.add(cell)
        r, c = cell
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= nr < h and 0 <= nc < w and i[nr][nc] == bg:
                stack.append((nr, nc))
    changed = [(r, c) for r in range(h) for c in range(w) if i[r][c] != o[r][c]]
    return bool(changed) and not any(cell in outside for cell in changed)


def split_parts(i: Grid, o: Grid) -> bool:
    """True when the input is k equal panels (optionally separated) of output size."""
    (h, w), (oh, ow) = shape(i), shape(o)
    for k in range(2, 5):
        if w == ow * k or w == ow * k + (k - 1):
            if h == oh:
                return True
        if h == oh * k or h == oh * k + (k - 1):
            if w == ow:
                return True
    return False


def same_size_kind(pairs: list[tuple[Grid, Grid]]) -> tuple[str, str]:
    """Classify same-size tasks by which cells change and how."""
    if all(symmetric(o) and not symmetric(i) for i, o in pairs):
        return "symmetry", ""
    adds = removes = recolors = 0
    for i, o in pairs:
        bg = background(i)
        for ri, ro in zip(i, o, strict=True):
            for a, b in zip(ri, ro, strict=True):
                if a == b:
                    continue
                if a == bg:
                    adds += 1
                elif b == bg:
                    removes += 1
                else:
                    recolors += 1
    counts = (("fill", adds), ("remove", removes), ("recolor", recolors))
    present = [kind for kind, n in counts if n]
    if present == ["fill"]:
        return "fill", "enclosed" if all(fills_enclosed(i, o) for i, o in pairs) else ""
    if len(present) == 1:
        return present[0], ""
    hist_same = all(
        Counter(v for r in i for v in r) == Counter(v for r in o for v in r)
        for i, o in pairs
    )
    return ("move" if hist_same else "same_mixed"), ""


def size_relation(pairs: list[tuple[Grid, Grid]]) -> str:
    rels = set()
    for i, o in pairs:
        (h, w), (oh, ow) = shape(i), shape(o)
        if (h, w) == (oh, ow):
            rels.add("same")
        elif oh % h == 0 and ow % w == 0:
            rels.add("upscale")
        elif h % oh == 0 and w % ow == 0:
            rels.add("downscale")
        elif oh * ow > h * w:
            rels.add("grow_other")
        else:
            rels.add("shrink_other")
    out_shapes = {shape(o) for _, o in pairs}
    in_shapes = {shape(i) for i, _ in pairs}
    if len(out_shapes) == 1 and len(in_shapes) > 1:
        return "fixed_output"
    return rels.pop() if len(rels) == 1 else "mixed"


def count_objects(grid: Grid) -> int:
    """Count 8-connected single-colour components of non-background cells."""
    h, w = shape(grid)
    bg = background(grid)
    seen = [[False] * w for _ in range(h)]
    count = 0
    for r in range(h):
        for c in range(w):
            if seen[r][c] or grid[r][c] == bg:
                continue
            count += 1
            stack = [(r, c)]
            seen[r][c] = True
            while stack:
                y, x = stack.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (
                            0 <= ny < h
                            and 0 <= nx < w
                            and not seen[ny][nx]
                            and grid[ny][nx] == grid[y][x]
                        ):
                            seen[ny][nx] = True
                            stack.append((ny, nx))
    return count


def classify(pairs: list[tuple[Grid, Grid]]) -> tuple[str, str]:
    if detail := is_geometry(pairs):
        return "geometry", detail
    if detail := is_colormap(pairs):
        return "colormap", detail
    if detail := is_scale_tile(pairs):
        return "scale_tile", detail
    if is_crop(pairs):
        return "crop", ""
    if all(shape(i) == shape(o) for i, o in pairs):
        return same_size_kind(pairs)
    if all(split_parts(i, o) for i, o in pairs):
        return "split_overlay", ""
    if all(shape(o)[0] * shape(o)[1] <= 9 for _, o in pairs):
        return "summary", ""
    if all(shape(o)[0] * shape(o)[1] < shape(i)[0] * shape(i)[1] for i, o in pairs):
        return "shrink_other", ""
    if all(contains(o, i) for i, o in pairs):
        return "grow_other", "input inside output"
    return "grow_other", ""


def rearc_lengths(rearc_dir: Path, prefix: str, filename: str) -> dict[str, int]:
    """Count body lines of each generate_/verify_ function in a RE-ARC file."""
    text = (rearc_dir / filename).read_text(encoding="utf-8")
    pattern = re.compile(rf"^def {prefix}_([0-9a-f]{{8}})\(", re.M)
    starts = [(m.group(1), m.start()) for m in pattern.finditer(text)]
    lengths = {}
    for n, (task_id, start) in enumerate(starts):
        end = starts[n + 1][1] if n + 1 < len(starts) else len(text)
        body = text[start:end].splitlines()[1:]
        lengths[task_id] = sum(1 for line in body if line.strip())
    return lengths


def symbolic_level(verifier_lines: int) -> str:
    """Bucket the RE-ARC DSL solution length into an ease estimate."""
    if verifier_lines <= 10:
        return "easy"
    if verifier_lines <= 25:
        return "medium"
    return "hard"


def task_features(task_id: str, task: dict, ver: dict, gen: dict) -> dict:
    pairs = [(p["input"], p["output"]) for p in task["train"]]
    category, detail = classify(pairs)
    ins = [i for i, _ in pairs]
    outs = [o for _, o in pairs]
    in_cols = set().union(*(colors(g) for g in ins))
    out_cols = set().union(*(colors(g) for g in outs))
    same = [(i, o) for i, o in pairs if shape(i) == shape(o)]
    changed = ""
    if len(same) == len(pairs):
        diff = sum(
            a != b
            for i, o in same
            for ri, ro in zip(i, o, strict=True)
            for a, b in zip(ri, ro, strict=True)
        )
        total = sum(shape(i)[0] * shape(i)[1] for i, _ in same)
        changed = f"{diff / total:.3f}"
    vlines = ver.get(task_id, 0)
    return {
        "task_id": task_id,
        "category": category,
        "detail": detail,
        "symbolic": symbolic_level(vlines),
        "n_train": len(pairs),
        "n_test": len(task["test"]),
        "in_h_max": max(shape(g)[0] for g in ins),
        "in_w_max": max(shape(g)[1] for g in ins),
        "out_h_max": max(shape(g)[0] for g in outs),
        "out_w_max": max(shape(g)[1] for g in outs),
        "size_relation": size_relation(pairs),
        "in_colors": len(in_cols),
        "out_colors": len(out_cols),
        "new_out_colors": len(out_cols - in_cols),
        "changed_ratio": changed,
        "objects_mean": f"{sum(count_objects(g) for g in ins) / len(ins):.1f}",
        "rearc_verifier_lines": vlines,
        "rearc_generator_lines": gen.get(task_id, 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--rearc", type=Path, default=DEFAULT_REARC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from inventory_render import render_html

    ver = rearc_lengths(args.rearc, "verify", "verifiers.py")
    gen = rearc_lengths(args.rearc, "generate", "generators.py")
    tasks = {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(args.data.glob("*.json"))
    }
    rows = [task_features(tid, task, ver, gen) for tid, task in tasks.items()]

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "training-features.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    html = render_html(rows, tasks)
    (args.out / "training.html").write_text(html, encoding="utf-8")
    counts = Counter(r["category"] for r in rows)
    print(json.dumps({"tasks": len(rows), "categories": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
