"""Round-1 DSL search solver: breadth-first program enumeration with tracing.

Run: nice -n 19 uv run arcagi eval --split evaluation \\
         --solver arcagi.solvers.search:solve --name dsl-search-r01 --timeout 10 \\
         --output artifacts/dsl-eval.json --traces artifacts/dsl-eval.jsonl

Enumerates programs from ``arcagi.dsl.primitives`` up to ``MAX_DEPTH`` steps,
deduplicates by observational equivalence (identical intermediate train grids),
tries terminal learners (color table, neighborhood rule) on every node, and
submits the cheapest program that reproduces every train pair.
"""

import heapq
import time
from dataclasses import dataclass, field

from arcagi.dsl import grid as g
from arcagi.dsl.learners import (
    apply_colormap,
    apply_local_rule,
    fit_colormap,
    fit_local_rule,
)
from arcagi.dsl.program import Program, cost, to_json
from arcagi.dsl.registry import PRIMITIVES
from arcagi.tasks import Grid, SolverTask

from .trace import SolverResult, TraceRecorder

MAX_DEPTH = 3
TIME_BUDGET = 2.5
MAX_NODES = 20000
MAX_SOLUTIONS = 30
MAX_NEAR = 20


@dataclass
class SearchResult:
    solutions: list[tuple[float, int, Program, list[Grid]]] = field(
        default_factory=list
    )
    near: list[tuple[float, int, Program, list[bool]]] = field(default_factory=list)
    nodes_per_depth: list[int] = field(default_factory=list)
    out_of_budget: bool = False


def _valid_outputs(grids: list[Grid]) -> bool:
    return all(g.is_valid(grid) for grid in grids)


class _Search:
    def __init__(self, task: SolverTask, budget: float, max_nodes: int) -> None:
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
        table = fit_colormap(train, self.targets, tests)
        if table is not None:
            step = ("colormap", table)
            self._add_solution(
                (*program, step), [apply_colormap(t, table) for t in tests]
            )
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
                for params in primitive.candidates(train, self.targets):
                    if self.over_budget():
                        return nxt
                    self.nodes += 1
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
        for _depth in range(max_depth):
            if self.result.solutions or not frontier:
                break
            frontier = self.expand(frontier, seen)
            self.result.nodes_per_depth.append(len(frontier))
            if self.result.out_of_budget:
                break
        return self.result


def search(
    task: SolverTask,
    *,
    max_depth: int = MAX_DEPTH,
    budget: float = TIME_BUDGET,
    max_nodes: int = MAX_NODES,
) -> SearchResult:
    """Enumerate programs; solutions are (cost, order, program, test outputs)."""
    return _Search(task, budget, max_nodes).run(task, max_depth)


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


def solve(task: SolverTask) -> SolverResult:
    """Return the cheapest train-consistent program's outputs plus a trace."""
    recorder = TraceRecorder(solver="dsl-search-r01")
    result = search(task)
    solutions = sorted(result.solutions, key=lambda item: (item[0], item[1]))
    ids = []
    for cost_value, _order, program, _tests in solutions:
        ids.append(
            recorder.attempt(
                f"program of cost {cost_value:.1f}",
                kind="program",
                program=to_json(program),
                train_results=[True] * len(task.train),
                data={"cost": cost_value},
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
    }
    if not solutions:
        recorder.reasoning = "No program reproduces every train pair; echo inputs."
        recorder.select(None)
        return recorder.result(list(task.test))
    recorder.reasoning = "Cheapest train-consistent program (MDL)."
    recorder.select(ids[0])
    return recorder.result(solutions[0][3])
