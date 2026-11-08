"""Separator-grid cell primitives on synthetic boards."""

import pytest

from arcagi.dsl.cells import CELLS, cells, split
from arcagi.dsl.primitives import MARK

# Two 2x2 cells split by a column of 5.
PAIR = ((1, 0, 5, 1, 1), (0, 0, 5, 0, 1))
# 2x2 layout of 2x2 cells with an outer frame of 8.
F = 8
QUAD = (
    (F, F, F, F, F, F, F),
    (F, 1, 0, F, 0, 0, F),
    (F, 0, 0, F, 0, 0, F),
    (F, F, F, F, F, F, F),
    (F, 2, 2, F, 3, 0, F),
    (F, 2, 2, F, 0, 3, F),
    (F, F, F, F, F, F, F),
)


def test_split_finds_equal_cells_and_frame() -> None:
    assert split(PAIR) == (5, ((0, 2),), ((0, 2), (3, 2)))
    assert len(cells(QUAD)) == 4
    assert cells(QUAD)[2] == ((2, 2), (2, 2))


def test_no_grid_means_no_candidates() -> None:
    plain = ((1, 2, 0), (0, 3, 0), (4, 0, 0))
    uneven = ((1, 5, 0, 0), (0, 5, 0, 1))
    assert split(plain) is None and split(uneven) is None
    for prim in CELLS.values():
        assert list(prim.candidates([plain], [plain])) == []
        assert list(prim.candidates([uneven], [((1,),)])) == []
    with pytest.raises(ValueError):
        CELLS["pick_cell"].apply(plain, "unique")


def test_pick_cell_selectors() -> None:
    pick = CELLS["pick_cell"]
    assert pick.apply(QUAD, "most_pixels") == ((2, 2), (2, 2))
    assert pick.apply(QUAD, "least_pixels") == ((0, 0), (0, 0))
    assert pick.apply(QUAD, "has_color", 3) == ((3, 0), (0, 3))
    with pytest.raises(ValueError):
        pick.apply(QUAD, "most_colors")  # all cells have one color: ambiguous
    params = list(pick.candidates([QUAD], [((0, 0), (0, 0))]))
    assert ("unique",) in params
    assert {("has_color", c) for c in (1, 2, 3)} <= set(params)
    assert list(pick.candidates([QUAD], [((0,),)])) == []


def test_overlay_cells_marks_result() -> None:
    over = CELLS["overlay_cells"]
    assert over.apply(PAIR, "and") == ((MARK, 0), (0, 0))
    assert over.apply(PAIR, "xor") == ((0, MARK), (0, MARK))
    assert over.apply(PAIR, "nor") == ((0, 0), (MARK, 0))
    params = list(over.candidates([PAIR], [((0, 0), (0, 0))]))
    assert ("and",) in params and ("stack",) in params
    two = ((1, 0, 5, 2, 2), (0, 0, 5, 0, 2))
    assert over.apply(two, "stack") == ((1, 2), (0, 2))
    assert over.apply(two, "stack_rev") == ((2, 2), (0, 2))


def test_cells_to_pixels_and_fill_cells() -> None:
    to_px = CELLS["cells_to_pixels"]
    assert to_px.apply(QUAD, "majority") == ((1, 0), (2, 3))
    assert to_px.apply(QUAD, "any") == ((MARK, 0), (MARK, MARK))
    assert to_px.apply(QUAD, "uniform") == ((0, 0), (2, 0))
    assert to_px.apply(QUAD, "max_pixels") == ((0, 0), (MARK, 0))
    assert ("majority",) in list(to_px.candidates([QUAD], [((0, 0), (0, 0))]))
    filled = CELLS["fill_cells"].apply(QUAD, "majority")
    assert filled[1] == (F, 1, 1, F, 0, 0, F)
    assert filled[5] == (F, 2, 2, F, 3, 3, F)
