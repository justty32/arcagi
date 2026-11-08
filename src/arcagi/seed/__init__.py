"""The empty-tree seed language: generic primitives, types, interpreter,
size-ordered typed enumerator and a block library.

``enumerate`` runs the enumerator over many tasks (optionally in worker
processes); results are deterministic and returned in task order.
"""

from __future__ import annotations

import multiprocessing
from dataclasses import dataclass
from typing import Any

from . import enum, interp, library, prims, types
from .enum import Result, solve
from .interp import EvalError, Program, run, size
from .library import Block, Library
from .prims import PRIMS, Prim

__all__ = [
    "PRIMS",
    "Block",
    "EvalError",
    "Library",
    "Prim",
    "Program",
    "Result",
    "Solution",
    "enum",
    "enumerate",
    "interp",
    "library",
    "prims",
    "run",
    "size",
    "solve",
    "types",
]


@dataclass(frozen=True)
class Solution:
    task_id: str
    program: Program | None
    train_ok: bool
    test_ok: bool
    nodes: int
    nodes_to_first: int | None
    seconds: float
    near: tuple = ()


def _check(prog: Program, pairs: Any, lib: Library) -> bool:
    if not pairs:
        return False
    for ex in pairs:
        if ex.output is None:
            return False
        try:
            if run(prog, ex.input, lib) != interp.to_value(ex.output):
                return False
        except EvalError:
            return False
    return True


def _one(job: tuple[Library, Any, int, dict | None]) -> Solution:
    lib, task, budget, order = job
    train = [(ex.input, ex.output) for ex in task.train]
    res = solve(train, lib, budget, order)
    prog = res.program
    ok_train = prog is not None and _check(prog, task.train, lib)
    ok_test = ok_train and _check(prog, task.test, lib)
    return Solution(
        task.task_id,
        prog,
        ok_train,
        ok_test,
        res.nodes,
        res.nodes_to_first,
        res.seconds,
        tuple(res.near),
    )


def enumerate(  # noqa: A001 - name fixed by the r07 interface
    lib: Library,
    tasks: list[Any],
    budget_nodes: int,
    workers: int = 1,
    order: dict | None = None,
) -> list[Solution]:
    """Solve each task with ``budget_nodes`` candidates; results in task order."""
    jobs = [(lib, t, budget_nodes, order) for t in tasks]
    if workers <= 1 or len(jobs) <= 1:
        return [_one(j) for j in jobs]
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(min(workers, len(jobs))) as pool:
        return pool.map(_one, jobs, chunksize=1)
