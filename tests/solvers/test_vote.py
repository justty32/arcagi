"""Voting over same-depth solutions: top-1 by cost, top-2 by votes, shape hint."""

from arcagi.solvers.search import solve
from arcagi.solvers.vote import LEARNER_WEIGHT, choose, weight
from arcagi.tasks import Example, Task

A = [((1,),)]
B = [((2,),)]
C = [((3, 3),)]


def sol(cost: float, order: int, outs, *steps: str):
    return (cost, order, tuple((s,) for s in steps), outs)


def test_weights_halve_learner_programs() -> None:
    assert weight((("flip_lr",),)) == 1.0
    assert weight((("flip_lr",), ("colormap", {}))) == LEARNER_WEIGHT
    assert weight((("object_colormap", {}),)) == LEARNER_WEIGHT


def test_top1_is_cheapest_and_votes_break_cost_ties() -> None:
    sols = [
        sol(2.0, 1, A, "rot90", "flip_lr"),
        sol(1.0, 2, B, "rot90"),
        sol(1.0, 3, A, "flip_lr"),
        sol(1.0, 4, A, "flip_ud"),
    ]
    vote = choose(sols)
    # B and A tie on cost 1.0; A has 3 votes, B has 1.
    assert vote.ranked[0][3] == A
    assert vote.votes_of(vote.ranked[0]) == 3.0
    assert vote.second == [[[2]]]


def test_top2_is_most_voted_other_output_with_learner_half_weight() -> None:
    sols = [
        sol(1.0, 1, A, "rot90"),
        sol(2.0, 2, B, "colormap"),
        sol(2.0, 3, B, "object_colormap"),
        sol(3.0, 4, C, "flip_lr", "rot90"),
    ]
    vote = choose(sols)
    assert vote.ranked[0][3] == A
    # B: 0.5 + 0.5 = 1.0 ties C: 1.0, so the cheaper B wins.
    assert vote.votes[tuple(tuple(map(tuple, grid)) for grid in B)] == 1.0
    assert vote.second == [[[2]]]
    sols.append(sol(4.0, 5, C, "transpose", "rot90"))
    assert choose(sols).second == [[[3, 3]]]


def test_penalized_programs_rank_last_and_no_second_when_unanimous() -> None:
    sols = [sol(0.5, 1, A, "local_rule"), sol(1.0, 2, B, "rot90")]
    vote = choose(sols, penalized={"local_rule"})
    assert vote.ranked[0][3] == B and vote.second == [[[1]]]
    same = choose([sol(1.0, 1, A, "rot90"), sol(2.0, 2, A, "flip_lr")])
    assert same.second is None
    assert choose([]).ranked == [] and choose([]).second is None


def test_shape_hint_swaps_in_the_cheapest_fitting_solution() -> None:
    sols = [
        sol(1.0, 1, A, "rot90"),
        sol(3.0, 2, C, "flip_lr", "rot90"),
        sol(2.0, 3, C, "tile"),
    ]
    vote = choose(sols, shape_hint=[(1, 2)])
    assert vote.hint_applied and vote.ranked[0][0] == 2.0
    assert vote.second == [[[1]]]
    # Already fitting, or nothing fits: unchanged.
    assert not choose(sols, shape_hint=[(1, 1)]).hint_applied
    kept = choose(sols, shape_hint=[(5, 5)])
    assert not kept.hint_applied and kept.ranked[0][3] == A


def test_solve_reports_vote_metadata() -> None:
    train = (
        Example(((1, 2), (1, 1)), ((2, 1), (1, 1))),
        Example(((3, 0), (0, 3)), ((0, 3), (3, 0))),
    )
    task = Task("flip", train, (Example(((1, 0), (0, 0)), ((0, 1), (0, 0))),))
    result = solve(task.to_solver_task())
    assert result.predictions == [((0, 1), (0, 0))]
    meta = result.trace["metadata"]
    assert meta["solutions"] >= 1 and meta["outputs"] >= 1
    assert meta["shape_hint_applied"] is False
    hinted = solve(task.to_solver_task(), shape_hint=[(2, 2)])
    assert hinted.predictions == result.predictions
