"""Immutable task types and the answer-free solver view."""

from dataclasses import dataclass

type Grid = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class Example:
    input: Grid
    output: Grid | None = None


@dataclass(frozen=True)
class SolverTask:
    """The solver contract: training pairs and test inputs, never test answers."""

    task_id: str
    train: tuple[Example, ...]
    test: tuple[Grid, ...]


@dataclass(frozen=True)
class Task:
    task_id: str
    train: tuple[Example, ...]
    test: tuple[Example, ...]

    def to_solver_task(self) -> SolverTask:
        """Strip test labels before passing a task to a solver."""
        return SolverTask(self.task_id, self.train, tuple(e.input for e in self.test))

    def to_dict(self) -> dict[str, list[dict[str, list[list[int]]]]]:
        """Return the original ARC JSON shape without metadata."""
        return {
            name: [
                {
                    "input": [list(row) for row in example.input],
                    **(
                        {"output": [list(row) for row in example.output]}
                        if example.output is not None
                        else {}
                    ),
                }
                for example in examples
            ]
            for name, examples in (("train", self.train), ("test", self.test))
        }
