"""CUDA prototype ``gpusearch``: GPU and CPU twin cover the same brute-force
space and must find the same solution set; programs re-run in Python.

Skipped unless ``native/bin/gpusearch`` is built (``make -C native gpu``) and a
CUDA device is visible.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from arcagi.dsl import background as bgc
from arcagi.dsl import program
from arcagi.tasks import load_task

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "gpusearch"
if not os.access(BIN, os.X_OK) or shutil.which("nvidia-smi") is None:
    pytest.skip(f"{BIN} not built or no CUDA device", allow_module_level=True)

TRAINING = ROOT / "data" / "ARC-AGI" / "data" / "training"
# One-step D4, split_overlay + colormap, flip + crop.
TASKS = ("3c9b0459", "3428a4f5", "7468f01a", "68b16354")


@pytest.mark.parametrize("kernel", ["shared", "flat"])
def test_gpu_matches_cpu_and_python(kernel: str, tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    args = [
        str(BIN),
        "--mode",
        "both",
        "--depth",
        "2",
        "--kernel",
        kernel,
        "--threads",
        "2",
        "--samples",
        "10",
        "--out",
        str(out),
    ]
    for task_id in TASKS:
        args += ["--task", str(TRAINING / f"{task_id}.json")]
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=300, cwd=ROOT, check=False
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["task"] for r in records] == list(TASKS)
    for r in records:
        assert r["agree"], f"{r['task']}: GPU and CPU solution sets differ"
        assert r["gpu"]["space"] == r["cpu"]["space"]
        assert "best" in r, f"{r['task']}: no solution"
        task = load_task(TRAINING / f"{r['task']}.json")
        grids = [e.input for e in task.train] + [e.output for e in task.train]
        with bgc.task_context(bgc.task_background(grids)):
            for steps in [r["best"]["program"], *r["samples"]]:
                prog = program.from_json(json.dumps(steps))
                for example in task.train:
                    assert program.run(prog, example.input) == example.output, (
                        r["task"],
                        steps,
                    )
