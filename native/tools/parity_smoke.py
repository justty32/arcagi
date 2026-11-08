"""Compare random wide-candidate programs with Python (not a pytest suite).

Run from the repository root with `nice -n 19 uv run python
native/tools/parity_smoke.py`. --sweep also checks every wide single-step
candidate, both with and without a terminal marker conversion.
"""

import argparse
import json
import random
import subprocess
from pathlib import Path

from arcagi.dsl import background as bgc
from arcagi.dsl import cells, objects, predicates
from arcagi.dsl import grid as g
from arcagi.dsl import objects_props as props
from arcagi.dsl import primitives as p
from arcagi.dsl import primitives_more as more
from arcagi.dsl.learners import fit_colormap, fit_local_rule
from arcagi.dsl.objects_learner import fit_object_colormap
from arcagi.dsl.program import run, run_step
from arcagi.dsl.registry import CATALOG, PRIMITIVES
from arcagi.tasks import load_task

ROOT = Path(__file__).resolve().parents[2]
PORTED = set(p.BASE) | set(more.MORE) | set(cells.CELLS)
MACROS = {
    name
    for name, program in CATALOG.macros().items()
    if name in PRIMITIVES and all(step[0] in PORTED for step in program)
}


def wide(states):
    """Target-independent candidate set, in primitive registry order."""
    colors = sorted({v for s in states for row in s for v in row})
    out = []
    for name in PRIMITIVES:
        params = []
        if name in MACROS:
            params = [()]
        elif name not in PORTED:
            continue
        elif name in ("upscale", "tile", "downscale"):
            for fy in range(1, 5):
                for fx in range(1, 5):
                    if (fy, fx) == (1, 1):
                        continue
                    if name == "downscale":
                        ok = all(
                            len(s) % fy == 0 and len(s[0]) % fx == 0 for s in states
                        )
                    else:
                        ok = all(
                            len(s) * fy <= 30 and len(s[0]) * fx <= 30 for s in states
                        )
                    if ok:
                        params.append((fy, fx))
        elif name == "split_overlay":
            for axis in ("h", "v"):
                try:
                    for state in states:
                        p._halves(state, axis)
                except ValueError:
                    continue
                params.extend((axis, op) for op in p._OPS)
        elif name == "crop_object":
            params = [
                (conn, how)
                for conn in ("4same", "8multi")
                for how in (
                    "largest",
                    "smallest",
                    "unique_color",
                    "most_colors",
                    "top_left",
                )
            ]
        elif name == "mirror_tile":
            params = [(m,) for m in ("lr", "ud", "quad")]
        elif name == "self_tile":
            params = [(m,) for m in ("pos", "neg")]
        elif name == "gravity":
            params = [(d,) for d in ("down", "up", "left", "right")]
        elif name == "symmetrize":
            params = [(m, c) for m in more._MIRRORS for c in colors]
        elif name in cells.CELLS:
            if not all(cells.split(state) is not None for state in states):
                continue
            modes = (
                cells.PICKS
                if name == "pick_cell"
                else (
                    (*cells._OPS, "stack", "stack_rev")
                    if name == "overlay_cells"
                    else cells.SUMMARIES
                )
            )
            params = [(mode,) for mode in modes]
            if name == "pick_cell":
                params.extend(("has_color", c) for c in colors)
        else:
            params = [()]
        out.extend((name, *param) for param in params)
    out.extend(("colormap", [[a, b]]) for a in colors for b in range(10) if a != b)
    return out


def expected(program, grid, bg=None):
    try:
        with bgc.task_context(bg):
            return {"out": run(tuple(program), grid)}
    except (ValueError, IndexError, KeyError):
        return {"error": True}


def object_wide(states, targets):
    """Common attribute/value selectors, capped at 24 per connectivity."""
    out = []
    colors = sorted({c for t in targets for row in t for c in row})
    for conn in props.CONNS:
        groups = [props.extract(s, conn) for s in states]
        selectors = []
        for attr in props.ATTRS:
            values = set.intersection(
                *({o.props[attr] for o in group} for group in groups)
            )
            selectors.extend((attr, value) for value in sorted(values))
        for attr, value in selectors[:24]:
            for name in objects.OBJECTS:
                if name not in PRIMITIVES or name == "fill_holes":
                    continue
                params = (
                    colors
                    if name == "recolor_sel"
                    else (
                        tuple(objects.DIRS)
                        if name in ("move_sel", "extend_sel")
                        else (None,)
                    )
                )
                for param in params:
                    step = (name, conn, attr, value)
                    out.append(step if param is None else (*step, param))
    if "fill_holes" in PRIMITIVES:
        out.extend(("fill_holes", c) for c in colors)
    return out


