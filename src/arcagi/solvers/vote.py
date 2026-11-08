"""Choose top-1 / top-2 among train-consistent programs by cost and votes.

Every solution votes for its test outputs with weight 1, or ``LEARNER_WEIGHT``
when it ends in a fitted learner (those overfit most). Top-1 is the cheapest
solution (``penalized`` steps such as ``local_rule`` rank last; equal cost goes
to the larger vote). With a ``shape_hint`` (one ``(h, w)`` per test input), a
top-1 whose outputs miss the hint is replaced by the cheapest solution that
fits it. Top-2 is the most-voted output different from top-1.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from arcagi.dsl import grid as g
from arcagi.dsl.program import Program
from arcagi.tasks import Grid

LEARNERS = frozenset({"colormap", "object_colormap", "local_rule"})
LEARNER_WEIGHT = 0.5

type Solution = tuple[float, int, Program, list[Grid]]
type Key = tuple[Grid, ...]


@dataclass
class Vote:
    ranked: list[Solution] = field(default_factory=list)  # top-1 first
    votes: dict[Key, float] = field(default_factory=dict)
    second: list[Grid] | None = None
    hint_applied: bool = False

    def votes_of(self, solution: Solution) -> float:
        return self.votes.get(_key(solution[3]), 0.0)


def weight(program: Program) -> float:
    return LEARNER_WEIGHT if any(step[0] in LEARNERS for step in program) else 1.0


def _key(tests: Sequence[Grid]) -> Key:
    return tuple(tuple(tuple(row) for row in grid) for grid in tests)


def fits(tests: Sequence[Grid], shape_hint: Sequence[tuple[int, int]]) -> bool:
    if len(tests) != len(shape_hint):
        return False
    return all(g.shape(t) == tuple(s) for t, s in zip(tests, shape_hint, strict=True))


def choose(
    solutions: Sequence[Solution],
    *,
    penalized: Collection[str] = (),
    shape_hint: Sequence[tuple[int, int]] | None = None,
) -> Vote:
    """Rank ``solutions`` (cost, order, program, test outputs) and pick top-2."""
    vote = Vote()
    if not solutions:
        return vote
    for sol in solutions:
        k = _key(sol[3])
        vote.votes[k] = vote.votes.get(k, 0.0) + weight(sol[2])

    def rank(sol: Solution) -> tuple[bool, float, float, int]:
        bad = any(step[0] in penalized for step in sol[2])
        return (bad, sol[0], -vote.votes[_key(sol[3])], sol[1])

    ranked = sorted(solutions, key=rank)
    if shape_hint is not None and not fits(ranked[0][3], shape_hint):
        fitting = [s for s in ranked if fits(s[3], shape_hint)]
        if fitting:
            best = fitting[0]
            ranked.remove(best)
            ranked.insert(0, best)
            vote.hint_applied = True
    vote.ranked = ranked
    top = _key(ranked[0][3])
    others = [s for s in ranked if _key(s[3]) != top]
    if others:
        # Most votes wins; ties keep rank order (sorted is stable).
        best = min(others, key=lambda s: -vote.votes[_key(s[3])])
        vote.second = [[list(row) for row in grid] for grid in best[3]]
    return vote
