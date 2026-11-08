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

from arcagi.dsl import cells, grid as g, primitives as p, primitives_more as more
from arcagi.dsl.learners import fit_colormap, fit_local_rule
from arcagi.dsl.program import run, run_step
from arcagi.dsl.registry import CATALOG, PRIMITIVES
from arcagi.tasks import load_task

ROOT = Path(__file__).resolve().parents[2]
PORTED = set(p.BASE) | set(more.MORE) | set(cells.CELLS)
MACROS = {
    name for name, program in CATALOG.macros().items()
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
                        ok = all(len(s) % fy == 0 and len(s[0]) % fx == 0 for s in states)
                    else:
                        ok = all(len(s) * fy <= 30 and len(s[0]) * fx <= 30 for s in states)
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
            params = [(conn, how) for conn in ("4same", "8multi") for how in (
                "largest", "smallest", "unique_color", "most_colors", "top_left",
            )]
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
            modes = cells.PICKS if name == "pick_cell" else (
                (*cells._OPS, "stack", "stack_rev") if name == "overlay_cells" else cells.SUMMARIES
            )
            params = [(mode,) for mode in modes]
            if name == "pick_cell":
                params.extend(("has_color", c) for c in colors)
        else:
            params = [()]
        out.extend((name, *param) for param in params)
    out.extend(("colormap", [[a, b]]) for a in colors for b in range(10) if a != b)
    return out


def expected(program, grid):
    try:
        return {"out": run(tuple(program), grid)}
    except (ValueError, IndexError, KeyError):
        return {"error": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261108)
    parser.add_argument("--programs", type=int, default=30, help="Random programs per task")
    parser.add_argument("--task", action="append", help="Training task ID; repeatable")
    parser.add_argument("--sweep", action="store_true")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    requests = []
    random_count = 0
    for task_id in (args.task or ("007bbfb7", "3c9b0459", "6150a2bd")):
        task = load_task(ROOT / "data" / "ARC-AGI" / "data" / "training" / f"{task_id}.json")
        for _ in range(args.programs):
            grid = rng.choice(task.train).input
            state = grid
            program = []
            for _ in range(rng.randint(1, 3)):
                step = rng.choice(wide([state]))
                program.append(step)
                try:
                    new = run_step(step, state)
                    if 0 < len(new) <= 30 and 0 < len(new[0]) <= 30:
                        state = new
                except (ValueError, IndexError, KeyError):
                    pass
            requests.append({"program": program, "grid": grid})
            random_count += 1
        if args.sweep:
            for example in (*task.train, *task.test):
                for grid in (example.input, example.output):
                    for step in wide([grid]):
                        requests.append({"program": [step], "grid": grid})
                        requests.append({"program": [step, ("colormap", [[10, 3]])], "grid": grid})
            states = [e.input for e in task.train]
            targets = [g.recolor(s, {c: (c + 1) % 10 for c in range(10)}) for s in states]
            table = fit_colormap(states, targets, states)
            if table is not None:
                for grid in states:
                    requests.append({"program": [("colormap", table)], "grid": grid})
            for features in ("n4", "n8"):
                table = fit_local_rule(states, targets, states, features)
                if table is not None:
                    for grid in states:
                        requests.append({"program": [("local_rule", features, table)], "grid": grid})
    payload = "".join(json.dumps(request) + "\n" for request in requests)
    completed = subprocess.run([str(ROOT / "native" / "bin" / "arcsearch"), "--run"],
                               input=payload, text=True, capture_output=True, check=True)
    lines = completed.stdout.splitlines()
    if len(lines) != len(requests):
        raise SystemExit(f"Expected {len(requests)} lines, received {len(lines)}")
    successes = errors = 0
    for index, (request, line) in enumerate(zip(requests, lines, strict=True)):
        want = json.loads(json.dumps(expected(request["program"], request["grid"])))
        got = json.loads(line)
        if want != got:
            print(json.dumps({"index": index, "request": request, "python": want, "native": got}))
            raise SystemExit("Parity mismatch")
        if "out" in got:
            successes += 1
        else:
            errors += 1
    print(json.dumps({"agreements": len(requests), "random_programs": random_count,
                      "valid_outputs": successes, "matching_errors": errors, "seed": args.seed}))


if __name__ == "__main__":
    main()
