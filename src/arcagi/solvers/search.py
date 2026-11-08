"""DSL search solver (``solve``): BFS program enumeration with tracing.

Programs up to ``MAX_DEPTH`` steps, deduplicated by observational equivalence,
terminal learners on every node; the first solved depth wins, cheapest first
(votes break ties). If none fits, ``solvers.rewrite`` edits the near misses.
"""

import heapq
import os
import time
from collections import Counter
from dataclasses import dataclass, field

from arcagi.dsl import background as bgc
from arcagi.dsl import grid as g
from arcagi.dsl.learners import (
    apply_colormap,
    apply_local_rule,
    fit_colormap,
    fit_local_rule,
)
from arcagi.dsl.objects_learner import apply_object_colormap, fit_object_colormap
from arcagi.dsl.program import Program, cost, to_json
from arcagi.dsl.registry import FIRST_STEP_ONLY, PRIMITIVES, REWRITE_ONLY
from arcagi.tasks import Grid, SolverTask

from . import rewrite
from .trace import SolverResult, TraceRecorder
from .vote import choose, fits, predict_hint

MAX_DEPTH = 3
TIME_BUDGET = 20.0
MAX_NODES = 100000
MAX_SOLUTIONS = 200  # whole first solved depth, capped
MAX_RECORDED = 30  # program attempts written to the trace
MAX_NEAR = 20
PENALIZED = frozenset({"local_rule"})
SOLVER_NAME = "dsl-search-r05"
REWRITE = os.environ.get("ARCAGI_REWRITE", "1") != "0"  # True unless env says 0
DEFER_GRACE = 5.0  # extra seconds for deferred learner fits after the deadline


@dataclass
class SearchResult:
    solutions: list[tuple[float, int, Program, list[Grid]]] = field(
        default_factory=list
    )
    near: list[tuple[float, int, Program, list[bool]]] = field(default_factory=list)
    nodes_per_depth: list[int] = field(default_factory=list)
    out_of_budget: bool = False
    block_calls: Counter[str] = field(default_factory=Counter)
    deferred: int = 0  # last-depth learner fits postponed by the shape hint


def _valid_outputs(grids: list[Grid]) -> bool:
    return all(g.is_valid(grid) for grid in grids)


class _Search:
    def __init__(
        self,
        task: SolverTask,
        budget: float,
        max_nodes: int,
        shape_hint: list[tuple[int, int]] | None = None,
    ) -> None:
        self.shape_hint = shape_hint
        self.last_depth = False
        self.deferred: list[tuple[int, Program, list[Grid], list[Grid]]] = []
        self.targets = [example.output for example in task.train]
        self.n = len(self.targets)
        self.deadline = time.perf_counter() + budget
        self.max_nodes = max_nodes
        self.nodes = 0
        self.order = 0
        self.result = SearchResult()

    def over_budget(self) -> bool:
        if self.nodes >= self.max_nodes or time.perf_counter() > self.deadline:
            self.result.out_of_budget = True
            return True
        return False

    def _add_solution(self, program: Program, tests: list[Grid]) -> None:
        if not _valid_outputs(tests) or len(self.result.solutions) >= MAX_SOLUTIONS:
            return
        self.order += 1
        self.result.solutions.append((cost(program), self.order, program, tests))

    def evaluate(self, program: Program, grids: list[Grid]) -> None:
        train, tests = grids[: self.n], grids[self.n :]
        if train == self.targets:
            self._add_solution(program, tests)
            return
        shapes_match = all(
            g.shape(s) == g.shape(t) for s, t in zip(train, self.targets, strict=True)
        )
        if not shapes_match:
            return
        if (
            self.last_depth
            and self.shape_hint is not None
            and not fits(tests, self.shape_hint)
        ):
            # Learners keep shapes: postpone fits that cannot meet the hint.
            self.deferred.append((self.order, program, train, tests))
            self.order += 4
            return
        self._fit_learners(program, train, tests)

    def _fit_learners(
        self, program: Program, train: list[Grid], tests: list[Grid]
    ) -> None:
        self.result.block_calls["colormap"] += 1
        self.result.block_calls["local_rule"] += 1
        table = fit_colormap(train, self.targets, tests)
        if table is not None:
            step = ("colormap", table)
            self._add_solution(
                (*program, step), [apply_colormap(t, table) for t in tests]
            )
        self.result.block_calls["object_colormap"] += 1
        table = fit_object_colormap(train, self.targets, tests)
        if table is not None:
            step = ("object_colormap", table)
            outs = [apply_object_colormap(t, table) for t in tests]
            self._add_solution((*program, step), outs)
        for features in ("n4", "n8"):
            rule = fit_local_rule(train, self.targets, tests, features)
            if rule is not None:
                step = ("local_rule", features, rule)
                outs = [apply_local_rule(t, features, rule) for t in tests]
                self._add_solution((*program, step), outs)
                break
        results = [s == t for s, t in zip(train, self.targets, strict=True)]
        cells = sum(len(t) * len(t[0]) for t in self.targets)
        same = sum(
            a == b
            for s, t in zip(train, self.targets, strict=True)
            for rs, rt in zip(s, t, strict=True)
            for a, b in zip(rs, rt, strict=True)
        )
        self.order += 1
        entry = (same / cells, self.order, program, results)
        if len(self.result.near) < MAX_NEAR:
            heapq.heappush(self.result.near, entry)
        else:
            heapq.heappushpop(self.result.near, entry)

    def expand(self, frontier, seen):
        nxt = []
        for program, grids in frontier:
            train = grids[: self.n]
            for name, primitive in PRIMITIVES.items():
                if name in REWRITE_ONLY or (program and name in FIRST_STEP_ONLY):
                    continue
                for params in primitive.candidates(train, self.targets):
                    if self.over_budget():
                        return nxt
                    self.nodes += 1
                    self.result.block_calls[name] += 1
                    try:
                        new = [primitive.apply(grid, *params) for grid in grids]
                    except (ValueError, IndexError, KeyError):
                        continue
                    if any(not (0 < len(x) <= 30 and 0 < len(x[0]) <= 30) for x in new):
                        continue
                    signature = tuple(new[: self.n])
                    if signature in seen:
                        continue
                    seen.add(signature)
                    step = (name, *params)
                    child = (*program, step)
                    self.evaluate(child, new)
                    nxt.append((child, new))
        return nxt

    def run(self, task: SolverTask, max_depth: int) -> SearchResult:
        grids = [example.input for example in task.train] + list(task.test)
        self.evaluate((), grids)
        frontier = [((), grids)]
        seen = {tuple(grids[: self.n])}
        for depth in range(max_depth):
            if self.result.solutions or not frontier:
                break
            self.last_depth = depth == max_depth - 1
            frontier = self.expand(frontier, seen)
            self.result.nodes_per_depth.append(len(frontier))
            if self.result.out_of_budget:
                break
        self._run_deferred()
        return self.result

    def _run_deferred(self) -> None:
        """Fit postponed learners (original orders) unless a solution fits the hint.

        The vote prefers hint-fitting solutions, so top-1 is unchanged either way.
        """
        self.result.deferred = len(self.deferred)
        hint = self.shape_hint
        if hint is None or any(fits(s[3], hint) for s in self.result.solutions):
            return
        limit = self.deadline + DEFER_GRACE
        resume = self.order
        for order, program, train, tests in self.deferred:
            if time.perf_counter() > limit:
                self.result.out_of_budget = True
                break
            self.order = order
            self._fit_learners(program, train, tests)
        self.order = resume


