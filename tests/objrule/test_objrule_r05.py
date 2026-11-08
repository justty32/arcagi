"""Round-5 per-object rules: 8 directions, two-step, shape -> color, formulas."""

import json

from arcagi.objrule import OBJRULE_PRIMS, view


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def _check(name, states, targets):
    prim = OBJRULE_PRIMS[name]
    found = prim.candidates(states, targets)
    assert found
    json.dumps(found)
    assert all(prim.apply(s, *found[0]) == t for s, t in zip(states, targets))
    return found


def test_dir8_to_diagonal() -> None:
    from arcagi.dsl import extract as ex

    g = grid("200 000 008")
    a = ex.anchor_at(g, "4same", (0, 0))
    body = view.make("nearest", "4same", "dir8_to")
    assert ex.run_on_object(body, g, a) == "down_right"
    aligned = grid("208")
    a = ex.anchor_at(aligned, "4same", (0, 0))
    assert ex.run_on_object(body, aligned, a) == "right"


def test_move_from_diagonal() -> None:
    s1, t1 = (
        grid("20000 00000 00000 00000 00008"),
        grid("00000 00000 00000 00020 00008"),
    )
    s2, t2 = (
        grid("00002 00000 00000 00000 80000"),
        grid("00000 00000 00000 02000 80000"),
    )
    s3, t3 = (
        grid("80000 00000 00000 00000 00002"),
        grid("80000 02000 00000 00000 00000"),
    )
    found = _check("move_from", [s1, s2, s3], [t1, t2, t3])
    assert found[0][3]["prop"] == "dir8_to"
    test = grid("00008 00000 00000 00000 20000")
    assert OBJRULE_PRIMS["move_from"].apply(test, *found[0]) == grid(
        "00008 00020 00000 00000 00000"
    )


def test_recolor_move_takes_marker_color() -> None:
    s1, t1 = (
        grid("00500 00000 00000 00000 00300"),
        grid("00000 00000 00000 00300 00300"),
    )
    s2, t2 = (
        grid("00000 00000 50004 00000 00000"),
        grid("00000 00000 00044 00000 00000"),
    )
    s3, t3 = (
        grid("00000 00000 60005 00000 00000"),
        grid("00000 00000 66000 00000 00000"),
    )
    found = _check("recolor_move", [s1, s2, s3], [t1, t2, t3])
    assert found[0][3]["prop"] == "color" and found[0][4]["prop"] == "dir_to"


def test_move_extend_slide_then_ray() -> None:
    s1 = grid("0000000 0002000 0000000 0000000 0000000 0000000 0008000")
    t1 = grid("0002000 0002000 0002000 0002000 0002000 0002000 0008000")
    s2 = grid("0000000 0000000 0000000 8000020 0000000 0000000 0000000")
    t2 = grid("0000000 0000000 0000000 8222222 0000000 0000000 0000000")
    s3 = grid("0008000 0000000 0000000 0000000 0000000 0002000 0000000")
    t3 = grid("0008000 0002000 0002000 0002000 0002000 0002000 0002000")
    found = _check("move_extend", [s1, s2, s3], [t1, t2, t3])
    assert len(found[0]) == 5


def test_recolor_from_same_shape_legend() -> None:
    # Gray objects take the color of the same-shaped legend object in the grid.
    s1 = grid("11020 00020 00000 55005 00005")
    t1 = grid("11020 00020 00000 11002 00002")
    s2 = grid("33004 00004 00000 50550 50000")
    t2 = grid("33004 00004 00000 40330 40000")
    found = _check("recolor_from", [s1, s2], [t1, t2])
    assert any(p[3]["sel"][0] == "same_shape_other_color" for p in found)
    test = grid("00770 60000 60000 00055 05000 05000")
    assert OBJRULE_PRIMS["recolor_from"].apply(test, *found[0]) == grid(
        "00770 60000 60000 00077 06000 06000"
    )


def test_move_by_size_formula() -> None:
    s1 = grid("30440 00000 00000 00000 00000")
    t1 = grid("00000 30000 00440 00000 00000")
    s2 = grid("6660 0000 0000 0000 0000")
    t2 = grid("0000 0000 0000 6660 0000")
    found = _check("move_by", [s1, s2], [t1, t2])
    conn, attr, value, d, body = found[0]
    assert d == "down" and body[0] in ("lin", "div")
    test = grid("70000 00000 00000 00000 00000 00000")
    assert OBJRULE_PRIMS["move_by"].apply(test, *found[0]) == grid(
        "00000 70000 00000 00000 00000 00000"
    )
