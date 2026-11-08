"""Task-level background: majority over all grids, border tie-break, context."""

import pytest

from arcagi.dsl import background as bgc
from arcagi.dsl.objects_props import extract
from arcagi.solvers.search import search
from arcagi.tasks import Example, SolverTask


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


@pytest.fixture(autouse=True)
def _clear():
    bgc.set_task_background(None)
    yield
    bgc.set_task_background(None)


def test_task_background_is_majority_over_all_grids() -> None:
    # Grid A alone is mostly 1, but 5 dominates the task as a whole.
    a = grid("111 115 111")
    b = grid("555 555 555")
    c = grid("555 515 555")
    assert bgc.task_background([a, b, c]) == 5


def test_task_background_tie_goes_to_border_color() -> None:
    # 4 cells of 3 and 4 cells of 7, but 7 owns the border.
    assert bgc.task_background([grid("777 737 737"), grid("3 3 3")]) == 7
    assert bgc.task_background([]) is None


def test_of_uses_context_only_when_set_and_present() -> None:
    mostly_two = grid("22222 20000")  # 0 is 40% of the cells
    assert bgc.of(mostly_two) == 2
    bgc.set_task_background(0)
    assert bgc.current() == 0
    assert bgc.of(mostly_two) == 0
    # A grid where the task color is absent or rare keeps its own background.
    assert bgc.of(grid("44 41")) == 4
    assert bgc.of(grid("11111 11000")) == 1  # 0 covers only 30%

    with pytest.raises(ValueError):
        bgc.set_task_background(12)


def test_extract_follows_context_and_caches_per_background() -> None:
    # A big blue field with a black frame piece: r02 calls blue the background.
    state = grid("0000 0111 0111 0111 0111")
    assert len(extract(state, "4same")) == 1  # the black frame
    with bgc.task_context(0):
        objs = extract(state, "4same")
        assert [o.props["color"] for o in objs] == [1]
        assert objs[0].props["size"] == 12
    assert extract(state, "4same")[0].props["color"] == 0


def test_search_sets_and_clears_context() -> None:
    task = SolverTask(
        task_id="t", train=[Example(grid("12 34"), grid("21 43"))], test=[grid("56 78")]
    )
    bgc.set_task_background(9)
    result = search(task)
    assert result.solutions
    assert bgc.current() == 9  # previous value restored
