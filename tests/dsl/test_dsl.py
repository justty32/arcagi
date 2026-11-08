"""Grid DSL: primitive properties, learners refusing bad fits, JSON programs."""

import pytest

from arcagi.dsl import grid as g
from arcagi.dsl.learners import fit_colormap, fit_local_rule
from arcagi.dsl.program import cost, from_json, run, to_json
from arcagi.dsl.registry import MARK, PRIMITIVES

A = ((1, 2, 0), (0, 3, 0))


def test_geometry_inverses_and_identities() -> None:
    assert g.rot90(g.rot270(A)) == A
    assert g.rot90(g.rot90(A)) == g.rot180(A)
    assert g.transpose(g.transpose(A)) == A
    assert g.flip_lr(g.flip_lr(A)) == A
    assert g.anti_transpose(A) == g.rot180(g.transpose(A))


def test_scaling_and_tiling_round_trip() -> None:
    assert g.downscale(g.upscale(A, 2, 3), 2, 3) == A
    assert g.shape(g.tile(A, 2, 2)) == (4, 6)
    with pytest.raises(ValueError):
        g.downscale(A, 2, 2)


def test_ratio_parameters_are_inferred_only_when_consistent() -> None:
    up = PRIMITIVES["upscale"]
    assert list(up.candidates([A], [g.upscale(A, 2, 2)])) == [(2, 2)]
    assert list(up.candidates([A, A], [g.upscale(A, 2, 2), g.upscale(A, 3, 3)])) == []


def test_split_overlay_skips_separator_and_marks_result() -> None:
    grid = ((1, 0, 5, 1, 1), (0, 0, 5, 0, 1))
    out = PRIMITIVES["split_overlay"].apply(grid, "v", "and")
    assert out == ((MARK, 0), (0, 0))


def test_fill_enclosed_marks_only_inner_background() -> None:
    grid = ((1, 1, 1, 0), (1, 0, 1, 0), (1, 1, 1, 0), (0, 0, 0, 0))
    out = PRIMITIVES["fill_enclosed"].apply(grid)
    assert out[1][1] == MARK
    assert out[0][3] == 0


def test_symmetrize_and_gravity() -> None:
    grid = ((1, 2, 0), (3, 0, 0))
    assert PRIMITIVES["symmetrize"].apply(grid, "lr", 0) == ((1, 2, 1), (3, 0, 3))
    tall = ((1, 0), (0, 0), (0, 2))
    assert PRIMITIVES["gravity"].apply(tall, "down") == ((0, 0), (0, 0), (1, 2))


def test_crop_object_selects_largest() -> None:
    grid = ((0, 0, 0, 0), (0, 2, 2, 0), (0, 2, 2, 0), (3, 0, 0, 0))
    out = PRIMITIVES["crop_object"].apply(grid, "4same", "largest")
    assert out == ((2, 2), (2, 2))


def test_colormap_learns_and_refuses_conflicts() -> None:
    assert fit_colormap([((1, 2),)], [((3, 2),)], [((1, 1),)]) == [[1, 3]]
    assert fit_colormap([((1, 1),)], [((3, 4),)], []) is None
    assert fit_colormap([((MARK, 1),)], [((1, 1),)], [((MARK + 1, 1),)]) is None


def test_local_rule_requires_known_test_keys() -> None:
    state, target = ((0, 1, 0),), ((2, 1, 2),)
    assert fit_local_rule([state], [target], [state], "n4") is not None
    assert fit_local_rule([state], [target], [((0, 3, 0),)], "n4") is None


def test_program_json_round_trip_and_cost() -> None:
    program = (("upscale", 2, 2), ("colormap", [[1, 3]]))
    assert from_json(to_json(program)) == (("upscale", 2, 2), ("colormap", [[1, 3]]))
    assert run(program, ((1,),)) == ((3, 3), (3, 3))
    assert cost((("flip_lr",),)) < cost(program)


def test_run_rejects_unresolved_marker() -> None:
    with pytest.raises(ValueError):
        ring = ((0,) * 5, (0, 1, 1, 1, 0), (0, 1, 0, 1, 0), (0, 1, 1, 1, 0), (0,) * 5)
        run((("fill_enclosed",),), ring)
