"""Hand cases for the S1 extension primitives (``arcagi.dsl.ext``)."""

import pytest

from arcagi.dsl.ext import prims as ext
from arcagi.dsl.registry import PRIMITIVES


def grid_of(*rows: str):
    return tuple(tuple(int(c) for c in row) for row in rows)


def test_registered() -> None:
    assert {"x_ray", "x_connect", "x_compress", "x_crop_color", "x_period"} <= set(
        PRIMITIVES
    )


def test_ray_diagonal_from_block_corner_only() -> None:
    grid = grid_of("0000", "0110", "0110", "0000")
    assert ext.ray(grid, "ul", "pass", -1) == grid_of("1000", "0110", "0110", "0000")


def test_ray_stop_and_pass() -> None:
    grid = grid_of("10200")
    assert ext.ray(grid, "r", "stop", 1) == grid_of("11200")
    assert ext.ray(grid, "r", "pass", 1) == grid_of("11211")


def test_connect_pairs_and_order() -> None:
    grid = grid_of("30003", "00000", "40004")
    assert ext.connect(grid, "h") == grid_of("33333", "00000", "44444")
    grid = grid_of("01000", "20002", "01000")
    assert ext.connect(grid, "hv") == grid_of("01000", "21222", "01000")
    assert ext.connect(grid, "vh") == grid_of("01000", "22222", "01000")


def test_compress() -> None:
    grid = grid_of("1122", "1122", "3344")
    assert ext.compress(grid, "dup") == grid_of("12", "34")
    assert ext.compress(grid_of("000", "010", "000"), "bg") == grid_of("1")
    with pytest.raises(ValueError):
        ext.compress(grid_of("00", "00"), "bg")


def test_crop_color() -> None:
    grid = grid_of("00000", "05550", "05150", "05550")
    assert ext.crop_color(grid, 5, "inner") == grid_of("1")
    assert ext.crop_color(grid, 1, "bbox") == grid_of("1")
    assert ext.crop_color(grid, 5, "only") == grid_of("555", "505", "555")


def test_period_fill_and_extend() -> None:
    assert ext.period(grid_of("1212", "2101", "1212"), "fill", 0) == grid_of(
        "1212", "2121", "1212"
    )
    assert ext.period(grid_of("283", "830", "300"), "fill", 0) == grid_of(
        "283", "832", "328"
    )
    assert ext.period(grid_of("000", "120", "000"), "extend", 0) == grid_of(
        "121", "121", "121"
    )


def test_python_candidates_follow_engine_rules() -> None:
    states = [grid_of("0100", "0000")]
    targets = [grid_of("0111", "0000")]
    assert ("r", "pass", 1) in ext.ray_candidates(states, targets)
    assert ext.compress_candidates(states, targets) == []
