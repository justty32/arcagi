"""Apply one block to one grid: ``python -m arcagi.blocks.run <name>``.

stdin: ``{"grid": [[...]], "params": [...]}``; stdout: the result grid as JSON.
Primitives and learners use the in-process implementation; macros run their
``program.json``. Exit code 2 on unknown blocks or invalid input.
"""

import json
import sys
from pathlib import Path

from arcagi.dsl.program import Program, run_step
from arcagi.tasks import Grid

from . import LEARNER_NAMES, default_blocks_root
from .catalog import load_macro_program


def _program_for(name: str, params: list, root: Path) -> Program:
    from arcagi.dsl.registry import PRIMITIVES

    if name in PRIMITIVES or name in LEARNER_NAMES:
        return ((name, *params),)
    macro = load_macro_program(root / name)
    if macro is None:
        raise KeyError(f"unknown block {name!r}")
    return macro


def apply_block(name: str, grid: Grid, params: list, root: Path | None = None) -> Grid:
    program = _program_for(name, params, root or default_blocks_root())
    for step in program:
        grid = run_step(step, grid)
    return grid


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m arcagi.blocks.run NAME < request.json", file=sys.stderr)
        return 2
    try:
        request = json.loads(sys.stdin.read())
        grid = tuple(tuple(int(c) for c in row) for row in request["grid"])
        params = list(request.get("params", []))
        result = apply_block(argv[0], grid, params)
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        print(f"arcagi.blocks.run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps([list(row) for row in result], separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
