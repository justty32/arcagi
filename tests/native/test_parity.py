"""Parity: native ``arcsearch --run`` must match ``arcagi.dsl.program.run``.

Grids are seeded samples of training-task inputs/outputs. Each ported primitive
is run with the parameters Python's ``candidates`` proposes on the task plus a
wide, target-free parameter set; random 2-3 step compositions are added. All
cases go to the binary in one batch; outputs (or errors) must agree exactly.
"""

import json
import os
import random
import subprocess
from pathlib import Path

import pytest

from arcagi.dsl import cells as cells_mod
from arcagi.dsl import grid as g
from arcagi.dsl import primitives as prims
from arcagi.dsl import primitives_more as more
from arcagi.dsl import program
from arcagi.dsl.learners import fit_colormap, fit_local_rule
from arcagi.dsl.registry import CATALOG, PRIMITIVES
from arcagi.tasks import Grid, Task, load_tasks

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcsearch"
if not os.access(BIN, os.X_OK):
    pytest.skip(f"{BIN} not built", allow_module_level=True)

SEED = 20261108
N_TASKS = 40
GRIDS_PER_TASK = 6
COMPOSITIONS_PER_TASK = 40
MAX_REPORT = 10

PORTED = {**prims.BASE, **more.MORE, **cells_mod.CELLS}

D4 = (
    "flip_lr",
    "flip_ud",
    "transpose",
    "rot90",
    "rot180",
    "rot270",
    "anti_transpose",
)
CROP_HOWS = ("largest", "smallest", "unique_color", "most_colors", "top_left")
GRAVITY = ("down", "up", "left", "right")
FACTORS = [(fy, fx) for fy in range(1, 5) for fx in range(1, 5) if (fy, fx) != (1, 1)]
SELF_TILE_MAX_CELLS = 100  # keep Python fast: self_tile output is (h*h, w*w)

type Step = list[object]
type Case = tuple[str, list[Step], Grid]


def _ported_macros() -> list[str]:
    """Live macros whose every step is a ported primitive (ported as well)."""
    return sorted(
        name
        for name, steps in CATALOG.macros().items()
        if name in PRIMITIVES and all(step[0] in PORTED for step in steps)
    )


MACROS = _ported_macros()


def _colors(grid: Grid) -> list[int]:
    return sorted(g.color_counts(grid))


def wide_steps(grid: Grid) -> list[Step]:
    """Target-free parameter sets for every ported step on ``grid``."""
    steps: list[Step] = [[name] for name in (*D4, "crop_bbox", "fill_enclosed")]
    for name in ("upscale", "downscale", "tile"):
        steps += [[name, fy, fx] for fy, fx in FACTORS]
    steps += [["split_overlay", axis, op] for axis in "hv" for op in prims._OPS]
    steps += [
        ["crop_object", conn, how] for conn in ("4same", "8multi") for how in CROP_HOWS
    ]
    steps += [["gravity", d] for d in GRAVITY]
    steps += [["mirror_tile", m] for m in ("lr", "ud", "quad")]
    height, width = g.shape(grid)
    if height * width <= SELF_TILE_MAX_CELLS:
        steps += [["self_tile", m] for m in ("pos", "neg")]
    colors = _colors(grid)
    steps += [["symmetrize", m, c] for m in more._MIRRORS for c in colors]
    steps += [["pick_cell", how] for how in cells_mod.PICKS]
    steps += [["pick_cell", "has_color", c] for c in colors]
    steps += [["overlay_cells", op] for op in (*cells_mod._OPS, "stack", "stack_rev")]
    for name in ("cells_to_pixels", "fill_cells"):
        steps += [[name, mode] for mode in cells_mod.SUMMARIES]
    steps += [["colormap", [[a, b]]] for a in colors for b in range(10) if a != b]
    steps += [[name] for name in MACROS]
    return steps


def _jsonable(value: object) -> object:
    if isinstance(value, tuple | list):
        return [_jsonable(v) for v in value]
    return value


