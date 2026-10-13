"""Build separate, reproducible datasets from RE-ARC's training-task rules."""

import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arcagi.generation.sources import repository_root, vendor_directory, verify_sources


def list_generators() -> list[str]:
    """Return the identifiers of all available procedural training rules."""
    verify_sources()
    source = (vendor_directory() / "generators.py").read_text()
    return sorted(re.findall(r"^def generate_([0-9a-f]{8})\(", source, re.MULTILINE))


def _positive_integer(name: str, value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def generate_dataset(
    output_dir: str | Path,
    *,
    task_ids: Sequence[str] | None = None,
    seed: int = 0,
    count: int = 1,
    train_examples: int = 3,
    test_examples: int = 1,
    difficulty_lower: float = 0.0,
    difficulty_upper: float = 1.0,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Write verified synthetic tasks and provenance to a new directory.

    Each task runs in a separate process with a fixed hash seed and timeout.
    Reproducibility is scoped to the recorded Python version and upstream
    revision. Existing directories are rejected to prevent accidental mixing.
    """
    for name, value in (
        ("count", count),
        ("train_examples", train_examples),
        ("test_examples", test_examples),
    ):
        _positive_integer(name, value)
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if not 0 <= difficulty_lower <= difficulty_upper <= 1:
        raise ValueError("difficulty must satisfy 0 <= lower <= upper <= 1")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    available = list_generators()
    selected = available if task_ids is None else sorted(set(task_ids))
    if not selected:
        raise ValueError("Select at least one generator")
    unknown = set(selected) - set(available)
    if unknown:
        raise ValueError(f"Unknown generator IDs: {', '.join(sorted(unknown))}")
    output_dir = Path(output_dir).resolve()
    official = (repository_root() / "data" / "ARC-AGI").resolve()
    if output_dir == official or official in output_dir.parents:
        raise ValueError("Generated tasks must be separate from the official dataset")
    output_dir.mkdir(parents=True, exist_ok=False)
    task_dir = output_dir / "tasks"
    task_dir.mkdir()
    manifest: dict[str, Any] = {
        "schema": "arcagi-generated/1",
        "kind": "synthetic-training-rule-examples",
        "source": verify_sources(),
        "python": platform.python_version(),
        "hash_seed": "0",
        "seed": seed,
        "count_per_rule": count,
        "train_examples": train_examples,
        "test_examples": test_examples,
        "difficulty": [difficulty_lower, difficulty_upper],
        "verified": True,
        "complete": False,
        "tasks": [],
    }
    manifest_path = output_dir / "manifest.json"

    def save_manifest() -> None:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    save_manifest()
    environment = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    source_root = str(Path(__file__).resolve().parents[2])
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [source_root, environment.get("PYTHONPATH")])
    )
    for task_id in selected:
        for index in range(count):
            derived_seed = int.from_bytes(
                hashlib.sha256(f"{seed}:{task_id}:{index}".encode()).digest()[:8], "big"
            )
            request = {
                "task_id": task_id,
                "seed": derived_seed,
                "train_examples": train_examples,
                "test_examples": test_examples,
                "difficulty_lower": difficulty_lower,
                "difficulty_upper": difficulty_upper,
            }
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "arcagi.generation.worker"],
                    input=json.dumps(request),
                    capture_output=True,
                    text=True,
                    env=environment,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise TimeoutError(
                    f"Generator {task_id} exceeded {timeout} seconds"
                ) from error
            if result.returncode:
                raise RuntimeError(
                    f"Generator {task_id} failed: {result.stderr.strip()}"
                )
            task = json.loads(result.stdout)
            from arcagi.tasks import task_from_dict

            task_from_dict(task, task_id=task_id, require_test_outputs=True)
            filename = f"{task_id}_{index:04d}.json"
            payload = (json.dumps(task, separators=(",", ":")) + "\n").encode()
            (task_dir / filename).write_bytes(payload)
            manifest["tasks"].append(
                {
                    "file": "tasks/" + filename,
                    "rule": task_id,
                    "seed": derived_seed,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            save_manifest()
    manifest["complete"] = True
    save_manifest()
    return manifest
