"""``arcsearch --batch`` (tasks x configs in one process) and the support gate."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcsearch"
TRAINING = ROOT / "data" / "ARC-AGI" / "data" / "training"
TASKS = ("3c9b0459", "6150a2bd", "67a3c6ac", "68b16354")  # one-step D4 tasks


def _batch(tmp_path, configs, threads=2, extra=()):
    ids = tmp_path / "ids.txt"
    ids.write_text("".join(f"{t}\n" for t in TASKS))
    cfg = tmp_path / "configs.jsonl"
    cfg.write_text("".join(json.dumps(c) + "\n" for c in configs))
    out = subprocess.run(
        [
            str(BIN),
            "--batch",
            "--tasks",
            str(ids),
            "--data-dir",
            str(TRAINING),
            "--configs",
            str(cfg),
            "--threads",
            str(threads),
            *extra,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout
    return [json.loads(line) for line in out.splitlines()]


needs_bin = pytest.mark.skipif(
    not os.access(BIN, os.X_OK), reason="arcsearch not built"
)


@needs_bin
def test_batch_solves_and_summarizes(tmp_path):
    rows = _batch(
        tmp_path,
        [
            {"name": "a", "max_nodes": 20000},
            {"name": "empty", "prims": [], "learners": []},
        ],
    )
    summary = {r["config"]: r for r in rows if r.get("summary")}
    assert summary["a"]["solved"] == len(TASKS)
    assert summary["empty"]["solved"] == 0 and summary["empty"]["nodes"] == 0
    for r in rows:
        if not r.get("summary") and r["config"] == "a":
            assert r["test_correct"] and r["nodes_to_first"] <= r["nodes"]


@needs_bin
def test_batch_is_deterministic_across_threads(tmp_path):
    cfg = [{"max_nodes": 20000}]
    strip = lambda rows: [  # noqa: E731
        {
            k: v
            for k, v in r.items()
            if k not in ("seconds", "task_seconds", "wall_seconds", "threads")
        }
        for r in rows
    ]
    assert strip(_batch(tmp_path, cfg, threads=1)) == strip(
        _batch(tmp_path, cfg, threads=3)
    )


@needs_bin
def test_batch_macro_and_cache(tmp_path):
    cfg = [{"prims": [], "learners": [], "macros": {"m_twice": [["rot90"], ["rot90"]]}}]
    cache = tmp_path / "cache"
    first = _batch(tmp_path, cfg, extra=("--cache", str(cache)))
    second = _batch(tmp_path, cfg, extra=("--cache", str(cache)))
    solved = [r for r in first if not r.get("summary") and r["test_correct"]]
    assert any(r["program"] == [["m_twice"]] for r in solved)
    assert second[-1]["cache_hits"] == len(TASKS)
    assert [r for r in second if not r.get("summary")] == [
        r for r in first if not r.get("summary")
    ]


def test_hybrid_support_gate():
    spec = importlib.util.spec_from_file_location(
        "hybrid", ROOT / "native" / "hybrid.py"
    )
    hybrid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hybrid)
    table = [["local_rule", "n4", [[0] * 6] * 10]]
    assert not hybrid.unsupported(table, 40)  # 4 cells per row, table alone
    assert hybrid.unsupported(table, 39)
    deep = [["flip_lr"], *table]
    assert hybrid.unsupported(deep, 150)  # 15 < 16 after another step
    assert not hybrid.unsupported(deep, 160)
    assert not hybrid.unsupported([["flip_lr"], ["colormap", [[1, 2]]]], 1)
