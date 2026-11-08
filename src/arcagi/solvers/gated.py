"""Gated entry: run the r06 hybrid solver, then pass its candidates through ``guard``.

The hybrid entry (``native/bin/solve``: Python search, native C++ fallback,
Python re-verification) is called unchanged; its trace lists up to 30
train-consistent programs (``kind == "program"``) in its own rank order. This
module re-runs those programs on the test inputs (and, for training tasks with
``data_synth`` pairs, on ``SYNTH_PAIRS`` synthetic pairs), builds
``guard.Candidate`` objects and lets ``guard.judge`` pick or abstain.

Entry points:

* external: ``python -m arcagi.solvers.gated {input} {output} {trace}``
  (same protocol as ``native/bin/solve``);
* plugin: ``arcagi.solvers.gated:solve`` (Python search only, no native step).
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from contextlib import contextmanager
from pathlib import Path

from arcagi.dsl import background as bgc
from arcagi.dsl import learners
from arcagi.dsl.program import from_json, run, run_step
from arcagi.tasks import Grid, SolverTask
from arcagi.tasks.validation import task_from_dict

from . import guard
from .trace import SolverResult, validate_trace

ROOT = Path(__file__).resolve().parents[3]
SYNTH_ROOT = Path(os.environ.get("ARCAGI_SYNTH", ROOT / "data_synth"))
SYNTH_PAIRS = 4
PROGRAM_SECONDS = 2.0
ERRORS = (
    ValueError,
    IndexError,
    KeyError,
    TypeError,
    ZeroDivisionError,
    RecursionError,
)


class _TimeoutError(Exception):
    pass


@contextmanager
def _limit(seconds: float):
    """Wall-clock limit (main thread only; elsewhere unlimited)."""
    try:
        previous = signal.signal(signal.SIGALRM, _raise_timeout)
    except ValueError:
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _raise_timeout(_signum, _frame):
    raise _TimeoutError


def synth_pairs(task_id: str, root: Path | None = None) -> list[tuple[Grid, Grid]]:
    """The first ``SYNTH_PAIRS`` synthetic pairs of a training task ([] if none)."""
    root = Path(root) if root is not None else SYNTH_ROOT
    manifest = root / "manifest.json"
    path = root / "training" / f"{task_id}.json"
    if not (manifest.is_file() and path.is_file()):
        return []
    entry = json.loads(manifest.read_text())["tasks"].get(task_id)
    if not entry:
        return []
    pairs = json.loads(path.read_text())["train"][entry["n_original"] :]
    return [(_grid(p["input"]), _grid(p["output"])) for p in pairs[:SYNTH_PAIRS]]


def _grid(rows) -> Grid:
    return tuple(tuple(row) for row in rows)


def _run_all(program, grids: Iterable[Grid], bg: int | None) -> list[Grid] | None:
    try:
        with _limit(PROGRAM_SECONDS), bgc.task_context(bg):
            return [run(program, grid) for grid in grids]
    except (*ERRORS, _TimeoutError):
        return None


def _local_keys(grid: Grid, step) -> dict:
    steps = learners._NEIGHBORS[step[1]]
    h, w = len(grid), len(grid[0])
    return {
        (y, x): learners._key(grid, y, x, steps) for y in range(h) for x in range(w)
    }


def _vrule_keys(grid: Grid, step) -> dict:
    from arcagi.dsl.ext import prims as ext  # read-only S1 helper

    steps = ext.VRULE_NEIGHBORS[step[1]]
    bg = bgc.of(grid)
    h, w = len(grid), len(grid[0])
    return {
        (y, x): ext._vkey(grid, y, x, steps, bg)[0] for y in range(h) for x in range(w)
    }


# Cell tables, step = (name, features, rows); a row is [*key, value] for one
# changing neighborhood key.
KEYED: dict[str, Callable[[Grid, tuple], dict]] = {
    "local_rule": _local_keys,
    "x_vrule": _vrule_keys,
}


def table_stats(program, train: Sequence[Grid], bg) -> tuple[int, int] | None:
    """``(rows, thin rows)`` summed over cell-table steps, or None if none.

    A row is *thin* when its key changes fewer than ``guard.ROW_SUPPORT``
    train cells (counted on the train states entering that step).
    """
    if not any(step[0] in KEYED for step in program):
        return None
    try:
        with _limit(PROGRAM_SECONDS), bgc.task_context(bg):
            states, rows, thin = list(train), 0, 0
            for step in program:
                after = [run_step(step, s) for s in states]
                keys = KEYED.get(step[0])
                if keys:
                    used: Counter = Counter()
                    for s, t in zip(states, after, strict=True):
                        for (y, x), k in keys(s, step).items():
                            if s[y][x] != t[y][x]:
                                used[k] += 1
                    rows += len(step[2])
                    thin += sum(
                        used[tuple(r[:-1])] < guard.ROW_SUPPORT for r in step[2]
                    )
                states = after
            return rows, thin
    except (*ERRORS, _TimeoutError):
        return None


def evaluate(
    task: SolverTask,
    programs: Sequence[tuple[str, str]],
    synth: Sequence[tuple[Grid, Grid]] = (),
) -> list[guard.Candidate]:
    """Re-run ``(program JSON, origin)`` pairs into guard candidates.

    A program failing train on re-run is dropped (the registry may have moved
    since the trace was written); one that cannot produce test outputs keeps
    ``tests=None``. Synthetic pairs run under their own task background.
    """
    bg = bgc.task_background(
        [e.input for e in task.train] + [e.output for e in task.train]
    )
    synth_bg = (
        bgc.task_background([g for pair in synth for g in pair]) if synth else None
    )
    out = []
    for text, origin in programs:
        try:
            program = from_json(text)
        except (ValueError, TypeError):
            continue
        got = _run_all(program, [e.input for e in task.train], bg)
        if got is None or any(
            a != e.output for a, e in zip(got, task.train, strict=True)
        ):
            continue
        tests = _run_all(program, task.test, bg)
        ok = 0
        if synth:
            res = _run_all(program, [i for i, _o in synth], synth_bg)
            if res is not None:
                ok = sum(a == o for a, (_i, o) in zip(res, synth, strict=True))
        out.append(
            guard.Candidate(
                text,
                tuple(tests) if tests is not None else None,
                origin,
                synth_ok=ok,
                synth_total=len(synth),
                table=table_stats(program, [e.input for e in task.train], bg),
            )
        )
    return out


def trace_programs(trace: dict | None) -> list[tuple[str, str]]:
    """``(program JSON, origin)`` of a trace's program attempts, in rank order."""
    if not trace:
        return []
    source = trace.get("metadata", {}).get("source", "unknown")
    return [
        (a["program"], a.get("data", {}).get("origin", source))
        for a in trace.get("attempts", [])
        if a.get("kind") == "program" and a.get("program")
    ]


