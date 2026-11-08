"""G4 evolution: mutate / cross near-miss programs, fitness = train pixel rate.

Seeds are the enumerator's ``near`` list. Mutations: subtree replacement with a
donor subtree (from the near pool, solved programs, leaves) and same-arity
operator swap; crossover swaps subtrees between two parents. Every evaluated
candidate costs one node; randomness comes only from ``random.Random`` seeded
by (seed, task_id), so a fixed seed gives a fixed run.
"""

import hashlib
import random

from . import prog as pg
from .backend import EvalError, run

POP = 24
LEAVES = [("$in",), 0, 1, 2]


def fitness(program, train, lib) -> float:
    total = 0.0
    for x, y in train:
        try:
            total += pg.pixel_score(run(program, x, lib), y)
        except EvalError:
            return 0.0
        except RecursionError:
            return 0.0
    return total / len(train)


def _positions(p, path=()):
    yield path, p
    for i, c in enumerate(pg.children(p)):
        yield from _positions(c, (*path, i))


def _replace(p, path, new):
    if not path:
        return new
    kids = pg.children(p)
    kids[path[0]] = _replace(kids[path[0]], path[1:], new)
    return pg.rebuild(p, kids)


def _arity_table(pool) -> dict[int, list[str]]:
    table: dict[int, set] = {}
    for p in pool:
        for s in pg.subtrees(p):
            if pg.is_node(s) and not s[0].startswith("$") \
                    and s[0] not in ("lam", "blk"):
                table.setdefault(len(s) - 1, set()).add(s[0])
    return {k: sorted(v) for k, v in sorted(table.items())}


def _mutate(rng, p, donors, arity):
    spots = [(path, s) for path, s in _positions(p)]
    path, node = spots[rng.randrange(len(spots))]
    r = rng.random()
    if r < 0.4 and pg.is_node(node) and node[0] not in ("lam", "blk") \
            and not node[0].startswith("$"):
        same = arity.get(len(node) - 1, [])
        if len(same) > 1:
            return _replace(p, path, (rng.choice(same), *node[1:]))
    if r < 0.6 and pg.is_node(node) and pg.children(node):
        # wrap: replace node by one of its children (shrink) or donor(op(node))
        kids = pg.children(node)
        return _replace(p, path, kids[rng.randrange(len(kids))])
    return _replace(p, path, rng.choice(donors))


def _cross(rng, a, b):
    pa = list(_positions(a))
    pb = list(_positions(b))
    path, _ = pa[rng.randrange(len(pa))]
    _, sub = pb[rng.randrange(len(pb))]
    return _replace(a, path, sub)


def evolve(task_id: str, train, near: list, lib, budget: int, seed: int,
           extra_donors: list | None = None):
    """Return (program or None, nodes used, best fitness)."""
    if budget <= 0 or not near:
        return None, 0, 0.0
    h = int(hashlib.sha1(f"{seed}:{task_id}".encode()).hexdigest()[:8], 16)
    rng = random.Random(h)
    parents = [pg.from_json(p) if isinstance(p, list) else p for p, _ in near]
    donors = []
    for p in parents + list(extra_donors or []):
        donors.extend(s for s in pg.subtrees(p) if not pg.free_vars(s))
    donors.extend(LEAVES)
    arity = _arity_table(parents + list(extra_donors or []))
    pop = [(fitness(p, train, lib), i, p) for i, p in enumerate(parents)]
    nodes = len(pop)
    seen = {pg.key(p) for _, _, p in pop}
    tick = len(pop)
    while nodes < budget:
        pop.sort(key=lambda t: (-t[0], t[1]))
        pop = pop[:POP]
        if pop[0][0] >= 1.0:
            break
        top = [p for _, _, p in pop[: max(2, len(pop) // 2)]]
        if len(top) > 1 and rng.random() < 0.3:
            a, b = rng.sample(top, 2)
            child = _cross(rng, a, b)
        else:
            child = _mutate(rng, rng.choice(top), donors, arity)
        nodes += 1
        if pg.size(child) > 40:
            continue
        k = pg.key(child)
        if k in seen:
            continue
        seen.add(k)
        tick += 1
        pop.append((fitness(child, train, lib), tick, child))
    pop.sort(key=lambda t: (-t[0], t[1]))
    best_fit, _, best = pop[0]
    return (best if best_fit >= 1.0 else None), nodes, best_fit
