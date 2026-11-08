"""File-protocol wrapper used by ``aos/solver/_entry``.

``python -m arcagi.blocks.solver INPUT OUTPUT [TRACE]`` reads an
``arcagi-solver-input/1`` request, solves it in-process (default
``arcagi.solvers.search:solve``; override with ``$ARCAGI_SOLVER``), and writes
the ``{task_id: [grid, ...]}`` response plus an optional trace file.
"""

import json
import os
import sys
from pathlib import Path

from arcagi.solvers import load_solver
from arcagi.solvers.trace import split_solver_output
from arcagi.tasks import Example, SolverTask, validate_grid

DEFAULT_SOLVER = "arcagi.solvers.search:solve"


def read_request(path: Path) -> SolverTask:
    request = json.loads(path.read_text(encoding="utf-8"))
    task = request["task"]
    train = tuple(
        Example(validate_grid(pair["input"]), validate_grid(pair["output"]))
        for pair in task["train"]
    )
    test = tuple(validate_grid(pair["input"]) for pair in task["test"])
    return SolverTask(str(request["task_id"]), train, test)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3):
        print(
            "usage: python -m arcagi.blocks.solver INPUT OUTPUT [TRACE]",
            file=sys.stderr,
        )
        return 2
    task = read_request(Path(argv[0]))
    solver = load_solver(os.environ.get("ARCAGI_SOLVER", DEFAULT_SOLVER))
    predictions, trace, _error = split_solver_output(solver(task))
    response = {task.task_id: [[list(row) for row in grid] for grid in predictions]}
    Path(argv[1]).write_text(json.dumps(response) + "\n", encoding="utf-8")
    if len(argv) == 3 and trace is not None:
        Path(argv[2]).write_text(json.dumps(trace) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
