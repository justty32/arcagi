"""End-to-end: ``arcsearch --request`` solves small training tasks.

Every returned program must reproduce all train outputs when executed by the
Python reference ``arcagi.dsl.program.run`` (under the task background context,
as the hybrid entry re-verifies them).
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from arcagi.dsl import background as bgc
from arcagi.dsl import program
from arcagi.tasks import load_task

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcsearch"
if not os.access(BIN, os.X_OK):
    pytest.skip(f"{BIN} not built", allow_module_level=True)

TRAINING = ROOT / "data" / "ARC-AGI" / "data" / "training"
BUDGET = 5
MAX_DEPTH = 3
# Tasks with a known one-step D4 solution (rot180 / rot180 / flip_lr / flip_ud).
TASKS = ("3c9b0459", "6150a2bd", "67a3c6ac", "68b16354")


def _request(task_id: str, trace: Path) -> dict[str, object]:
    task = load_task(TRAINING / f"{task_id}.json")
    data = task.to_dict()
    return {
        "schema_version": "arcagi-solver-input/1",
        "task_id": task_id,
        "task": {
            "train": data["train"],
            "test": [{"input": example["input"]} for example in data["test"]],
        },
        "seed": 0,
        "params": {},
        "trace_path": str(trace),
    }


@pytest.mark.parametrize("task_id", TASKS)
def test_arcsearch_solves_simple_task(task_id: str, tmp_path: Path) -> None:
    request, out = tmp_path / "request.json", tmp_path / "out.json"
    request.write_text(json.dumps(_request(task_id, tmp_path / "trace.json")))
    proc = subprocess.run(
        [
            str(BIN),
            "--request",
            str(request),
            "--budget",
            str(BUDGET),
            "--max-depth",
            str(MAX_DEPTH),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=BUDGET * 6,
        cwd=ROOT,
        check=False,
    )
    assert proc.returncode == 0, f"arcsearch failed: {proc.stderr[-2000:]}"
    result = json.loads(out.read_text())
    assert isinstance(result.get("stats"), dict)
    solutions = result.get("solutions")
    assert solutions, f"{task_id}: no solution found"

    task = load_task(TRAINING / f"{task_id}.json")
    grids = [e.input for e in task.train] + [e.output for e in task.train]
    with bgc.task_context(bgc.task_background(grids)):
        for solution in solutions:
            assert isinstance(solution["cost"], int | float)
            prog = program.from_json(json.dumps(solution["program"]))
            for example in task.train:
                assert program.run(prog, example.input) == example.output, (
                    f"{task_id}: {solution['program']} fails a train pair"
                )
