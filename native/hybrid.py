"""Run the unchanged Python solver, then verify and vote on native programs."""

import time

T0 = time.perf_counter()

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from arcagi.dsl import background
from arcagi.dsl.program import cost, from_json, run, to_json
from arcagi.solvers import search, vote
from arcagi.solvers.trace import TraceRecorder, validate_trace
from arcagi.tasks.validation import task_from_dict

ROOT = Path(__file__).resolve().parent.parent


def write_result(request, output, trace_path, predictions, trace):
    """Write the external response and the standard trace dictionary."""
    Path(output).write_text(json.dumps({request["task_id"]: predictions}) + "\n")
    if trace_path:
        trace["elapsed_seconds"] = time.perf_counter() - T0
        Path(trace_path).write_text(json.dumps(validate_trace(trace)) + "\n")


def main():
    request_path, output_path = sys.argv[1:3]
    request = json.loads(Path(request_path).read_text())
    trace_path = sys.argv[3] if len(sys.argv) > 3 else request.get("trace_path")
    task = task_from_dict(request["task"], task_id=request["task_id"]).to_solver_task()
    result = search.solve(task)
    if result.trace and result.trace.get("metadata", {}).get("solutions", 0) > 0:
        trace = validate_trace(result.trace)
        trace["solver"] = "native-s1"
        trace["metadata"].update({
            "source": "python", "arcsearch": {}, "cpp_solutions": 0, "verified": 0,
        })
        write_result(request, output_path, trace_path, result.predictions, trace)
        return

    native = {"solutions": [], "stats": {}}
    native_error = None
    remaining = 19.0 - (time.perf_counter() - T0)
    if remaining > 1.0:
        with tempfile.TemporaryDirectory(prefix="arcsearch-", dir=ROOT / "native" / "bin") as tmp:
            path = Path(tmp) / "solutions.json"
            try:
                completed = subprocess.run([
                    str(ROOT / "native" / "bin" / "arcsearch"),
                    "--request", str(Path(request_path).resolve()),
                    "--budget", str(remaining - 0.5), "--out", str(path),
                ], timeout=remaining + 2, check=True, capture_output=True, text=True)
                native = json.loads(path.read_text())
                if completed.stderr:
                    native_error = completed.stderr.strip()
            except (subprocess.SubprocessError, OSError, ValueError) as exc:
                native_error = str(exc)

    solutions = []
    grids = [e.input for e in task.train] + [e.output for e in task.train]
    with background.task_context(background.task_background(grids)):
        for order, solution in enumerate(native["solutions"]):
            try:
                program = from_json(json.dumps(solution["program"]))
                if not all(run(program, e.input) == e.output for e in task.train):
                    continue
                tests = [run(program, grid) for grid in task.test]
                solutions.append((cost(program), order, program, tests))
            except Exception:
                continue
    chosen = vote.choose(solutions, penalized=search.PENALIZED, shape_hint=vote.predict_hint(task))
    recorder = TraceRecorder(solver="native-s1")
    ids = []
    for solution in chosen.ranked[:30]:
        value, _order, program, _tests = solution
        ids.append(recorder.attempt(
            f"program of cost {value:.1f}", kind="program", program=to_json(program),
            train_results=[True] * len(task.train),
            data={"cost": value, "votes": chosen.votes_of(solution)},
        ))
    recorder.select(ids[0] if ids else None)
    recorder.reasoning = (
        "Python-verified native program selected by the standard vote."
        if ids else "No verified program; echo test inputs."
    )
    recorder.metadata = {
        "source": "native", "arcsearch": native["stats"],
        "cpp_solutions": len(native["solutions"]), "verified": len(solutions),
        "solutions": len(chosen.ranked), "second": chosen.second,
        "shape_hint_applied": chosen.hint_applied,
    }
    if native_error:
        recorder.metadata["native_error"] = native_error
    predictions = chosen.ranked[0][3] if chosen.ranked else list(task.test)
    write_result(request, output_path, trace_path, predictions, recorder.to_dict())


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    main()
