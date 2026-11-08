"""Run Python search, native seeded search, then Python prefix completion."""

# Capture process time before importing the solver and its live catalog.
# ruff: noqa: E402

import time

T0 = time.perf_counter()
DEADLINE = T0 + 19.0

import json
import os
import signal
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from arcagi.dsl import background
from arcagi.dsl.program import cost, from_json, run, to_json
from arcagi.dsl.registry import PRIMITIVES
from arcagi.solvers import search, vote
from arcagi.solvers.trace import TraceRecorder, validate_trace
from arcagi.tasks import Example, SolverTask
from arcagi.tasks.validation import task_from_dict

ROOT = Path(__file__).resolve().parent.parent
ERRORS = (ValueError, IndexError, KeyError)
# Table learners overfit; the color-variable rule ranks with local_rule.
PENALIZED = search.PENALIZED | {"x_vrule"}
# Support gate (D-r7-18, re-selected on training only by
# native/tools/gate_select.py, reports/native-s1d/): a program ending in a
# table learner needs enough train output cells per table row when other
# steps come before the table; a table that is the whole program is not gated.
SUPPORT_MIN = (0.0, 16.0)  # (table is the whole program, table after other steps)
GUARDED = ("colormap", "local_rule", "x_vrule")


def _rows(step):
    if step[0] in ("local_rule", "x_vrule"):
        return len(step[2])
    if step[0] == "colormap":
        return len(step[1])
    return 0


def unsupported(program, train_cells):
    """True when a terminal colormap / local_rule / x_vrule table has too few
    train output cells per row."""
    last = program[-1]
    if last[0] not in GUARDED:
        return False
    rows = _rows(last)
    if not rows:
        return False
    need = SUPPORT_MIN[0] if len(program) == 1 else SUPPORT_MIN[1]
    return train_cells / rows < need


class DeadlineReached(BaseException):
    """End a bounded Python phase, including candidate generation and learners."""


def _alarm(_signum, _frame):
    raise DeadlineReached


@contextmanager
def until(deadline):
    """Use wall time so cooperative Python checks cannot overrun the task."""
    left = deadline - time.perf_counter()
    if left <= 0:
        raise DeadlineReached
    previous = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, left)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def write_result(request, output, trace_path, predictions, trace):
    """Write the external response and the standard trace dictionary."""
    Path(output).write_text(json.dumps({request["task_id"]: predictions}) + "\n")
    if trace_path:
        trace["elapsed_seconds"] = time.perf_counter() - T0
        Path(trace_path).write_text(json.dumps(validate_trace(trace)) + "\n")


def make_seeds(task, ported, seeds):
    """Apply unported live primitives once; dedupe by train states."""
    states = [e.input for e in task.train]
    targets = [e.output for e in task.train]
    grids = states + list(task.test)
    seen = set()
    for name, primitive in PRIMITIVES.items():
        if name in ported:
            continue
        try:
            for params in primitive.candidates(states, targets):
                try:
                    new = [primitive.apply(grid, *params) for grid in grids]
                    if any(not (0 < len(g) <= 30 and 0 < len(g[0]) <= 30) for g in new):
                        continue
                    signature = tuple(new[: len(states)])
                    if signature in seen:
                        continue
                    seen.add(signature)
                    seeds.append({"program": [[name, *params]], "grids": new})
                    if len(seeds) >= 300:
                        return
                except ERRORS:
                    continue
        except ERRORS:
            continue


