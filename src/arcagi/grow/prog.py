"""Program-tuple helpers shared by compression, evolution and the curve loop.

Program = ("op", *args) | ("$in",) | ("$0",) | ("$1",) | ("lam", n, body)
        | ("blk", name, *args) | int   (r07 03-設計 §2)
"""

import hashlib
import json

HOLE_PREFIX = "$h"


def is_node(p) -> bool:
    return isinstance(p, tuple) and len(p) > 0 and isinstance(p[0], str)


def children(p) -> list:
    """Sub-program positions (lam arity and blk name are not children)."""
    if not is_node(p):
        return []
    if p[0] == "lam":
        return [p[2]]
    if p[0] == "blk":
        return list(p[2:])
    return list(p[1:])


def rebuild(p, kids: list):
    if p[0] == "lam":
        return ("lam", p[1], kids[0])
    if p[0] == "blk":
        return ("blk", p[1], *kids)
    return (p[0], *kids)


def size(p) -> int:
    """Node count; holes count 0, everything else 1 per node."""
    if is_hole(p):
        return 0
    return 1 + sum(size(c) for c in children(p))


def is_hole(p) -> bool:
    return is_node(p) and p[0].startswith(HOLE_PREFIX)


def free_vars(p, depth: int = 0) -> bool:
    """True when a de Bruijn variable escapes its lambda."""
    if is_node(p):
        if p[0] in ("$0", "$1"):
            return depth == 0
        if p[0] == "lam":
            return free_vars(p[2], depth + 1)
        return any(free_vars(c, depth) for c in children(p))
    return False


def subtrees(p):
    yield p
    for c in children(p):
        yield from subtrees(c)


def ops(p):
    """Operator / block names used in a program (multiset as list)."""
    out = []
    for s in subtrees(p):
        if is_node(s) and not s[0].startswith("$") and s[0] != "lam":
            out.append(s[1] if s[0] == "blk" else s[0])
    return out


def to_json(p):
    if isinstance(p, tuple):
        return [to_json(e) for e in p]
    return p


def from_json(p):
    if isinstance(p, list):
        return tuple(from_json(e) for e in p)
    return p


def key(p) -> str:
    return hashlib.sha1(json.dumps(to_json(p)).encode()).hexdigest()[:10]


def norm(v):
    if isinstance(v, (list, tuple)):
        return tuple(norm(e) for e in v)
    return v


def _shape(v):
    if isinstance(v, tuple) and all(isinstance(r, tuple) for r in v):
        return tuple(len(r) for r in v)
    return None


def change_score(out, target, inp) -> float:
    """Shape match x accuracy on cells where ``target`` differs from ``inp``.

    Falls back to all cells when the input has another shape or nothing
    changes; 0 when the output shape differs from the target's.
    """
    out, target, inp = norm(out), norm(target), norm(inp)
    if out == target:
        return 1.0
    shape = _shape(target)
    if shape is None or _shape(out) != shape:
        return 0.0
    cells = [(i, j) for i, n in enumerate(shape) for j in range(n)]
    if _shape(inp) == shape:
        changed = [(i, j) for i, j in cells if target[i][j] != inp[i][j]]
        cells = changed or cells
    if not cells:
        return 0.0
    return sum(out[i][j] == target[i][j] for i, j in cells) / len(cells)


def pixel_score(out, target) -> float:
    """Fraction of equal cells for same-shape 2-level lists; exact match else."""
    out, target = norm(out), norm(target)
    if out == target:
        return 1.0
    if not (isinstance(out, tuple) and isinstance(target, tuple)):
        return 0.0
    if len(out) != len(target) or not all(
        isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b)
        for a, b in zip(out, target, strict=True)
    ):
        return 0.0
    cells = sum(len(r) for r in target)
    same = sum(
        x == y
        for ra, rb in zip(out, target, strict=True)
        for x, y in zip(ra, rb, strict=True)
    )
    return same / cells if cells else 0.0
