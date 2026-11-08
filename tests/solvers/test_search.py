"""DSL search solver: finds known programs, falls back cleanly, valid traces."""

from arcagi.dsl import grid as g
from arcagi.eval import evaluate_tasks
from arcagi.solvers.search import search, solve
from arcagi.solvers.trace import validate_trace
from arcagi.tasks import Example, Task

INPUTS = [((1, 2), (3, 0)), ((0, 4), (5, 6)), ((7, 0), (0, 8))]


def _task(fn, task_id: str = "synthetic") -> Task:
    train = tuple(Example(grid, fn(grid)) for grid in INPUTS[:2])
    return Task(task_id, train, (Example(INPUTS[2], fn(INPUTS[2])),))


def test_finds_two_step_program() -> None:
    task = _task(lambda grid: g.upscale(g.rot90(grid), 2, 2))
    result = search(task.to_solver_task())
    assert result.solutions
    best = min(result.solutions, key=lambda item: (item[0], item[1]))
    assert len(best[2]) == 2


def test_solver_scores_and_records_selected_program() -> None:
    task = _task(lambda grid: g.recolor(g.flip_lr(grid), {1: 9}))
    report = evaluate_tasks([task], solve, solver_name="dsl")
    record = report["tasks"][0]
    assert record["correct"] is True
    trace = validate_trace(record["trace"])
    assert trace["selected"] is not None
    assert "metadata" in trace


def test_unsolvable_task_echoes_inputs_without_selection() -> None:
    train = (Example(((1,),), ((2, 3, 4),)), Example(((5,),), ((9,),)))
    task = Task("odd", train, (Example(((1,),), ((1,),)),))
    result = solve(task.to_solver_task())
    assert result.predictions == [((1,),)]
    assert result.trace["selected"] is None