def collect(task, args, rng, requests):
    states = [e.input for e in task.train]
    targets = [e.output for e in task.train]
    bg = bgc.task_background(states + targets)
    with bgc.task_context(bg):
        for _ in range(args.programs):
            grid = rng.choice(states)
            current = states
            state = grid
            program = []
            for _ in range(rng.randint(1, 2 if args.objects else 3)):
                pool = object_wide(current, targets) if args.objects else wide([state])
                if not pool:
                    break
                step = rng.choice(pool)
                program.append(step)
                try:
                    if args.objects:
                        new = [run_step(step, s) for s in current]
                        if all(0 < len(s) <= 30 and 0 < len(s[0]) <= 30 for s in new):
                            current = new
                    else:
                        new = run_step(step, state)
                        if 0 < len(new) <= 30 and 0 < len(new[0]) <= 30:
                            state = new
                except (ValueError, IndexError, KeyError):
                    pass
            for sample in (
                states + list(e.input for e in task.test) if args.objects else [grid]
            ):
                requests.append({"program": program, "grid": sample, "bg": bg})
        if args.sweep:
            for example in (*task.train, *task.test):
                for grid in (example.input, example.output):
                    if grid is None:
                        continue
                    pool = (
                        object_wide([grid], targets) if args.objects else wide([grid])
                    )
                    if args.objects:
                        for conn in props.CONNS:
                            pool.extend(
                                ("recolor_sel", conn, "pred", name, 3)
                                for name in predicates.LIVE
                            )
                            pool.extend(
                                ("move_sel", conn, "pred", body, "right")
                                for body in (
                                    ["rank", "size", "max"],
                                    ["not", ["eq", "color", 2]],
                                    ["and", ["gt", "size", 1], ["lt", "size", 20]],
                                    ["or", ["eq", "color", 1], ["eq", "color", 2]],
                                )
                            )
                    for step in pool:
                        requests.append({"program": [step], "grid": grid, "bg": bg})
                        requests.append(
                            {
                                "program": [step, ("colormap", [[10, 3]])],
                                "grid": grid,
                                "bg": bg,
                            }
                        )
            if args.objects:
                for name, prim in objects.OBJECTS.items():
                    if name in PRIMITIVES:
                        for params in prim.candidates(states, targets):
                            for grid in states:
                                requests.append(
                                    {
                                        "program": [(name, *params)],
                                        "grid": grid,
                                        "bg": bg,
                                    }
                                )
            recolored = [
                g.recolor(s, {c: (c + 1) % 10 for c in range(10)}) for s in states
            ]
            learned = []
            table = fit_colormap(states, recolored, states)
            if table is not None:
                learned.append(("colormap", table))
            # Exercise both ordinary and split object tables with changed labels.
            for color in (2, 3):
                outs = [
                    objects._recolor_sel(s, "4same", "is_largest", 1, color)
                    for s in states
                ]
                table = fit_object_colormap(states, outs, states)
                if table is not None:
                    learned.append(("object_colormap", table))
            for features in ("n4", "n8"):
                table = fit_local_rule(states, recolored, states, features)
                if table is not None:
                    learned.append(("local_rule", features, table))
            for step in learned:
                for grid in states:
                    requests.append({"program": [step], "grid": grid, "bg": bg})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261108)
    parser.add_argument(
        "--programs", type=int, default=50, help="Random programs per task"
    )
    parser.add_argument("--task", action="append", help="Training task ID; repeatable")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument(
        "--objects", action="store_true", help="Object programs of 1-2 steps"
    )
    args = parser.parse_args()
    rng = random.Random(args.seed)
    requests = []
    tasks = args.task or ("007bbfb7", "00d62c1b", "017c7c7b", "025d127b", "0520fde7")
    for task_id in tasks:
        task = load_task(
            ROOT / "data" / "ARC-AGI" / "data" / "training" / f"{task_id}.json"
        )
        collect(task, args, rng, requests)
    payload = "".join(json.dumps(request) + "\n" for request in requests)
    completed = subprocess.run(
        [str(ROOT / "native" / "bin" / "arcsearch"), "--run"],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
    )
    lines = completed.stdout.splitlines()
    if len(lines) != len(requests):
        raise SystemExit(f"Expected {len(requests)} lines, received {len(lines)}")
    successes = errors = 0
    for index, (request, line) in enumerate(zip(requests, lines, strict=True)):
        want = json.loads(
            json.dumps(expected(request["program"], request["grid"], request["bg"]))
        )
        got = json.loads(line)
        if want != got:
            print(
                json.dumps(
                    {"index": index, "request": request, "python": want, "native": got}
                )
            )
            raise SystemExit("Parity mismatch")
        if "out" in got:
            successes += 1
        else:
            errors += 1
    print(
        json.dumps(
            {
                "agreements": len(requests),
                "random_programs": len(tasks) * args.programs,
                "valid_outputs": successes,
                "matching_errors": errors,
                "seed": args.seed,
            }
        )
    )


if __name__ == "__main__":
    main()
