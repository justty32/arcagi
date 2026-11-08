"""Parity for the S1 extension primitives (``x_*``): native ``--run`` vs Python.

Every training grid (train inputs/outputs and test inputs) is run through every
target-free parameter of each ``x_*`` primitive, with and without the task
background context, plus seeded random 2-step ext compositions. Outputs and
errors must agree exactly.
"""

import json
import os
import random
import subprocess
from pathlib import Path

import pytest

from arcagi.dsl import background, program
from arcagi.dsl.ext import prims as ext
from arcagi.tasks import Grid, load_tasks

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcsearch"
if not os.access(BIN, os.X_OK):
    pytest.skip(f"{BIN} not built", allow_module_level=True)

SEED = 20261108
COMPOSITIONS_PER_TASK = 20

type Step = list[object]


def wide_steps(grid: Grid) -> list[Step]:
    colors = sorted({c for row in grid for c in row})
    steps: list[Step] = [
        ["x_ray", d, m, c]
        for c in (-1, *colors)
        for d in ext.RAY_DIRS
        for m in ("pass", "stop")
    ]
    steps += [["x_connect", a] for a in ext.CONNECT_AXES]
    steps += [["x_compress", m] for m in ext.COMPRESS_MODES]
    steps += [["x_crop_color", c, m] for c in (*colors, 5) for m in ext.CROP_MODES]
    steps += [["x_period", m, c] for c in colors for m in ext.PERIOD_MODES]
    return steps


def python_out(steps: list[Step], grid: Grid, bg: int | None):
    with background.task_context(bg):
        try:
            out = program.run(tuple(tuple(s) for s in steps), grid)
        except (ValueError, IndexError, KeyError):
            return None
    return [list(row) for row in out]


def build_cases():
    rng = random.Random(SEED)
    cases = []
    for task in load_tasks(ROOT / "data/ARC-AGI/data/training"):
        grids = [e.input for e in task.train] + [e.output for e in task.train]
        bg = background.task_background(grids)
        grids += [t.input for t in task.test]
        grid = rng.choice(grids)
        steps = wide_steps(grid)
        for step in steps:
            cases.append(([step], grid, None))
            cases.append(([step], grid, bg))
        for _ in range(COMPOSITIONS_PER_TASK):
            cases.append(
                ([rng.choice(steps), rng.choice(steps)], rng.choice(grids), bg)
            )
    return cases


def test_ext_run_matches_python() -> None:
    cases = build_cases()
    lines = "".join(
        json.dumps({"program": steps, "grid": [list(r) for r in grid], "bg": bg}) + "\n"
        for steps, grid, bg in cases
    )
    proc = subprocess.run(
        [str(BIN), "--run"], input=lines, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    native = [json.loads(line) for line in proc.stdout.splitlines()]
    assert len(native) == len(cases)
    bad = []
    for (steps, grid, bg), got in zip(cases, native, strict=True):
        want = python_out(steps, grid, bg)
        if (None if got.get("error") else got["out"]) != want:
            bad.append((steps, bg))
    assert not bad, f"{len(bad)}/{len(cases)} mismatches, e.g. {bad[:5]}"
