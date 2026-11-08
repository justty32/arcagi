"""Integer formulas over grid features (JSON S-expressions) and their fitting.

Block ``_rule.json``: ``{"kind": "formula", "in": "features", "out": "int",
"body": BODY[, "extracts": {name: extract body}]}``; ``x``/``y`` are feature
names (``arcagi.dsl.features``, extract features need their source in
``extracts``). One layer: ``["lin", x, a, b]`` a*x+b (a 1..4, b -3..3), ``["mul",
x, y]``, ``["sq", x]``, ``["max"|"min", x, y]``, ``["div", x, k]`` exact x//k (k
2..5), ``["const", k]`` (never a fitted *formula*). Two layers (generator only,
after every one-layer body failed): ``["lin2", x, a, y, b]`` a*x+b*y (a in
{1,2,3,-1}, b in -2..2 not 0), ``["mulc", x, c, y]`` (x+c)*y (c in -2..2 not 0).

``fit`` tries one-layer library bodies, a small direct search over the base
features, then two-layer library bodies; a body must hold on every pair and the
targets take two values or more. CLI (block ``_entry``): ``python -m
arcagi.dsl.formula RULE.json`` reads a grid / feature dict on stdin, prints it.
"""

import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from arcagi.tasks import Grid

from . import grid as g
from .features import EXTRA, NAMES, compute, known

type Body = list[object]
type Feats = Mapping[str, int]
type Lib = Mapping[str, Body] | Iterable[Body]

A_RANGE = range(1, 5)
B_RANGE = range(-3, 4)
K_RANGE = range(2, 6)
A2_RANGE = (1, 2, 3, -1)
C2_RANGE = (-2, -1, 1, 2)
TWO_CAP = 3000  # two-layer candidates per generator run
OPS = ("lin", "mul", "sq", "max", "min", "div", "const", "lin2", "mulc")
MAX_SIDE = 30
MIN_DIRECT_PAIRS = 3  # fewer pairs: library formulas only
LIVE: dict[str, Body] = {}  # name -> body of live formula blocks (install)
_LIVE_KEY: list[tuple[str, ...]] = [()]  # LIVE bodies as JSON, in LIVE order


def evaluate(body: Sequence[object], feats: Feats) -> int:
    """Value of ``body`` on a feature dict; ValueError when undefined."""
    op = body[0]
    if op == "const":
        return int(body[1])  # type: ignore[call-overload]
    x = feats[body[1]]  # type: ignore[index]
    if op == "lin2":
        return int(body[2]) * x + int(body[4]) * feats[body[3]]  # type: ignore[call-overload,index]
    if op == "mulc":
        return (x + int(body[2])) * feats[body[3]]  # type: ignore[call-overload,index]
    if op == "lin":
        return int(body[2]) * x + int(body[3])  # type: ignore[call-overload]
    if op == "sq":
        return x * x
    if op == "div":
        k = int(body[2])  # type: ignore[call-overload]
        if x % k:
            raise ValueError("inexact division")
        return x // k
    y = feats[body[2]]  # type: ignore[index]
    if op not in ("mul", "max", "min"):
        raise ValueError(f"unknown formula op {op!r}")
    return x * y if op == "mul" else max(x, y) if op == "max" else min(x, y)


def validate(body: object) -> bool:
    if not isinstance(body, list) or not body or body[0] not in OPS:
        return False
    op, args = body[0], body[1:]
    if op == "const":
        return len(args) == 1 and isinstance(args[0], int)
    if not args or not known(args[0]):
        return False
    if op == "lin2":
        ok = len(args) == 4 and args[1] in A2_RANGE and args[3] in C2_RANGE
        return ok and known(args[2])
    if op == "mulc":
        return len(args) == 3 and args[1] in C2_RANGE and known(args[2])
    if op == "lin":
        return len(args) == 3 and args[1] in A_RANGE and args[2] in B_RANGE
    if op == "sq":
        return len(args) == 1
    if op == "div":
        return len(args) == 2 and args[1] in K_RANGE
    return len(args) == 2 and known(args[1])