def search(
    task: SolverTask,
    *,
    max_depth: int = MAX_DEPTH,
    budget: float = TIME_BUDGET,
    max_nodes: int = MAX_NODES,
    shape_hint: list[tuple[int, int]] | None = None,
) -> SearchResult:
    """Enumerate programs; solutions are (cost, order, program, test outputs).

    Object primitives see the task background (all train inputs and outputs)
    for the duration of the search; the previous context is restored after.
    ``shape_hint`` lets the last depth postpone learner fits whose test shapes
    miss it (see ``_Search._run_deferred``).
    """
    grids = [e.input for e in task.train] + [e.output for e in task.train]
    with bgc.task_context(bgc.task_background(grids)):
        return _Search(task, budget, max_nodes, shape_hint).run(task, max_depth)


def _features(task: SolverTask) -> dict[str, object]:
    pairs = [(e.input, e.output) for e in task.train]
    shapes = {(g.shape(i) == g.shape(o)) for i, o in pairs}
    new_colors = max(
        len(set(g.color_counts(o)) - set(g.color_counts(i))) for i, o in pairs
    )
    return {
        "same_shape": shapes == {True},
        "n_train": len(pairs),
        "max_new_colors": new_colors,
    }


def solve(
    task: SolverTask, shape_hint: list[tuple[int, int]] | None = None
) -> SolverResult:
    """Return the voted top-1 program's outputs plus a trace (top-2 in metadata).

    ``shape_hint`` (one ``(h, w)`` per test input) demotes a top-1 whose test
    outputs have other shapes when some solution fits the hint.
    """
    recorder = TraceRecorder(solver=SOLVER_NAME)
    if shape_hint is None:
        shape_hint = predict_hint(task)
    result = search(task, shape_hint=shape_hint)
    ledger = rewrite.rescue(task, result) if REWRITE and not result.solutions else None
    vote = choose(result.solutions, penalized=PENALIZED, shape_hint=shape_hint)
    solutions = vote.ranked
    ids = []
    for solution in solutions[:MAX_RECORDED]:
        cost_value, order, program, _tests = solution
        ids.append(
            recorder.attempt(
                f"{'rewrite ' if order < 0 else ''}program of cost {cost_value:.1f}",
                kind="program",
                program=to_json(program),
                train_results=[True] * len(task.train),
                data={"cost": cost_value, "votes": vote.votes_of(solution)},
            )
        )
    for acc, _order, program, results in sorted(result.near, reverse=True):
        recorder.attempt(
            f"near miss, pixel accuracy {acc:.3f}",
            kind="near_miss",
            program=to_json(program),
            train_results=results,
            data={"pixel_acc": round(acc, 4)},
        )
    recorder.metadata = {
        "features": _features(task),
        "nodes_per_depth": result.nodes_per_depth,
        "out_of_budget": result.out_of_budget,
        "solutions": len(solutions),
        "outputs": len(vote.votes),
        "shape_hint_applied": vote.hint_applied,
        "block_calls": dict(result.block_calls),
        "deferred_fits": result.deferred,
        "second": vote.second,
        "rewrite": ledger.to_json() if ledger else None,
    }
    if not solutions:
        recorder.reasoning = "No program reproduces every train pair; echo inputs."
        recorder.select(None)
        return recorder.result(list(task.test))
    recorder.reasoning = "Cheapest train-consistent program, votes break ties."
    recorder.select(ids[0])
    return recorder.result(solutions[0][3])
