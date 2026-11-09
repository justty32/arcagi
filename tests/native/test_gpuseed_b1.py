"""B1: resident pooled GPU context for the seed layer (N5d, reports/seed-gpu-b1-1110/).

``native/bin/arcbatch-gpuseed-b1`` must reproduce ``native/bin/arcbatch`` rows
exactly (program, train_ok, test_ok, nodes, nodes_to_first, near; only seconds
and eval_steps may differ). With ``--gpu-min 0`` every layer goes to the GPU, and
decomposition sub-problems reuse one device context per worker thread.

Skipped unless the binary is built (``make -C native gpuseed-b1``) and a CUDA
device is visible.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcbatch-gpuseed-b1"
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




def _profs(err: str) -> dict:
    out = {}
    for x in err.splitlines():
        if x.startswith("{"):
            j = json.loads(x)
            out["b1" if j.get("b1_prof") else "seed"] = j
    return out


def test_b1_forced_matches_arcbatch(tmp_path: Path) -> None:
    ids = SOLVED + FIRST[:6]
    ref, _ = _run(REF, ids, 200000, tmp_path)
    got, err = _run(BIN, ids, 200000, tmp_path, ["--gpu-seed", "--gpu-min", "0", "--seed-prof"])
    assert got == ref
    p = _profs(err)
    assert p["seed"]["layers_gpu"] > 0 and p["seed"]["fallbacks"] == 0
    b1 = p["b1"]
    # one context per worker thread at most; every other Enumerator reuses one
    assert 1 <= b1["ctx_creates"] <= 4
    assert b1["ctx_creates"] + b1["ctx_reuses"] == p["seed"]["enumerators"] or b1["ctx_reuses"] > 0


def test_b1_verify(tmp_path: Path) -> None:
    ids = SOLVED[:3] + FIRST[:3]
    ref, _ = _run(REF, ids, 200000, tmp_path)
    got, err = _run(BIN, ids, 200000, tmp_path, ["--gpu-seed", "--gpu-min", "0", "--seed-prof"],
                    env={"ARC_GPUSEED_VERIFY": "1"})
    assert got == ref
    assert _profs(err)["seed"]["verified"] > 0


def test_b1_cpu_mode_matches_arcbatch(tmp_path: Path) -> None:
    ids = FIRST[:6]
    ref, _ = _run(REF, ids, 100000, tmp_path)
    got, _ = _run(BIN, ids, 100000, tmp_path)
    assert got == ref