def main():
    request_path, output_path = sys.argv[1:3]
    request = json.loads(Path(request_path).read_text())
    trace_path = sys.argv[3] if len(sys.argv) > 3 else request.get("trace_path")
    task = task_from_dict(request["task"], task_id=request["task_id"]).to_solver_task()
    phases = {
        "startup": time.perf_counter() - T0,
        "python": 0.0,
        "seeds": 0.0,
        "cpp": 0.0,
        "prefix_py": 0.0,
        "verify": 0.0,
    }
    origins = {"cpp": 0, "seed": 0, "prefix_py": 0}
    start = time.perf_counter()
    result = None
    try:
        # Keep the baseline solver call and successful result unchanged. The
        # external task deadline also bounds deferred fits and rewrite rescue.
        with until(DEADLINE - 0.15):
            result = search.solve(task)
    except DeadlineReached:
        pass
    phases["python"] = time.perf_counter() - start
    if (
        result
        and result.trace
        and result.trace.get("metadata", {}).get("solutions", 0) > 0
    ):
        trace = validate_trace(result.trace)
        trace["solver"] = "native-s1"
        trace["metadata"].update(
            {
                "source": "python",
                "top1_origin": "python",
                "arcsearch": {},
                "cpp_solutions": 0,
                "verified": trace["metadata"]["solutions"],
                "seeds": 0,
                "prefixes_tried": 0,
                "solutions_by_origin": origins,
                "phase_seconds": phases,
            }
        )
        write_result(request, output_path, trace_path, result.predictions, trace)
        return

    native = {"solutions": [], "stats": {}}
    native_error = None
    seeds, prefixes, solutions = [], [], []
    solution_origins = {}
    prefixes_tried = 0
    bg = background.task_background(
        [e.input for e in task.train] + [e.output for e in task.train]
    )
    with tempfile.TemporaryDirectory(
        prefix="arcsearch-", dir=ROOT / "native" / "bin"
    ) as tmp:
        tmp = Path(tmp)
        start = time.perf_counter()
        try:
            with until(min(DEADLINE - 0.15, start + 1.5)), background.task_context(bg):
                ported = json.loads(
                    subprocess.check_output(
                        [str(ROOT / "native" / "bin" / "arcsearch"), "--list-ported"],
                        text=True,
                        timeout=max(
                            0.01, min(1.5, DEADLINE - time.perf_counter() - 0.15)
                        ),
                    )
                )
                make_seeds(task, set(ported), seeds)
        except (DeadlineReached, subprocess.SubprocessError, OSError, ValueError):
            pass
        phases["seeds"] = time.perf_counter() - start
        budget = DEADLINE - time.perf_counter() - 4.0
        if budget >= 1.0:
            start = time.perf_counter()
            path, seed_path, prefix_path = (
                tmp / "solutions.json",
                tmp / "seeds.json",
                tmp / "prefixes.json",
            )
            seed_path.write_text(json.dumps(seeds))
            try:
                completed = subprocess.run(
                    [
                        str(ROOT / "native" / "bin" / "arcsearch"),
                        "--request",
                        str(Path(request_path).resolve()),
                        "--budget",
                        str(budget),
                        "--seeds",
                        str(seed_path),
                        "--dump-prefixes",
                        "20",
                        "--prefix-out",
                        str(prefix_path),
                        "--out",
                        str(path),
                    ],
                    timeout=max(0.01, DEADLINE - time.perf_counter() - 0.8),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                native = json.loads(path.read_text())
                prefixes = json.loads(prefix_path.read_text())
                if completed.stderr:
                    native_error = completed.stderr.strip()
            except (subprocess.SubprocessError, OSError, ValueError) as exc:
                native_error = str(exc)
            phases["cpp"] = time.perf_counter() - start

        train_cells = sum(len(e.output) * len(e.output[0]) for e in task.train)
        gated = [0]

        def verify(raw_program, origin):
            try:
                with until(DEADLINE - 0.15), background.task_context(bg):
                    program = from_json(json.dumps(raw_program))
                    if len(program) > 4 and program[-1][0] in PENALIZED:
                        return
                    if unsupported(program, train_cells):
                        gated[0] += 1
                        return
                    if not all(run(program, e.input) == e.output for e in task.train):
                        return
                    tests = [run(program, grid) for grid in task.test]
                    order = len(solutions)
                    solutions.append((cost(program), order, program, tests))
                    solution_origins[order] = origin
                    origins[origin] += 1
            except (*ERRORS, DeadlineReached):
                return

        start = time.perf_counter()
        for solution in native["solutions"]:
            if time.perf_counter() >= DEADLINE - 0.15:
                break
            verify(solution["program"], solution.get("origin", "cpp"))
        phases["verify"] += time.perf_counter() - start

        start = time.perf_counter()
        verify_before = phases["verify"]
        if not solutions:
            for prefix in prefixes:
                if time.perf_counter() >= DEADLINE - 0.8:
                    break
                prefixes_tried += 1
                try:
                    with until(DEADLINE - 0.8), background.task_context(bg):
                        program = from_json(json.dumps(prefix["program"]))
                        sub = SolverTask(
                            task.task_id,
                            tuple(
                                Example(run(program, e.input), e.output)
                                for e in task.train
                            ),
                            tuple(run(program, grid) for grid in task.test),
                        )
                    left = DEADLINE - 0.8 - time.perf_counter()
                    with until(min(DEADLINE - 0.8, time.perf_counter() + 0.4)):
                        finished = search.search(
                            sub, max_depth=1, budget=min(0.4, left)
                        )
                    for _value, _order, suffix, _tests in finished.solutions:
                        before = time.perf_counter()
                        verify([*program, *suffix], "prefix_py")
                        phases["verify"] += time.perf_counter() - before
                except (*ERRORS, DeadlineReached):
                    continue
        phases["prefix_py"] = (
            time.perf_counter() - start - (phases["verify"] - verify_before)
        )

    chosen = vote.choose(
        solutions, penalized=PENALIZED, shape_hint=vote.predict_hint(task)
    )
    recorder = TraceRecorder(solver="native-s1")
    ids = []
    for solution in chosen.ranked[:30]:
        value, order, program, _tests = solution
        ids.append(
            recorder.attempt(
                f"program of cost {value:.1f}",
                kind="program",
                program=to_json(program),
                train_results=[True] * len(task.train),
                data={
                    "cost": value,
                    "votes": chosen.votes_of(solution),
                    "origin": solution_origins[order],
                },
            )
        )
    recorder.select(ids[0] if ids else None)
    recorder.reasoning = (
        "Python-verified program selected by the standard vote."
        if ids
        else "No verified program; echo test inputs."
    )
    recorder.metadata = {
        "source": "native",
        "top1_origin": solution_origins[chosen.ranked[0][1]] if ids else None,
        "arcsearch": native["stats"],
        "cpp_solutions": len(native["solutions"]),
        "verified": len(solutions),
        "support_gated": gated[0],
        "solutions": len(chosen.ranked),
        "second": chosen.second,
        "shape_hint_applied": chosen.hint_applied,
        "seeds": len(seeds),
        "prefixes_tried": prefixes_tried,
        "solutions_by_origin": origins,
        "phase_seconds": phases,
    }
    if native_error:
        recorder.metadata["native_error"] = native_error
    predictions = chosen.ranked[0][3] if chosen.ranked else list(task.test)
    write_result(request, output_path, trace_path, predictions, recorder.to_dict())


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    main()
