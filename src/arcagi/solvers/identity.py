"""A pipeline smoke baseline, not an ARC reasoning solver."""

from arcagi.tasks import Grid, SolverTask


def solve(task: SolverTask) -> tuple[Grid, ...]:
    """Return each test input unchanged."""
    return task.test
