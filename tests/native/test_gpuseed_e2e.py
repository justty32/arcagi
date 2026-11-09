"""GPU seed layer inside the real seed search (N5c, reports/seed-gpu-e2e-1110/).

``native/bin/arcbatch-gpuseed`` must reproduce ``native/bin/arcbatch`` rows
exactly (program, train_ok, test_ok, nodes, nodes_to_first, near; only
seconds and eval_steps may differ), with and without ``--gpu-seed``.
``--gpu-min 1`` forces even tiny layers onto the GPU.

Skipped unless the binary is built (``make -C native gpuseed-e2e``) and a CUDA
device is visible.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcbatch-gpuseed"
REF = ROOT / "native" / "bin" / "arcbatch"
DATA = ROOT / "data" / "ARC-AGI" / "data" / "training"
if not os.access(BIN, os.X_OK) or not os.access(REF, os.X_OK) or shutil.which("nvidia-smi") is None:
    pytest.skip(f"{BIN} not built or no CUDA device", allow_module_level=True)

FIRST = sorted(p.stem for p in DATA.glob("*.json"))
SOLVED = ["1e0a9b12", "2dee498d", "25ff71a9", "3c9b0459"]  # some solved at these budgets


def _run(exe: Path, ids: list[str], budget: int, tmp: Path, extra: list[str] = (), env=None):
    tasks = tmp / "tasks.txt"
    tasks.write_text("\n".join(ids) + "\n")
    cfg = tmp / "configs.jsonl"
    cfg.write_text(json.dumps({"name": "base", "budget": budget, "decomp": True}) + "\n")
    p = subprocess.run(
        [str(exe), "--mode", "seed", "--tasks", str(tasks), "--data-dir", str(DATA),
         "--configs", str(cfg), "--threads", "4", *extra],
        capture_output=True, text=True, timeout=600, check=True,
        env={**os.environ, **(env or {})},
    )
    rows = {}
    for line in p.stdout.splitlines():
        r = json.loads(line)
        if r.get("summary"):
            continue
        r.pop("seconds"), r.pop("eval_steps")
        rows[r["task_id"]] = r
    assert sorted(rows) == sorted(ids)
    return rows, p.stderr


def test_cpu_mode_matches_arcbatch(tmp_path: Path) -> None:
    ids = FIRST[:8]
    ref, _ = _run(REF, ids, 100000, tmp_path)
    got, _ = _run(BIN, ids, 100000, tmp_path)
    assert got == ref


def test_gpu_forced_matches_arcbatch(tmp_path: Path) -> None:
    ids = SOLVED + FIRST[:6]
    ref, _ = _run(REF, ids, 200000, tmp_path)
    got, err = _run(BIN, ids, 200000, tmp_path, ["--gpu-seed", "--gpu-min", "1", "--seed-prof"])
    assert got == ref
    assert sum(r["test_ok"] for r in ref.values()) >= 3
    prof = [json.loads(x) for x in err.splitlines() if x.startswith("{")]
    assert len(prof) == 1 and prof[0]["gpu"] is True
    assert prof[0]["layers_gpu"] > 0 and prof[0]["gpu_cands"] > 0 and prof[0]["fallbacks"] == 0


def test_gpu_verify(tmp_path: Path) -> None:
    ids = SOLVED[:3]
    ref, _ = _run(REF, ids, 200000, tmp_path)
    got, err = _run(BIN, ids, 200000, tmp_path, ["--gpu-seed", "--gpu-min", "1", "--seed-prof"],
                    env={"ARC_GPUSEED_VERIFY": "1"})
    assert got == ref
    prof = json.loads([x for x in err.splitlines() if x.startswith("{")][0])
    assert prof["verified"] > 0


def test_seed_prof_cpu_mode(tmp_path: Path) -> None:
    _, err = _run(BIN, FIRST[:2], 20000, tmp_path, ["--seed-prof"])
    prof = [json.loads(x) for x in err.splitlines() if x.startswith("{")]
    assert len(prof) == 1
    p = prof[0]
    assert p["seed_prof"] is True and p["gpu"] is False and p["layers_gpu"] == 0
    assert p["run_s"] > 0 and 0 < p["nodes_sup"] <= p["nodes_all"]
