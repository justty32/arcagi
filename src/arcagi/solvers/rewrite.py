"""Source-space rewrite search: edit seed programs, keep train-consistent ones.

Run after the BFS fails (``arcagi.solvers.search.solve``): seeds are its best
near misses plus the empty program. Every rule in
``arcagi.solvers.rewrite_rules.RULES`` yields programs one edit away; level 1
edits the seeds, level 2 edits the best level-1 programs. Seeds and the level-2
beam rank by a foreground score (cells where input, target or prediction
differ). Only train pairs are checked (all of them must match). The first
level with a solution wins, so fewer edits beat shorter programs;
``vote.choose`` then ranks by cost. Guards against memorising: no >=3x3
literal grid parameters; at most one per-object rule step, and only last.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass

from arcagi.dsl import background as bgc
from arcagi.dsl import grid as g
from arcagi.dsl.learners import apply_colormap, fit_colormap
from arcagi.dsl.program import Program, cost, run_step
from arcagi.tasks import Grid, SolverTask

from .rewrite_ledger import RewriteLedger
from .rewrite_rules import RULES, has_literal_grid, objrule_misplaced

MAX_LEN = 5
MAX_SOLUTIONS = 50
CACHE_LIMIT = 50000

type Found = tuple[float, Program, list[Grid]]


@dataclass(frozen=True)
class Budget:
    candidates: int = 3000
    seconds: float = 8.0
    max_edits: int = 2
    seeds: int = 5
    beam: int = 20  # level-1 programs that level 2 edits
    first_share: float = 0.6  # share of candidates level 1 may spend


def _ok(grid: Grid) -> bool:
    return 0 < len(grid) <= 30 and 0 < len(grid[0]) <= 30


def _run_all(program: Program, grids: Sequence[Grid]) -> list[Grid] | None:
    out = list(grids)
    for step in program:
        out = _step_all(step, out)  # type: ignore[assignment]
        if out is None:
            return None
    return out


def _step_all(step, grids: Sequence[Grid]) -> list[Grid] | None:
    try:
        out = [run_step(step, grid) for grid in grids]
    except Exception:  # noqa: BLE001 - rewritten params may break any primitive
        return None
    return out if all(_ok(x) for x in out) else None


def _key(program: Program) -> str:
    """Hashable identity of a program (parameters may hold lists)."""
    return repr(program)


class _Context:
    """Train inputs / targets plus a prefix cache of intermediate train grids."""

    def __init__(self, task: SolverTask) -> None:
        self.inputs = [e.input for e in task.train]
        self.targets = [e.output for e in task.train]
        self.tests = list(task.test)
        grids = [*self.inputs, *self.targets]
        self.palette = sorted({c for grid in grids for row in grid for c in row})
        self.cache: dict[str, list[Grid] | None] = {_key(()): self.inputs}

    def states(self, prefix: Program) -> list[Grid] | None:
        k = len(prefix)
        while k and _key(prefix[:k]) not in self.cache:
            k -= 1
        grids = self.cache[_key(prefix[:k])]
        if len(self.cache) > CACHE_LIMIT:
            self.cache = {_key(()): self.inputs}
        for i in range(k, len(prefix)):
            if grids is None:
                break
            grids = _step_all(prefix[i], grids)
            self.cache[_key(prefix[: i + 1])] = grids
        return grids


class _Rewriter:
    def __init__(self, task: SolverTask, budget: Budget, ledger: RewriteLedger):
        self.ctx = _Context(task)
        self.budget = budget
        self.ledger = ledger
        self.deadline = time.perf_counter() + budget.seconds
        self.cells = sum(len(t) * len(t[0]) for t in self.ctx.targets)
        self.seen: set[str] = set()
        self.sigs: set[tuple[Grid, ...]] = set()
        self.found: list[Found] = []

    def over(self, limit: int) -> bool:
        timeout = time.perf_counter() > self.deadline
        if timeout or self.ledger.candidates >= self.budget.candidates:
            self.ledger.out_of_budget = True
        return timeout or self.ledger.candidates >= limit

    def _accuracy(self, train: list[Grid]) -> float | None:
        """Foreground score: share of right cells where in != out or pred != in.

        Pairs whose input and target shapes differ score on all cells; None
        when some prediction has the wrong shape.
        """
        right = total = 0
        for x, s, t in zip(self.ctx.inputs, train, self.ctx.targets, strict=True):
            if g.shape(s) != g.shape(t):
                return None
            keep = g.shape(x) == g.shape(t)
            for i, (rs, rt) in enumerate(zip(s, t, strict=True)):
                for j, (a, b) in enumerate(zip(rs, rt, strict=True)):
                    if not keep or a != x[i][j] or b != x[i][j]:
                        total += 1
                        right += a == b
        return right / total if total else 1.0

    def _accept(self, program: Program, tests: list[Grid] | None, rules) -> None:
        if tests is None or not all(g.is_valid(t) for t in tests):
            return
        if len(self.found) < MAX_SOLUTIONS:
            self.found.append((cost(program), program, tests))
            self.ledger.hit(rules, program)

    def evaluate(self, program: Program, rules: tuple[str, ...]) -> float | None:
        """Foreground score of a non-solution (None: drop it); records solutions."""
        train = self.ctx.states(program)
        if train is None:
            return None
        sig = tuple(train)
        if sig in self.sigs:
            return None
        self.sigs.add(sig)
        if train == self.ctx.targets:
            self._accept(program, _run_all(program, self.ctx.tests), rules)
            return None
        acc = self._accuracy(train)
        if acc is None:
            return 0.0
        tests = _run_all(program, self.ctx.tests)
        if tests is not None:
            table = fit_colormap(train, self.ctx.targets, tests)
            if table is not None:
                outs = [apply_colormap(t, table) for t in tests]
                self._accept((*program, ("colormap", table)), outs, rules)
        return acc

    def level(self, frontier, limit: int):
        children = []
        for name, rule in RULES.items():
            for _acc, parent, rules in frontier:
                for child in rule(parent, self.ctx):
                    if self.over(limit):
                        return children
                    key = _key(child)
                    if key in self.seen or len(child) > MAX_LEN:
                        continue
                    self.seen.add(key)
                    if has_literal_grid(child) or objrule_misplaced(child):
                        continue
                    trail = (*rules, name)
                    self.ledger.try_(trail)
                    acc = self.evaluate(child, trail)
                    if acc is not None:
                        children.append((acc, child, trail))
        return children

    def run(self, seeds: Sequence[Program]) -> list[Found]:
        frontier = []
        unique = {_key(tuple(map(tuple, s))): tuple(map(tuple, s)) for s in seeds}
        for key, seed in unique.items():
            self.seen.add(key)
            train = self.ctx.states(seed)
            if train is not None and tuple(train) not in self.sigs:
                self.sigs.add(tuple(train))
                frontier.append((self._accuracy(train) or 0.0, seed, ()))
        # Best foreground score first; [] is one seed but never crowds others out.
        frontier.sort(key=lambda f: (-f[0], len(f[1]) == 0))
        empty = [f for f in frontier if not f[1]]
        frontier = [f for f in frontier if f[1]][: self.budget.seeds - len(empty)]
        frontier += empty
        total = self.budget.candidates
        for edits in range(1, self.budget.max_edits + 1):
            last = edits == self.budget.max_edits
            limit = total if last else int(total * self.budget.first_share)
            children = self.level(frontier, limit)
            if self.found or not children or self.over(total):
                break
            children.sort(key=lambda c: -c[0])
            frontier = children[: self.budget.beam]
        return sorted(self.found, key=lambda f: f[0])


def search(
    task: SolverTask,
    seeds: Sequence[Program],
    budget: Budget | None = None,
    ledger: RewriteLedger | None = None,
) -> list[Found]:
    """Train-consistent rewrites of ``seeds``: (cost, program, test outputs).

    Only the fewest-edit level that has any solution is returned, cheapest first.
    """
    ledger = ledger if ledger is not None else RewriteLedger()
    start = time.perf_counter()
    grids = [e.input for e in task.train] + [e.output for e in task.train]
    with bgc.task_context(bgc.task_background(grids)):
        found = _Rewriter(task, budget or Budget(), ledger).run(seeds)
    ledger.seconds = time.perf_counter() - start
    ledger.solved = bool(found)
    return found


def rescue(task: SolverTask, result) -> RewriteLedger:
    """Seed with ``[]`` plus the best near misses of a BFS ``SearchResult``;
    append rewritten solutions to ``result.solutions`` with negative orders.
    """
    ranked = [entry[2] for entry in result.near]
    seeds = [(), *ranked]  # ranked, deduplicated and capped by ``search``
    ledger = RewriteLedger()
    found = search(task, seeds, ledger=ledger)
    for i, (cost_value, program, tests) in enumerate(found):
        result.solutions.append((cost_value, i - len(found), program, tests))
    return ledger


__all__ = ["Budget", "rescue", "search"]