def task_steps(task: Task) -> list[Step]:
    """Python-inferred parameters on the task's train pairs, plus fitted learners."""
    states = [e.input for e in task.train]
    targets = [e.output for e in task.train]
    steps: list[Step] = []
    for name, prim in PORTED.items():
        try:
            params = list(prim.candidates(states, targets))
        except (ValueError, IndexError, KeyError):
            continue
        steps += [[name, *_jsonable(p)] for p in params]
    table = fit_colormap(states, targets, [])
    if table:
        steps.append(["colormap", table])
    for features in ("n4", "n8"):
        table = fit_local_rule(states, targets, [], features)
        if table:
            steps.append(["local_rule", features, table])
    return steps


def task_grids(task: Task, rng: random.Random) -> list[Grid]:
    seen: list[Grid] = []
    for example in task.train:
        for grid in (example.input, example.output):
            if grid is not None and grid not in seen:
                seen.append(grid)
    if len(seen) > GRIDS_PER_TASK:
        seen = rng.sample(seen, GRIDS_PER_TASK)
    return seen


def build_cases() -> list[Case]:
    rng = random.Random(SEED)
    tasks = load_tasks(ROOT / "data" / "ARC-AGI" / "data" / "training")
    cases: list[Case] = []
    for task in rng.sample(tasks, N_TASKS):
        grids = task_grids(task, rng)
        inferred = task_steps(task)
        pool = list(inferred)
        for grid in grids:
            wide = wide_steps(grid)
            pool += rng.sample(wide, min(20, len(wide)))
            cases += [(task.task_id, [step], grid) for step in (*inferred, *wide)]
        for _ in range(COMPOSITIONS_PER_TASK):
            steps = [rng.choice(pool) for _ in range(rng.randint(2, 3))]
            if rng.random() < 0.5:  # resolve a possible marker color
                steps.append(["colormap", [[prims.MARK, rng.randrange(10)]]])
            cases.append((task.task_id, steps, rng.choice(grids)))
    return cases


def python_out(steps: list[Step], grid: Grid) -> list[list[int]] | None:
    prog = program.from_json(json.dumps(steps))
    try:
        out = program.run(prog, grid)
    except (ValueError, IndexError, KeyError):
        return None
    return [list(row) for row in out]


def native_out(cases: list[Case]) -> list[dict[str, object]]:
    lines = [
        json.dumps({"program": steps, "grid": [list(r) for r in grid]})
        for _, steps, grid in cases
    ]
    proc = subprocess.run(
        [str(BIN), "--run"],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        timeout=600,
        cwd=ROOT,
        check=False,
    )
    assert proc.returncode == 0, f"arcsearch --run failed: {proc.stderr[-2000:]}"
    replies = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert len(replies) == len(cases), (
        f"expected {len(cases)} reply lines, got {len(replies)}"
    )
    return replies


def _covered(cases: list[Case]) -> set[str]:
    return {str(step[0]) for _, steps, _ in cases for step in steps}


def test_native_run_matches_python() -> None:
    cases = build_cases()
    missing = (set(PORTED) | {"colormap"} | set(MACROS)) - _covered(cases)
    assert not missing, f"sampling never exercised: {sorted(missing)}"
    replies = native_out(cases)
    mismatches = []
    for (task_id, steps, grid), reply in zip(cases, replies, strict=True):
        expected = python_out(steps, grid)
        if expected is None:
            ok = reply.get("error") is True
        else:
            ok = reply.get("out") == expected
        if not ok:
            mismatches.append((task_id, steps, grid, expected, reply))
    if mismatches:
        report = [f"{len(mismatches)}/{len(cases)} mismatches; first {MAX_REPORT}:"]
        for task_id, steps, grid, expected, reply in mismatches[:MAX_REPORT]:
            report.append(
                f"- task {task_id} program {json.dumps(steps)} "
                f"grid {g.shape(grid)}: python="
                f"{'error' if expected is None else json.dumps(expected)} "
                f"native={json.dumps(reply)[:400]}"
            )
        pytest.fail("\n".join(report))