def length(body: Sequence[object]) -> int:
    """Description length: features read plus non-trivial constants."""
    op = body[0]
    if op == "const":
        return 1
    if op == "lin":
        return 1 + int(body[2] != 1) + int(body[3] != 0)
    if op == "lin2":
        return 4 + int(body[2] != 1) + int(body[4] != 1)
    if op == "mulc":
        return 5 + int(abs(body[2]) != 1)  # type: ignore[arg-type]
    return 2 if op in ("sq", "div") else 3


def enumerate_bodies(names: Sequence[str] = NAMES) -> list[Body]:
    """Every formula in simplicity order (ties keep enumeration order)."""
    out: list[Body] = [
        ["lin", x, a, b] for x in names for a in A_RANGE for b in B_RANGE
    ]
    out += [["sq", x] for x in names] + [["div", x, k] for x in names for k in K_RANGE]
    for op in ("mul", "max", "min"):
        out += [[op, x, y] for x, y in combinations(names, 2)]
    return sorted(out, key=length)


def enumerate_two(names: Sequence[str] = NAMES, cap: int = TWO_CAP) -> list[Body]:
    """The ``cap`` simplest two-layer bodies over ``names``."""
    pairs = list(combinations(names, 2))
    out: list[Body] = [
        ["lin2", x, a, y, b] for x, y in pairs for a in A2_RANGE for b in C2_RANGE
    ]
    out += [["mulc", x, c, y] for x in names for y in names for c in C2_RANGE]
    return sorted(out, key=length)[: max(cap, 0)]


ALL_BODIES: tuple[Body, ...] = tuple(enumerate_bodies())


def holds(body: Sequence[object], xs: Sequence[Feats], ys: Sequence[int]) -> bool:
    try:
        return all(evaluate(body, x) == y for x, y in zip(xs, ys, strict=True))
    except (ValueError, KeyError, TypeError):
        return False


def _direct(cols: dict[str, tuple[int, ...]], ys: tuple[int, ...]) -> Body | None:
    """Smallest direct formula (analytic linear fit, then the other forms)."""
    best: Body | None = None
    for name, col in cols.items():
        if len(set(col)) < 2:
            continue
        pts = list(zip(col, ys))
        (x1, y1), (x2, y2) = next((p, q) for p in pts for q in pts if p[0] != q[0])
        a, rem = divmod(y2 - y1, x2 - x1)
        b = y1 - a * x1
        if rem or a not in A_RANGE or b not in B_RANGE:
            continue
        if all(a * x + b == y for x, y in zip(col, ys)):
            body: Body = ["lin", name, a, b]
            if best is None or length(body) < length(best):
                best = body
    if best is not None and length(best) == 1:
        return best
    for body in ALL_BODIES:
        if body[0] == "lin" or (best is not None and length(body) >= length(best)):
            continue
        if _holds_cols(body, cols, ys):
            return body
    return best


def _holds_cols(body: Body, cols: dict[str, tuple], ys: tuple[int, ...]) -> bool:
    op, xc = body[0], cols[body[1]]  # type: ignore[index]
    for i, y in enumerate(ys):
        x = xc[i]
        if op == "sq":
            v = x * x
        elif op == "div":
            k = body[2]
            if x % k:  # type: ignore[operator]
                return False
            v = x // k  # type: ignore[operator]
        else:
            z = cols[body[2]][i]  # type: ignore[index]
            v = x * z if op == "mul" else max(x, z) if op == "max" else min(x, z)
        if v != y:
            return False
    return True


@lru_cache(maxsize=65536)
def _fit_cached(rows: tuple[tuple, ...], ys: tuple[int, ...], lib: tuple[str, ...]):
    xs = [dict(r) for r in rows]
    cols = {n: tuple(x[n] for x in xs) for n in NAMES}  # direct search: base only
    two = [t for t in lib if t.startswith(('["lin2"', '["mulc"'))]  # last
    for text in [t for t in lib if t not in two]:
        if holds(json.loads(text), xs, ys):
            return text
    body = _direct(cols, ys) if len(ys) >= MIN_DIRECT_PAIRS else None
    if body is not None:
        return json.dumps(body)
    return next((t for t in two if holds(json.loads(t), xs, ys)), None)


