"""Isolated CPU hot paths must preserve all seed task fields except seconds."""
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native/bin"
NAMES = ("arcbatch", "arcbatch-hot-a", "arcbatch-hot")
pytestmark = pytest.mark.skipif(
    not all(os.access(BIN / name, os.X_OK) for name in NAMES),
    reason="run make -C native hot",
)


@pytest.mark.parametrize("decomp", [False, True])
def test_hot_rows_match_reference(tmp_path, decomp):
    tasks = tmp_path / "tasks.txt"
    tasks.write_text("007bbfb7\n025d127b\n1e0a9b12\n68b16354\n")
    configs = tmp_path / "configs.jsonl"
    configs.write_text(json.dumps({"name": "hot", "budget": 30000, "decomp": decomp}) + "\n")
    results = []
    for name in NAMES:
        completed = subprocess.run(
            [str(BIN / name), "--mode", "seed", "--tasks", str(tasks),
             "--configs", str(configs), "--threads", "2"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=55,
        )
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        results.append({row["task_id"]: {k: v for k, v in row.items() if k != "seconds"}
                        for row in rows if not row.get("summary")})
    assert len(results[0]) == 4
    assert results[1] == results[0]
    assert results[2] == results[0]
