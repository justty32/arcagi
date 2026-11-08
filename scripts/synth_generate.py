"""Build the synthetic scoring set: RE-ARC variants of every training task.

Run (from the repo root)::

    systemd-run --user --scope -p MemoryMax=8G \\
        nice -n 19 .venv/bin/python scripts/synth_generate.py --workers 6

Output ``data_synth/training/<task_id>.json`` in the official ARC-AGI-1 format:
``train`` = the original train pairs followed by >= ``--min-pairs`` synthetic
pairs, ``test`` = the original test pairs. ``data_synth/manifest.json`` records
per task how many leading train pairs are original (``n_original``), the seed
and the file hash, so consumers can slice ``train[n_original:]`` for synthetic
pairs only. Generator code (``--data-root data_synth``) reads the directory as
is. Only the training split is touched: RE-ARC has no evaluation rules.

Pairs come from ``arcagi.generation.worker`` (unmodified RE-ARC generators and
verifiers, one process per task, ``PYTHONHASHSEED=0``). The per-task seed is
``sha256("<seed>:<task_id>:<attempt>")``; attempt 0 asks for ``--pairs``,
later attempts fall back to ``--min-pairs``. Same seed, Python version and
vendored sources give byte-identical files (``--check N`` re-generates N tasks
and compares hashes).
"""

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arcagi.generation import list_generators  # noqa: E402
from arcagi.generation.sources import verify_sources  # noqa: E402
from arcagi.tasks import task_from_dict  # noqa: E402

TRAINING = ROOT / "data" / "ARC-AGI" / "data" / "training"
SCHEMA = "arcagi-synth/1"
MAX_WORKERS = 6
ATTEMPTS = 3


def derived_seed(seed: int, task_id: str, attempt: int) -> int:
    digest = hashlib.sha256(f"{seed}:{task_id}:{attempt}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _worker_env() -> dict[str, str]:
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")])
    )
    return env


def synth_pairs(task_id: str, args: argparse.Namespace) -> tuple[list, int, int]:
    """Synthetic pairs for one rule: (pairs, seed used, attempt index)."""
    errors = []
    for attempt in range(ATTEMPTS):
        want = args.pairs if attempt == 0 else args.min_pairs
        seed = derived_seed(args.seed, task_id, attempt)
        request = {
            "task_id": task_id,
            "seed": seed,
            "train_examples": want - 1,
            "test_examples": 1,
            "difficulty_lower": args.difficulty_lower,
            "difficulty_upper": args.difficulty_upper,
        }
        try:
            result = subprocess.run(
                [sys.executable, "-m", "arcagi.generation.worker"],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                env=_worker_env(),
                timeout=args.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"attempt {attempt}: timeout {args.timeout}s")
            continue
        if result.returncode:
            tail = result.stderr.strip().splitlines()[-1:] or ["?"]
            errors.append(f"attempt {attempt}: {tail[0]}")
            continue
        task = json.loads(result.stdout)
        return task["train"] + task["test"], seed, attempt
    raise RuntimeError("; ".join(errors))


def build_task(task_id: str, args: argparse.Namespace, out: Path) -> dict:
    original = json.loads((TRAINING / f"{task_id}.json").read_text())
    pairs, seed, attempt = synth_pairs(task_id, args)
    task = {"train": original["train"] + pairs, "test": original["test"]}
    task_from_dict(task, task_id=task_id, require_test_outputs=True)
    payload = (json.dumps(task, separators=(",", ":")) + "\n").encode()
    (out / f"{task_id}.json").write_bytes(payload)
    return {
        "file": f"training/{task_id}.json",
        "n_original": len(original["train"]),
        "n_synth": len(pairs),
        "seed": seed,
        "attempt": attempt,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def generate(args: argparse.Namespace, out_root: Path, ids: list[str]) -> dict:
    out = out_root / "training"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": SCHEMA,
        "source": verify_sources(),
        "python": platform.python_version(),
        "hash_seed": "0",
        "seed": args.seed,
        "pairs": args.pairs,
        "min_pairs": args.min_pairs,
        "difficulty": [args.difficulty_lower, args.difficulty_upper],
        "split": "training",
        "layout": "train = original train pairs + synthetic; test = original test",
        "tasks": {},
        "failed": {},
    }
    start = time.perf_counter()
    workers = min(args.workers, MAX_WORKERS)
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(build_task, t, args, out): t for t in ids}
        for done, future in enumerate(as_completed(futures), 1):
            task_id = futures[future]
            try:
                manifest["tasks"][task_id] = future.result()
            except Exception as error:  # noqa: BLE001 - record and continue
                manifest["failed"][task_id] = str(error)[:500]
            if done % 50 == 0:
                print(f"{done}/{len(ids)} done", file=sys.stderr, flush=True)
    manifest["tasks"] = dict(sorted(manifest["tasks"].items()))
    manifest["failed"] = dict(sorted(manifest["failed"].items()))
    manifest["seconds"] = round(time.perf_counter() - start, 1)
    n = [e["n_synth"] for e in manifest["tasks"].values()]
    manifest["summary"] = {
        "tasks": len(n),
        "failed": len(manifest["failed"]),
        "synth_pairs": sum(n),
        "min_synth": min(n, default=0),
    }
    return manifest


def check(args: argparse.Namespace, out_root: Path, count: int) -> int:
    """Re-generate ``count`` random tasks into a temp dir and compare hashes."""
    manifest = json.loads((out_root / "manifest.json").read_text())
    ids = sorted(manifest["tasks"])
    sample = random.Random(args.seed).sample(ids, min(count, len(ids)))
    with tempfile.TemporaryDirectory() as tmp:
        fresh = generate(args, Path(tmp), sample)
    bad = [
        t
        for t in sample
        if fresh["tasks"].get(t, {}).get("sha256") != manifest["tasks"][t]["sha256"]
    ]
    print(json.dumps({"checked": len(sample), "mismatch": bad}))
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "data_synth")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pairs", type=int, default=24)
    parser.add_argument("--min-pairs", type=int, default=20)
    parser.add_argument("--difficulty-lower", type=float, default=0.0)
    parser.add_argument("--difficulty-upper", type=float, default=0.5)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--tasks", nargs="*", help="subset of training ids")
    parser.add_argument("--check", type=int, metavar="N", help="verify N tasks")
    args = parser.parse_args(argv)
    if not 2 <= args.min_pairs <= args.pairs:
        parser.error("need 2 <= --min-pairs <= --pairs")
    out_root = args.out.resolve()
    if args.check:
        return check(args, out_root, args.check)
    training = {p.stem for p in TRAINING.glob("*.json")}
    ids = sorted(set(args.tasks or list_generators()) & training)
    if (out_root / "manifest.json").exists():
        parser.error(f"{out_root} already holds a set; remove it or pick --out")
    manifest = generate(args, out_root, ids)
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps(manifest["summary"] | {"seconds": manifest["seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
