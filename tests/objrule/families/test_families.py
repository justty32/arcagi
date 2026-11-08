"""S3 per-object rule families: keyed regions, keyed stamps, bridges, scopes."""

import json

import pytest

from arcagi.dsl import background as bgc
from arcagi.objrule import OBJRULE_PRIMS
from arcagi.objrule.families import FAMILY_PRIMS, scope


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def fit(name, states, targets):
    prim = FAMILY_PRIMS[name]
    with bgc.task_context(bgc.task_background(list(states) + list(targets))):
        found = prim.candidates(states, targets)
        assert found, name
        json.dumps(found)
        assert all(prim.apply(s, *found[0]) == t for s, t in zip(states, targets))
    return found


def test_registered_in_objrule() -> None:
    assert set(FAMILY_PRIMS) <= set(OBJRULE_PRIMS)
    assert {"halo8_key", "inner_key", "stamp_key", "bridge"} <= set(FAMILY_PRIMS)


def test_halo_by_color() -> None:
    # color 2 gets a ring of 1, color 3 is left alone
    states = [
        grid("00000 02000 00000 00003"),
        grid("0000000 0020000 0000000 0300000 0000020 0000000"),
    ]
    targets = [
        grid("11100 12100 11100 00003"),
        grid("0111000 0121000 0111000 0300111 0000121 0000111"),
    ]
    found = fit("halo8_key", states, targets)
    assert found[0][1] == "color"
    assert dict(found[0][2]) == {2: 1}
    test = grid("0000 0020 0000 3000")
    with bgc.task_context(0):
        out = FAMILY_PRIMS["halo8_key"].apply(test, *found[0])
    assert out == grid("0111 0121 0111 3000")


def test_halo_needs_two_values_and_support() -> None:
    # one painted object only: below the >= 3 objects threshold
    states = [grid("000 020 000 000")]
    targets = [grid("111 121 111 000")]
    with bgc.task_context(0):
        assert FAMILY_PRIMS["halo8_key"].candidates(states, targets) == []


def test_inner_by_largest() -> None:
    s1 = grid("5550000 5550000 5550000 0000000 0005555 0005555 0005555 0005555")
    t1 = grid("5550000 5150000 5550000 0000000 0005555 0005225 0005225 0005555")
    s2 = grid("555550 555550 555550 000000 555000 555000 555000")
    t2 = grid("555550 522250 555550 000000 555000 515000 555000")
    found = fit("inner_key", [s1, s2], [t1, t2])
    assert found[0][1] == "is_largest"


def test_bbox_fill_const() -> None:
    states = [grid("800 080 008"), grid("0800 8000 0000"), grid("080 800 080")]
    targets = [grid("822 282 228"), grid("2800 8200 0000"), grid("280 820 280")]
    found = fit("bbox_fill_key", states, targets)
    assert found[0][0] == "8same"


def test_stamp_by_color() -> None:
    states = [
        grid("00000 02000 00000 00010 00000"),
        grid("0000000 0010000 0000000 0000200 0000000"),
        grid("000000 010000 000000 000000 000020 000000"),
    ]
    targets = [
        grid("40400 02000 40470 00717 00070"),
        grid("0070000 0717000 0074040 0000200 0004040"),
        grid("070000 717000 070000 000404 000020 000404"),
    ]
    found = fit("stamp_key", states, targets)
    table = dict(found[0][2])
    assert set(table) == {1, 2}
    assert (0, -1, 7) in table[1] and (-1, -1, 4) in table[2]


def test_bridge_constant_fill() -> None:
    states = [grid("10001 00000 10000"), grid("100100 000000 000000 000100")]
    targets = [grid("18881 80000 10000"), grid("188100 000800 000800 000100")]
    found = fit("bridge", states, targets)
    assert found[0][1:] == ("hv", "stop", 8)


def test_bridge_pass_mode_paints_around_walls() -> None:
    s = grid("2050200 0050000 0050000 3050030")
    t = grid("2252200 0050000 0050000 3353330")
    s2 = grid("40504 00500")
    t2 = grid("44544 00500")
    found = fit("bridge", [s, s2], [t, t2])
    assert found[0][2] == "pass" and found[0][3] == -1


def test_scope_parse_and_alt_background() -> None:
    assert scope.parse("4same") == ("4same", None)
    assert scope.parse("8same@5") == ("8same", 5)
    for bad in ("4same@", "4same@x", "nope", 3):
        with pytest.raises(ValueError):
            scope.parse(bad)
    g = grid("000000 055550 052550 055550 000000")
    with bgc.task_context(0):
        plain = scope.objects(g, "4same")
        assert sorted(o.props["color"] for o in plain) == [2, 5]
        objs = scope.objects(g, "4same@5")
    assert sorted(o.props["color"] for o in objs) == [0, 2]


def test_alt_background_scope_fits() -> None:
    # objects sit on a 5 panel; rings are painted on the panel color only
    s1 = grid("00000000 05555550 05255550 05555550 05555250 05555550 00000000")
    t1 = grid("00000000 01115550 01215550 01111110 05551210 05551110 00000000")
    s2 = grid("0000000 0555550 0555550 0552550 0555550 0000000")
    t2 = grid("0000000 0555550 0511150 0512150 0511150 0000000")
    found = fit("halo8_key", [s1, s2], [t1, t2])
    assert found[0][0].endswith("@5")
