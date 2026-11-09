"""GPU seed layer ``gpuseed`` (reports/seed-gpu-1110/): each GPU-enumerated layer
must match the CPU seed Enumerator (same fingerprint set of new entries, same
node count) on every task.

Skipped unless ``native/bin/gpuseed`` is built (``make -C native gpuseed``) and
a CUDA device is visible.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "gpuseed"
if not os.access(BIN, os.X_OK) or shutil.which("nvidia-smi") is None:
    pytest.skip(f"{BIN} not built or no CUDA device", allow_module_level=True)


def test_gpu_layers_match_cpu_enumerator() -> None:
    out = subprocess.run(
        [str(BIN), "--data", str(ROOT / "data/ARC-AGI/data/training"), "--limit", "20",
         "--max-layer", "4", "--reps-cpu", "1", "--reps-gpu", "1", "--threads", "2"],
        capture_output=True, text=True, timeout=300, check=True,
    ).stdout
    rows = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    layers = [r for r in rows if "tasks_compared" in r]
    assert [r["layer"] for r in layers] == [2, 3, 4]
    assert not [r for r in rows if "task" in r]  # no per-task mismatch / unsupported lines
    for r in layers:
        assert r["tasks_compared"] == 20 and r["skipped"] == 0
        assert r["set_mismatch"] == 0 and r["node_mismatch"] == 0
        assert r["cpu_nodes"] == r["gpu_nodes"] > 0
        assert r["cpu_new"] == r["gpu_new"] > 0
