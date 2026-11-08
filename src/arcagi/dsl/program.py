"""Programs: a JSON list of steps ``[name, *params]`` applied left to right.

Example: ``[["split_overlay", "v", "xor"], ["colormap", [[10, 3]]]]``. The JSON
form is the exchange format for traces, LLM-written programs and other-language
executors.
"""

import json

from arcagi.tasks import Grid

from . import grid as g
from .learners import apply_colormap, apply_local_rule
from .registry import PRIMITIVES

type Step = tuple[object, ...]
type Program = tuple[Step, ...]


def run_step(step: Step, grid: Grid) -> Grid:
    name, *params = step
    if name == "colormap":
        return apply_colormap(grid, params[0])  # type: ignore[arg-type]
    if name == "local_rule":
        return apply_local_rule(grid, params[0], params[1])  # type: ignore[arg-type]
    return PRIMITIVES[name].apply(grid, *params)  # type: ignore[index]


def run(program: Program, grid: Grid) -> Grid:
    """Execute ``program``; raise ValueError if the result is not a valid ARC grid."""
    for step in program:
        grid = run_step(step, grid)
        height, width = g.shape(grid)
        if not (0 < height <= 30 and 0 < width <= 30):
            raise ValueError("intermediate grid out of bounds")
    if not g.is_valid(grid):
        raise ValueError("program produced an invalid grid")
    return grid


def cost(program: Program) -> float:
    """Description length: one per step, 0.1 per scalar, 0.05 per table row."""
    total = 0.0
    for step in program:
        for param in step[1:]:
            total += 0.05 * len(param) if isinstance(param, list) else 0.1
        total += 1
    return total


def to_json(program: Program) -> str:
    return json.dumps([list(step) for step in program], separators=(",", ":"))


def from_json(text: str) -> Program:
    return tuple(tuple(step) for step in json.loads(text))