def gate(
    task: SolverTask,
    trace: dict | None,
    *,
    gates: Iterable[str] = guard.DEFAULT_GATES,
    synth_root: Path | None = None,
) -> tuple[guard.Verdict, list[guard.Candidate]]:
    synth = synth_pairs(task.task_id, synth_root) if "synth" in set(gates) else []
    cands = evaluate(task, trace_programs(trace), synth)
    train = [(e.input, e.output) for e in task.train]
    return guard.judge(cands, train, task.test, gates=set(gates)), cands


def _annotate(trace: dict, verdict: guard.Verdict) -> dict:
    trace = dict(trace)
    meta = dict(trace.get("metadata", {}))
    meta["guard"] = {
        "abstained": verdict.abstained,
        "reason": verdict.reason,
        "chosen": verdict.chosen.candidate.program if verdict.chosen else None,
        "distrusted": [
            {"program": j.candidate.program, "reasons": j.reasons}
            for j in verdict.ranked
            if not j.trusted
        ][:30],
    }
    trace["metadata"] = meta
    return trace


def solve(task: SolverTask) -> SolverResult:
    """Plugin form: Python search candidates only, then the guard."""
    from . import search

    result = search.solve(task)
    verdict, _ = gate(task, result.trace)
    trace = _annotate(result.trace, verdict) if result.trace else None
    return SolverResult(verdict.predictions, trace)


def main(argv: Sequence[str] | None = None, runner: Callable | None = None) -> int:
    """External form: run ``native/bin/solve`` then gate its trace."""
    argv = list(sys.argv[1:] if argv is None else argv)
    request_path, output_path = argv[:2]
    trace_path = argv[2] if len(argv) > 2 else None
    request = json.loads(Path(request_path).read_text())
    task = task_from_dict(request["task"], task_id=request["task_id"]).to_solver_task()
    with tempfile.TemporaryDirectory(prefix="gated-") as tmp:
        inner_out, inner_trace = Path(tmp) / "out.json", Path(tmp) / "trace.json"
        (runner or _run_hybrid)(request_path, inner_out, inner_trace)
        trace = json.loads(inner_trace.read_text()) if inner_trace.is_file() else None
    verdict, _ = gate(task, trace)
    Path(output_path).write_text(
        json.dumps({request["task_id"]: verdict.predictions}) + "\n"
    )
    if trace_path and trace:
        Path(trace_path).write_text(
            json.dumps(validate_trace(_annotate(trace, verdict))) + "\n"
        )
    return 0


def _run_hybrid(request_path, out_path, trace_path) -> None:
    subprocess.run(
        [
            str(ROOT / "native" / "bin" / "solve"),
            str(request_path),
            str(out_path),
            str(trace_path),
        ],
        check=False,
        timeout=60,
    )


if __name__ == "__main__":
    raise SystemExit(main())
