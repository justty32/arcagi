"""Check procedural generation, provenance, bounds, and failure behavior."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from arcagi.generation import generate_dataset, list_generators
from arcagi.generation.sources import verify_sources
from arcagi.generation.worker import generate_task
from arcagi.tasks import load_tasks


def test_upstream_has_400_rules_and_valid_checksums() -> None:
    assert len(list_generators()) == 400
    assert verify_sources()["license"] == "MIT"


def test_generation_reproduces_verified_schema(tmp_path: Path) -> None:
    options = {"task_ids": ["007bbfb7", "00d62c1b"], "seed": 42}
    first = generate_dataset(tmp_path / "first", **options)
    second = generate_dataset(tmp_path / "second", **options)
    assert first == second
    assert first["complete"] is True
    assert len(first["tasks"]) == 2
    tasks = load_tasks(tmp_path / "first" / "tasks", require_test_outputs=True)
    assert len(tasks) == 2
    for record in first["tasks"]:
        left = tmp_path / "first" / record["file"]
        right = tmp_path / "second" / record["file"]
        assert left.read_bytes() == right.read_bytes()
        content = json.loads(left.read_text())
        assert len(content["train"]) == 3
        assert len(content["test"]) == 1
        inputs = [pair["input"] for pair in content["train"] + content["test"]]
        assert len({json.dumps(grid) for grid in inputs}) == 4


def test_seed_changes_generated_task(tmp_path: Path) -> None:
    first = generate_dataset(tmp_path / "first", task_ids=["007bbfb7"], seed=1)
    second = generate_dataset(tmp_path / "second", task_ids=["007bbfb7"], seed=2)
    assert first["tasks"][0]["sha256"] != second["tasks"][0]["sha256"]


@pytest.mark.parametrize(
    "options",
    [
        {"count": 0},
        {"train_examples": -1},
        {"test_examples": 0},
        {"difficulty_lower": 0.8, "difficulty_upper": 0.2},
        {"difficulty_lower": float("nan")},
        {"timeout": 0},
        {"timeout": float("inf")},
        {"task_ids": ["not-a-rule"]},
        {"task_ids": []},
    ],
)
def test_invalid_parameters_create_no_output(tmp_path: Path, options: dict) -> None:
    destination = tmp_path / "invalid"
    with pytest.raises(ValueError):
        generate_dataset(destination, **options)
    assert not destination.exists()


def test_existing_output_is_not_overwritten(tmp_path: Path) -> None:
    marker = tmp_path / "precious.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        generate_dataset(tmp_path, task_ids=["007bbfb7"])
    assert marker.read_text() == "keep"


def test_timeout_marks_dataset_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("worker", 0.1)

    monkeypatch.setattr("arcagi.generation.dataset.subprocess.run", timeout)
    with pytest.raises(TimeoutError, match="007bbfb7"):
        generate_dataset(tmp_path / "timeout", task_ids=["007bbfb7"])
    manifest = json.loads((tmp_path / "timeout" / "manifest.json").read_text())
    assert manifest["complete"] is False
    assert manifest["tasks"] == []


def test_checksum_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "re-arc"
    directory.mkdir()
    (tmp_path / "re-arc-source.json").write_text(
        json.dumps({"files": {"generators.py": "wrong-checksum"}})
    )
    (directory / "generators.py").write_text("changed upstream")
    monkeypatch.setattr("arcagi.generation.sources.vendor_directory", lambda: directory)
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_sources()


def test_official_dataset_is_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("arcagi.generation.dataset.repository_root", lambda: tmp_path)
    destination = tmp_path / "data" / "ARC-AGI" / "generated"
    with pytest.raises(ValueError, match="separate from the official dataset"):
        generate_dataset(destination, task_ids=["007bbfb7"])
    assert not destination.exists()


def test_failed_verification_has_bounded_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def invalid_generator(lower: float, upper: float) -> dict:
        nonlocal calls
        calls += 1
        return {"input": ((0,),), "output": ((1,),)}

    modules = (
        SimpleNamespace(generate_007bbfb7=invalid_generator),
        SimpleNamespace(verify_007bbfb7=lambda grid: ((2,),)),
        SimpleNamespace(rng=[], is_grid=lambda grid: True),
    )
    monkeypatch.setattr("arcagi.generation.worker.load_upstream", lambda: modules)
    monkeypatch.setattr("arcagi.generation.worker.random.seed", lambda seed: None)
    with pytest.raises(RuntimeError, match="within 400 attempts"):
        generate_task(
            {
                "task_id": "007bbfb7",
                "seed": 0,
                "train_examples": 3,
                "test_examples": 1,
                "difficulty_lower": 0,
                "difficulty_upper": 1,
            }
        )
    assert calls == 400
