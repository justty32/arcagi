"""Task schema tests include malformed inputs that must fail validation."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from arcagi.tasks import (
    TaskValidationError,
    load_task,
    load_tasks,
    task_from_dict,
    validate_grid,
)


def task_data() -> dict:
    return {
        "train": [{"input": [[1, 0]], "output": [[0, 1]]}],
        "test": [{"input": [[2, 0]], "output": [[0, 2]]}],
    }


@pytest.mark.parametrize(
    "value",
    [
        [],
        [[]],
        [[1], [1, 2]],
        [[-1]],
        [[10]],
        [[True]],
        [[False]],
        [[1.0]],
        [["1"]],
        [[None]],
        [[0] * 31],
        [[0]] * 31,
        "0",
        {"row": [1]},
    ],
)
def test_invalid_grids_are_rejected(value: object) -> None:
    with pytest.raises(TaskValidationError):
        validate_grid(value)


def test_grid_boundaries_and_freezing() -> None:
    source = [[0] * 30 for _ in range(30)]
    source[29][29] = 9
    grid = validate_grid(source)
    source[0][0] = 2
    assert len(grid) == len(grid[0]) == 30
    assert grid[0][0] == 0
    assert grid[29][29] == 9
    assert validate_grid([[9]]) == ((9,),)


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {},
        {"train": [], "test": []},
        {"train": task_data()["train"]},
        {"train": [], "test": task_data()["test"]},
        {"train": task_data()["train"], "test": []},
        {**task_data(), "unexpected": 1},
        {**task_data(), "name": 1},
        {**task_data(), "train": [{"input": [[0]]}]},
        {**task_data(), "test": [{"output": [[0]]}]},
        {**task_data(), "test": [{"input": [[0]], "output": None}]},
        {**task_data(), "test": [{"input": [[0]], "extra": 1}]},
        {**task_data(), "test": [None]},
    ],
)
def test_invalid_tasks_are_rejected(value: object) -> None:
    with pytest.raises(TaskValidationError):
        task_from_dict(value, task_id="broken")


def test_hidden_test_outputs_allowed_only_for_solving() -> None:
    data = task_data()
    del data["test"][0]["output"]
    task = task_from_dict(data, task_id="hidden")
    assert task.test[0].output is None
    assert task.to_dict() == data
    with pytest.raises(TaskValidationError, match="missing output"):
        task_from_dict(data, task_id="hidden", require_test_outputs=True)


def test_metadata_name_never_changes_filename_identity(tmp_path: Path) -> None:
    path = tmp_path / "real-id.json"
    path.write_text(json.dumps({**task_data(), "name": "untrusted-id"}))
    task = load_task(path)
    assert task.task_id == "real-id"
    assert task.to_dict() == task_data()


def test_task_and_examples_are_immutable() -> None:
    task = task_from_dict(task_data(), task_id="immutable")
    with pytest.raises(FrozenInstanceError):
        task.task_id = "changed"
    with pytest.raises(TypeError):
        task.train[0].input[0][0] = 3


def test_loading_sorted_and_roundtrip(tmp_path: Path) -> None:
    for name in ("b", "a"):
        (tmp_path / f"{name}.json").write_text(json.dumps(task_data()))
    (tmp_path / "notes.txt").write_text("not a task")
    tasks = load_tasks(tmp_path, require_test_outputs=True)
    assert [task.task_id for task in tasks] == ["a", "b"]
    assert all(task.to_dict() == task_data() for task in tasks)


def test_empty_or_missing_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(TaskValidationError, match="No task JSON"):
        load_tasks(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_tasks(tmp_path / "absent")


@pytest.mark.parametrize("content", ['{"train":', '{"train": [], "train": []}'])
def test_malformed_json_and_duplicate_keys_include_path(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "broken.json"
    path.write_text(content)
    with pytest.raises(TaskValidationError, match="broken.json"):
        load_task(path)


def test_official_public_corpus_loads_when_checked_out() -> None:
    root = Path(__file__).resolve().parents[2] / "data" / "ARC-AGI" / "data"
    if not (root / "training").is_dir():
        pytest.skip("Official ARC-AGI submodule is not checked out")
    for split in ("training", "evaluation"):
        tasks = load_tasks(root / split, require_test_outputs=True)
        assert len(tasks) == 400
        assert len({task.task_id for task in tasks}) == 400
