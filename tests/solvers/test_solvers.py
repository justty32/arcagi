"""The plugin interface is immutable and cannot accidentally receive labels."""

import sys
from types import ModuleType

import pytest

from arcagi.solvers import load_solver, predict
from arcagi.tasks import SolverTask, Task, task_from_dict


@pytest.fixture
def task() -> Task:
    return task_from_dict(
        {
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [
                {"input": [[3]], "output": [[4]]},
                {"input": [[5]], "output": [[6]]},
            ],
        },
        task_id="demo",
    )


def test_solver_view_contains_no_test_answers(task: Task) -> None:
    def inspect(view: SolverTask) -> list:
        assert view.task_id == "demo"
        assert view.train[0].output == ((2,),)
        assert view.test == (((3,),), ((5,),))
        assert not hasattr(view.test[0], "output")
        assert set(view.__dict__) == {"task_id", "train", "test"}
        return [[[7]], [[8]]]

    assert predict(inspect, task) == (((7,),), ((8,),))
    assert task.test[0].output == ((4,),)


def test_identity_is_only_a_pipeline_smoke_baseline(task: Task) -> None:
    assert predict(load_solver(), task) == (((3,),), ((5,),))


@pytest.mark.parametrize(
    "result",
    [None, "text", [], [[[1]]], [[[1]], [[2]], [[3]]], [[[True]], [[1]]]],
)
def test_invalid_prediction_count_or_grid_rejected(task: Task, result: object) -> None:
    with pytest.raises(ValueError):
        predict(lambda _: result, task)


def test_plugin_import(monkeypatch: pytest.MonkeyPatch, task: Task) -> None:
    module = ModuleType("test_arc_plugin")
    module.solve = lambda view: view.test
    module.not_callable = 1
    monkeypatch.setitem(sys.modules, module.__name__, module)
    assert (
        predict(load_solver("test_arc_plugin:solve"), task)
        == task.to_solver_task().test
    )
    with pytest.raises(TypeError, match="not callable"):
        load_solver("test_arc_plugin:not_callable")
    with pytest.raises(AttributeError):
        load_solver("test_arc_plugin:missing")


@pytest.mark.parametrize("spec", ["", "module", ":solve", "module:", "a:b:c"])
def test_bad_plugin_syntax(spec: str) -> None:
    with pytest.raises(ValueError, match="module:function"):
        load_solver(spec)


def test_solver_exception_is_not_hidden_by_predict(task: Task) -> None:
    def broken(_: SolverTask) -> list:
        raise RuntimeError("solver failure")

    with pytest.raises(RuntimeError, match="solver failure"):
        predict(broken, task)
