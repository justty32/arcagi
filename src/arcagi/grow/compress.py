"""G1 compression: subtree + anti-unification blocks scored by MDL saving.

After each pass the solved learn-set programs are mined: every closed subtree
of size >= 2 is a candidate, and every pair of such subtrees with the same root
operator is anti-unified into a template with at most ``max_holes`` holes.
saving = occurrences * size - size - k * holes; the top ``m`` positive ones
join the library. Use counts drive the enumeration order (log prior); blocks
unused for ``retire_after`` consecutive passes retire; the library caps at 40.
"""

import math
from dataclasses import dataclass

from . import prog as pg

LIB_CAP = 40
RETIRE_AFTER = 3


@dataclass(frozen=True)
class Params:
    m: int = 3
    k: float = 2.0
    max_holes: int = 2


def anti_unify(a, b, max_holes: int):
    """Least general generalisation of two programs, or None if > max_holes."""
    table: dict = {}

    def rec(x, y):
        if x == y:
            return x
        if (
            pg.is_node(x)
            and pg.is_node(y)
            and x[0] == y[0]
            and not x[0].startswith("$")
            and len(x) == len(y)
            and (x[0] not in ("lam", "blk") or x[1] == y[1])
        ):
            return pg.rebuild(x, [rec(c, d) for c, d in
                                 zip(pg.children(x), pg.children(y), strict=True)])
        if (x, y) not in table:
            if len(table) >= max_holes:
                raise _TooManyError
            table[(x, y)] = (f"{pg.HOLE_PREFIX}{len(table)}",)
        return table[(x, y)]

    try:
        out = rec(a, b)
    except _TooManyError:
        return None
    return out


class _TooManyError(Exception):
    pass


def matches(template, p, binding: dict | None = None) -> bool:
    binding = {} if binding is None else binding
    if pg.is_hole(template):
        if template in binding:
            return binding[template] == p
        if pg.free_vars(p):
            return False
        binding[template] = p
        return True
    if pg.is_node(template):
        if not pg.is_node(p) or template[0] != p[0] or len(template) != len(p):
            return False
        if template[0] in ("lam", "blk") and template[1] != p[1]:
            return False
        return all(
            matches(t, q, binding)
            for t, q in zip(pg.children(template), pg.children(p), strict=True)
        )
    return template == p


def n_holes(t) -> int:
    return len({s for s in pg.subtrees(t) if pg.is_hole(s)})


def _canonical(t):
    """Renumber holes in first-occurrence order."""
    names: dict = {}

    def rec(x):
        if pg.is_hole(x):
            names.setdefault(x, (f"{pg.HOLE_PREFIX}{len(names)}",))
            return names[x]
        if pg.is_node(x):
            return pg.rebuild(x, [rec(c) for c in pg.children(x)])
        return x

    return rec(t)


def candidates(programs: dict[str, object], params: Params) -> list[dict]:
    """Scored templates (saving > 0), best first, deterministic order."""
    occs: list[tuple[str, object]] = []
    for tid in sorted(programs):
        for s in pg.subtrees(programs[tid]):
            if pg.is_node(s) and pg.size(s) >= 2 and not pg.free_vars(s):
                occs.append((tid, s))
    pool: dict[str, object] = {}
    for _, s in occs:
        pool.setdefault(pg.key(s), s)
    distinct = [pool[k] for k in sorted(pool)]
    templates = dict(pool)
    for i, a in enumerate(distinct):
        for b in distinct[i + 1:]:
            if a[0] != b[0]:
                continue
            t = anti_unify(a, b, params.max_holes)
            if t is not None and not pg.is_hole(t):
                t = _canonical(t)
                templates.setdefault(pg.key(t), t)
    scored = []
    for k in sorted(templates):
        t = templates[k]
        sz, h = pg.size(t), n_holes(t)
        if sz < 2 or (t[0] == "blk" and sz == 1):
            continue
        srcs = [tid for tid, s in occs if matches(t, s)]
        saving = len(srcs) * sz - sz - params.k * h
        if saving > 0:
            scored.append({"body": t, "holes": h, "size": sz, "saving": saving,
                           "occurrences": len(srcs), "src_tasks": sorted(set(srcs))})
    scored.sort(key=lambda c: (-c["saving"], -c["size"], pg.key(c["body"])))
    return scored


def block_name(body) -> str:
    return f"g1_{pg.key(body)}"


def update(lib_blocks: list[dict], programs: dict[str, object], params: Params,
           pass_no: int, extra: dict[str, object] | None = None,
           ) -> tuple[list[dict], list[dict]]:
    """Return (new library blocks, added blocks) after one pass.

    ``programs`` are the solved learn-set programs of this pass (they count
    uses); ``extra`` (cold-start near misses) only feeds template mining.
    """
    used: dict[str, int] = {}
    for p in programs.values():
        for name in pg.ops(p):
            used[name] = used.get(name, 0) + 1
    kept = []
    for b in lib_blocks:
        b = dict(b)
        n = used.get(b["name"], 0)
        b["uses"] = int(b.get("uses", 0)) + n
        b["idle"] = 0 if n else int(b.get("idle", 0)) + 1
        if b["idle"] < RETIRE_AFTER:
            kept.append(b)
    from .sig import infer_sig

    bodies = {pg.key(b["body"]) for b in kept}
    while True:  # drop blocks whose body calls a retired block
        names = {b["name"] for b in kept}
        ok = [b for b in kept if all(not n.startswith("g1_") or n in names
                                     for n in pg.ops(b["body"]))]
        if len(ok) == len(kept):
            break
        kept = ok
    known = {b["name"]: b for b in kept}
    added = []
    for c in candidates({**programs, **(extra or {})}, params):
        if len(added) >= params.m or len(kept) + len(added) >= LIB_CAP:
            break
        if pg.key(c["body"]) in bodies:
            continue
        if any(name not in known and name.startswith("g1_")
               for name in pg.ops(c["body"])):
            continue  # refers to a retired block
        sig = infer_sig(c["body"], known)
        if sig is None:
            continue
        bodies.add(pg.key(c["body"]))
        added.append({
            "name": block_name(c["body"]), "body": c["body"], "holes": c["holes"],
            "sig": sig, "src_tasks": c["src_tasks"], "saving": c["saving"],
            "uses": 0, "idle": 0, "born": pass_no,
        })
    return kept + added, added


def order_from_uses(uses: dict[str, int]) -> dict[str, float]:
    """Enumeration prior: log(1 + uses) per operator / block name."""
    return {k: math.log1p(v) for k, v in sorted(uses.items()) if v > 0}


def lib_bits(blocks: list[dict], n_prims: int) -> float:
    """Description length of the library: sum of block sizes * log2(vocab)."""
    vocab = max(2, n_prims + len(blocks) + 3)
    return round(sum(pg.size(b["body"]) for b in blocks) * math.log2(vocab), 2)
