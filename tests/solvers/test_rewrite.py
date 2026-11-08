"""Rewrite search: rules, gates, budget, and the search.py hook."""

from arcagi.dsl import grid as g
from arcagi.solvers import rewrite, search
from arcagi.solvers.rewrite import Budget
from arcagi.solvers.rewrite_ledger import RewriteLedger
from arcagi.solvers.rewrite_rules import (
    RULES,
    delete_step,
    has_literal_grid,
    objrule_misplaced,
    param_neighbors,
    swap_adjacent,
    swap_prim,
)
from arcagi.solvers.trace import validate_trace
from arcagi.tasks import Example, Task

INPUTS = [((1, 2), (3, 0)), ((0, 4), (5, 6)), ((7, 0), (0, 8))]


class _Ctx:
    targets: list = []
    palette = [0, 3]

    def states(self, prefix):
        return None


def _task(fn) -> Task:
    train = tuple(Example(grid, fn(grid)) for grid in INPUTS[:2])
    return Task("synthetic", train, (Example(INPUTS[2], fn(INPUTS[2])),))


def test_rule_table_is_fixed_and_ordered() -> None:
    assert list(RULES)[:2] == ["residual", "append_objrule"]
    assert set(RULES) == {
        "residual",
        "append_objrule",
        "param_neighbors",
        "delete_step",
        "swap_adjacent",
        "swap_prim",
        "macro_ref",
        "insert_step",
    }


def test_param_neighbors_scans_palette_pm1_and_conn() -> None:
    program = (("fill_holes", 5), ("crop_object", "4same", "largest"))
    out = set(param_neighbors(program, _Ctx()))
    assert (("fill_holes", 0), program[1]) in out
    assert (("fill_holes", 4), program[1]) in out  # -1
    assert (("fill_holes", 7), program[1]) not in out  # not in task palette
    assert (program[0], ("crop_object", "8multi", "largest")) in out


def test_structural_rules() -> None:
    program = (("flip_lr",), ("rot90",))
    assert list(delete_step(program, _Ctx())) == [(("rot90",),), (("flip_lr",),)]
    assert list(swap_adjacent(program, _Ctx())) == [(("rot90",), ("flip_lr",))]
    swapped = set(swap_prim((("upscale", 2, 2),), _Ctx()))
    assert (("tile", 2, 2),) in swapped  # ny/nx alias fy/fx
    assert (("flip_lr", 2, 2),) not in swapped


def test_gates() -> None:
    grid = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    assert has_literal_grid((("crop_extract", ["x", grid]),))
    assert not has_literal_grid((("colormap", [[1, 2], [3, 4], [5, 6]]),))
    rule = ("move_from", "4same", "all", 1, "extract_x")
    assert not objrule_misplaced((("flip_lr",), rule, ("colormap", [[1, 2]])))
    assert objrule_misplaced((rule, ("flip_lr",)))
    assert objrule_misplaced((rule, rule))


def test_one_edit_from_near_miss_seed() -> None:
    task = _task(lambda grid: g.rot90(g.flip_lr(grid))).to_solver_task()
    ledger = RewriteLedger()
    found = rewrite.search(task, [(), (("flip_lr",), ("flip_ud",))], ledger=ledger)
    assert found
    cost, program, tests = found[0]
    assert tests == [g.rot90(g.flip_lr(INPUTS[2]))]
    assert ledger.solved and sum(ledger.hits.values()) >= 1
    assert ledger.candidates <= Budget().candidates


def test_budget_caps_candidates() -> None:
    task = Task(
        "odd",
        (Example(((1,),), ((2, 3, 4),)), Example(((5,),), ((9,),))),
        (Example(((1,),), ((1,),)),),
    ).to_solver_task()
    ledger = RewriteLedger()
    found = rewrite.search(task, [()], Budget(candidates=40), ledger)
    assert found == []
    assert ledger.candidates <= 40


def test_solve_tags_rewrite_and_records_ledger(monkeypatch) -> None:
    def no_bfs(task, **_kw):
        result = search.SearchResult()
        result.near.append((0.5, 1, (("flip_lr",), ("flip_ud",)), [False, False]))
        return result

    monkeypatch.setattr(search, "search", no_bfs)
    task = _task(lambda grid: g.rot90(g.flip_lr(grid))).to_solver_task()
    result = search.solve(task)
    trace = validate_trace(result.trace)
    assert trace["metadata"]["rewrite"]["solved"] is True
    selected = [a for a in trace["attempts"] if a["id"] == trace["selected"]][0]
    assert selected["description"].startswith("rewrite ")
    assert result.predictions == [g.rot90(g.flip_lr(INPUTS[2]))]
    monkeypatch.setattr(search, "REWRITE", False)
    off = validate_trace(search.solve(task).trace)
    assert off["metadata"]["rewrite"] is None and off["selected"] is None
