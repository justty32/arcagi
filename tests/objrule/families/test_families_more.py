"""S3 families, second batch: mirror about an object, keyed parts, move_ex."""

import pytest

from arcagi.dsl import background as bgc
from arcagi.objrule.families import FAMILY_PRIMS
from arcagi.objrule.families.mirror import mirror_about


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def fit(name, states, targets):
    prim = FAMILY_PRIMS[name]
    with bgc.task_context(bgc.task_background(list(states) + list(targets))):
        found = prim.candidates(states, targets)
        assert found, name
        assert all(prim.apply(s, *found[0]) == t for s, t in zip(states, targets))
    return found


def test_mirror_about_center_object() -> None:
    s1 = grid("200000 000000 003000 000000 000000")
    t1 = grid("200020 000000 003000 000000 200020")
    s2 = grid("0000000 0200000 0000000 0003000 0000000 0000000 0000000")
    t2 = grid("0000000 0200020 0000000 0003000 0000000 0200020 0000000")
    found = fit("mirror_about", [s1, s2], [t1, t2])
    assert found[0][1:] == ("color", 3, "both")


def test_mirror_about_needs_moving_center() -> None:
    s = grid("200 030 000")
    t = grid("202 030 202")
    with bgc.task_context(0):
        assert FAMILY_PRIMS["mirror_about"].candidates([s, s], [t, t]) == []
        with pytest.raises(ValueError):
            mirror_about(grid("000 000"), "4same", "color", 3, "lr")


def test_part_bottom_half() -> None:
    states = [grid("20 20 20 20"), grid("202 202 002 000"), grid("02 02")]
    targets = [grid("20 20 80 80"), grid("202 802 008 000"), grid("02 08")]
    found = fit("part_key", states, targets)
    assert found[0][1:3] == ("bottom_half", "const")


def test_part_alternate_cells_of_a_line() -> None:
    states = [grid("3000 0300 0030 0003"), grid("300 030 003"), grid("30 03")]
    targets = [grid("3000 0400 0030 0004"), grid("300 040 003"), grid("30 04")]
    found = fit("part_key", states, targets)
    assert found[0][0] == "8same" and found[0][1] == "alt_odd"


def test_move_ex_one_step_toward_other() -> None:
    states = [grid("3000 0000 0004"), grid("30004"), grid("00 00 30 00 40")]
    targets = [grid("0000 0300 0004"), grid("03004"), grid("00 00 00 30 40")]
    found = fit("move_ex", states, targets)
    assert found[0][4:] == ("step", "keep")


def test_group_scope_own_color_bbox() -> None:
    # each pair of same-colored pixels spans a rectangle filled in its color
    states = [grid("10000 00000 00100 03000 00003"), grid("2000 0020 4000 0004")]
    targets = [grid("11100 11100 11100 03333 03333"), grid("2220 2220 4444 4444")]
    found = fit("bbox_fill_key", states, targets)
    assert found[0][0] == "group" and dict(found[0][2]) == {0: -1}


def test_template_fill_same_size_markers() -> None:
    states = [
        grid("240000 340000 000550 000550 550000 550000"),
        grid("0000 1200 0000 0055"),
        grid("55000 55000 00000 00120"),
    ]
    targets = [
        grid("240000 340000 000240 000340 240000 340000"),
        grid("0000 1200 0000 0012"),
        grid("12000 55000 00000 00120"),
    ]
    with pytest.raises(AssertionError):
        fit("template_paste", states, targets)  # 1x2 vs 2x2 boxes differ
    states[2] = grid("00000 55000 00000 00120")
    targets[2] = grid("00000 12000 00000 00120")
    assert fit("template_paste", states, targets) == [("fill",)]
