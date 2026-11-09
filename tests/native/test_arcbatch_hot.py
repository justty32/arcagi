"""Isolated CPU hot paths must preserve all seed task fields except seconds."""

import json
import os
import subprocess
from pathlib import Path

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
    configs.write_text(
        json.dumps({"name": "hot", "budget": 30000, "decomp": decomp}) + "\n"
    )
    results = []
    for name in NAMES:
        completed = subprocess.run(
            [
                str(BIN / name),
                "--mode",
                "seed",
                "--tasks",
                str(tasks),
                "--configs",
                str(configs),
                "--threads",
                "2",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=55,
        )
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        results.append(
            {
                row["task_id"]: {k: v for k, v in row.items() if k != "seconds"}
                for row in rows
                if not row.get("summary")
            }
        )
    assert len(results[0]) == 4
    assert results[1] == results[0]
    assert results[2] == results[0]


@pytest.mark.parametrize(
    "candidate", ["arcbatch-hot-c", "arcbatch-hot-d", "arcbatch-hot-e"]
)
@pytest.mark.parametrize("decomp", [False, True])
def test_new_hot_rows_match_reference(tmp_path, decomp, candidate):
    if not os.access(BIN / candidate, os.X_OK):
        target = "hot-e" if candidate == "arcbatch-hot-e" else "hot2"
        pytest.skip(f"run make -C native {target}")
    tasks = tmp_path / "tasks.txt"
    tasks.write_text("007bbfb7\n025d127b\n1e0a9b12\n68b16354\n")
    configs = tmp_path / "configs.jsonl"
    configs.write_text(
        json.dumps({"name": "hot2", "budget": 30000, "decomp": decomp}) + "\n"
    )
    results = []
    for name in ("arcbatch", candidate):
        completed = subprocess.run(
            [
                str(BIN / name),
                "--mode",
                "seed",
                "--tasks",
                str(tasks),
                "--configs",
                str(configs),
                "--threads",
                "2",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=55,
        )
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        results.append(
            {
                row["task_id"]: {k: v for k, v in row.items() if k != "seconds"}
                for row in rows
                if not row.get("summary")
            }
        )
    assert len(results[0]) == 4
    assert results[1] == results[0]


@pytest.mark.skipif(
    not all(
        (ROOT / f"native/hot/{obj}/seed_value.o").exists()
        for obj in ("obj-ab", "obj-c", "obj-d")
    ),
    reason="run make -C native hot hot2",
)
@pytest.mark.parametrize("candidate", ["obj-c", "obj-d"])
def test_hot_interpreter_budgets_and_store(tmp_path, candidate):
    results = []
    for obj in ("obj-ab", candidate):
        executable = tmp_path / obj
        subprocess.run(
            [
                "g++",
                "-std=c++20",
                "-O2",
                "-pthread",
                "-Inative/src",
                "tests/native/hot_c_check.cpp",
                f"native/hot/{obj}/seed_value.o",
                "-o",
                str(executable),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        result = subprocess.run(
            [str(executable)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
            env={**os.environ, "ARC_HOT_STATS": "1"},
        )
        results.append(result.stdout)
        if obj == "obj-c":
            counters = [
                json.loads(line)
                for line in result.stderr.splitlines()
                if line.startswith("{")
            ]
            higher = next(row for row in counters if row.get("hot_higher_cache"))
            assert higher["hits"] > 0
            assert higher["budget_fallbacks"] > 0
            assert higher["growing_inserts"] > 0
    assert results[1] == results[0]
    assert results[0].endswith("higher-order invariants: PASS\n")


@pytest.mark.skipif(
    not all(
        (ROOT / f"native/hot/{obj}/seed_value.o").exists()
        for obj in ("obj-ab", "obj-e")
    ),
    reason="run make -C native hot hot-e",
)
def test_hot_e_scalar_batches_and_store(tmp_path):
    results = []
    for obj in ("obj-ab", "obj-e"):
        executable = tmp_path / obj
        subprocess.run(
            [
                "g++",
                "-std=c++20",
                "-O2",
                "-pthread",
                "-Inative/src",
                "-Inative/hot",
                "tests/native/hot_e_check.cpp",
                f"native/hot/{obj}/seed_value.o",
                "-o",
                str(executable),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        result = subprocess.run(
            [str(executable)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        results.append(result.stdout)
    assert results[1] == results[0]
    assert results[0].endswith("scalar batch invariants: PASS\n")