def fit(xs: Sequence[Feats], ys: Sequence[int], library: Lib = ()) -> Body | None:
    """Simplest body on every pair: one-layer library, direct search (needs
    ``MIN_DIRECT_PAIRS``), then two-layer library."""
    if len(xs) != len(ys) or len(xs) < 2 or len(set(ys)) < 2:
        return None
    if library is LIVE:
        lib = _LIVE_KEY[0]
    else:
        bodies = library.values() if isinstance(library, Mapping) else library
        lib = tuple(json.dumps(b) for b in bodies)
    rows = tuple(tuple(sorted(x.items())) for x in xs)
    text = _fit_cached(rows, tuple(ys), lib)
    return None if text is None else json.loads(text)


def fit_dim(xs: Sequence[Feats], ys: Sequence[int], library=()) -> Body | None:
    """``fit``, or ``["const", k]`` when every target is ``k``."""
    return ["const", ys[0]] if ys and len(set(ys)) == 1 else fit(xs, ys, library)


def predict_shapes(
    train_pairs: Sequence[tuple[Grid, Grid]], test_inputs: Sequence[Grid]
) -> list[tuple[int, int]] | None:
    """Output (h, w) for each test input from formulas fitted on train, or None."""
    if not train_pairs:
        return None
    xs = [compute(i) for i, _ in train_pairs]
    dims = [fit_dim(xs, [g.shape(o)[d] for _, o in train_pairs], LIVE) for d in (0, 1)]
    if None in dims:
        return None
    out = []
    for grid in test_inputs:
        try:
            h, w = (evaluate(b, compute(grid)) for b in dims)  # type: ignore[arg-type]
        except (ValueError, KeyError):
            return None
        if not (0 < h <= MAX_SIDE and 0 < w <= MAX_SIDE):
            return None
        out.append((h, w))
    return out


def adopt(rule: object) -> None:
    """Make a rule's ``extracts`` (feature source bodies) known to features."""
    found = rule.get("extracts") if isinstance(rule, dict) else None
    for name, body in (found if isinstance(found, dict) else {}).items():
        EXTRA.setdefault(name, body)


def read_rule(folder: Path) -> Body | None:
    try:
        rule = json.loads((folder / "_rule.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    adopt(rule)
    body = rule.get("body") if isinstance(rule, dict) else None
    return body if validate(body) else None


def install(bodies: Mapping[str, Body], scores: Mapping[str, float] | None = None):
    """Set the live library: simplest first, then best-scored on training."""
    LIVE.clear()
    sc = scores or {}
    good = [(k, v) for k, v in bodies.items() if validate(v)]
    LIVE.update(sorted(good, key=lambda kv: (length(kv[1]), -sc.get(kv[0], 0), kv[0])))
    _LIVE_KEY[0] = tuple(json.dumps(v) for v in LIVE.values())


def resolve(ref: object) -> Body:
    """A body from a param: inline body, live block name, else its folder."""
    if isinstance(ref, list) and validate(ref):
        return ref
    if isinstance(ref, str) and ref in LIVE:
        return LIVE[ref]
    if isinstance(ref, str):
        from arcagi.blocks import default_blocks_root

        if (body := read_rule(default_blocks_root() / ref)) is not None:
            return body
    raise ValueError(f"unknown formula {ref!r}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m arcagi.dsl.formula RULE.json < grid", file=sys.stderr)
        return 2
    try:
        if (body := read_rule(Path(argv[0]).parent)) is None:
            raise ValueError(f"bad rule file {argv[0]}")
        data = json.loads(sys.stdin.read())
        data = data["grid"] if isinstance(data, dict) and "grid" in data else data
        if isinstance(data, list):
            data = compute(tuple(tuple(row) for row in data))
        print(evaluate(body, data))
    except (ValueError, TypeError, KeyError) as exc:
        print(f"arcagi.dsl.formula: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
