"""Object layer: selector inference, selector+action primitives, object colormap."""

import json

from arcagi.dsl.objects import OBJECTS, apply_object_colormap, fit_object_colormap
from arcagi.dsl.objects_props import extract, separate


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def candidates(name: str, states, targets) -> list:
    out = list(OBJECTS[name].candidates(states, targets))
    json.dumps(out)  # parameters must stay JSON-serializable
    return out


def solves(name: str, states, targets) -> list:
    """Candidate params that reproduce every train target."""
    prim = OBJECTS[name]
    return [
        p
        for p in candidates(name, states, targets)
        if all(prim.apply(s, *p) == t for s, t in zip(states, targets, strict=True))
    ]


# Two inputs: a big 2x2 object and small dots of different colors.
S1 = grid("0000000 0110020 0110000 0000300 0000000")
S2 = grid("0000000 0300000 0001100 0001100 0201100")


def test_attributes_of_extracted_objects() -> None:
    objs = extract(S1, "4same")
    big = next(o for o in objs if o.props["size"] == 4)
    assert big.props["is_largest"] == 1 and big.props["is_smallest"] == 0
    assert big.props["shape"] == "2x2:1111"
    assert {o.props["color"] for o in objs} == {1, 2, 3}
    ring = extract(grid("000000 011100 010100 011100 000000"), "4same")[0]
    assert ring.props["has_hole"] == 1 and ring.props["touches_border"] == 0


def test_separate_picks_simplest_attribute_or_nothing() -> None:
    objs = extract(S1, "4same")
    labeled = [[(o, o.props["size"] == 4) for o in objs]]
    assert separate(labeled)[0] == ("color", 1)
    mixed = [[(objs[0], True), (objs[1], True), (objs[2], False)]]
    assert all(attr != "color" for attr, _ in separate(mixed))
    assert separate([[(o, None) for o in objs]]) == []


def test_recolor_sel_infers_selector_from_largest_object() -> None:
    t1 = grid("0000000 0550020 0550000 0000300 0000000")
    t2 = grid("0000000 0300000 0005500 0005500 0205500")
    found = solves("recolor_sel", [S1, S2], [t1, t2])
    assert ("4same", "color", 1, 5) in found
    test = grid("000 077 077")
    s3 = grid("1200 0000 0033 0033")
    assert OBJECTS["recolor_sel"].apply(s3, "4same", "is_largest", 1, 5) == grid(
        "1200 0000 0055 0055"
    )
    assert candidates("recolor_sel", [test], [grid("00 00")]) == []


def test_delete_and_keep_sel() -> None:
    t1 = grid("0000000 0110000 0110000 0000000 0000000")
    t2 = grid("0000000 0000000 0001100 0001100 0001100")
    assert ("4same", "color", 1) in solves("keep_sel", [S1, S2], [t1, t2])
    assert ("4same", "is_largest", 0) in solves("delete_sel", [S1, S2], [t1, t2])


def test_fill_holes_paints_inside_objects() -> None:
    s = grid("00000 01110 01010 01110 00000")
    t = grid("00000 01110 01410 01110 00000")
    assert solves("fill_holes", [s], [t]) == [(4,)]


def test_move_sel_slides_until_blocked() -> None:
    s = grid("00000 02000 00000 00000 11111")
    t = grid("00000 00000 00000 02000 11111")
    found = solves("move_sel", [s], [t])
    assert any(p[-1] == "down" for p in found)
    # Two stacked objects do not overlap after sliding.
    two = grid("030 000 020 000")
    out = OBJECTS["move_sel"].apply(two, "4same", "all", 1, "down")
    assert out == grid("000 000 030 020")


def test_extend_sel_draws_rays_to_border() -> None:
    s = grid("00000 00000 30000 00000")
    t = grid("00000 00000 33333 00000")
    assert ("4same", "all", 1, "right") in solves("extend_sel", [s], [t])


def test_object_colormap_learns_size_to_color() -> None:
    s1 = grid("1010 0000 1101")
    t1 = grid("2020 0000 3302")
    s2 = grid("0011 0000 1010")
    t2 = grid("0033 0000 2020")
    test = grid("1100 0001")
    table = fit_object_colormap([s1, s2], [t1, t2], [test])
    assert table is not None
    json.dumps(table)
    assert apply_object_colormap(test, table) == grid("3300 0002")
    assert all(apply_object_colormap(s, table) == t for s, t in [(s1, t1), (s2, t2)])


def test_object_colormap_refuses_low_support_and_unknown_test_keys() -> None:
    # Three size classes (1->2, 2->3, 3->4), so no two-way split fits.
    states = [grid("1010 0000 1101 0000 1110"), grid("0011 0000 1010 0000 0111")]
    targets = [grid("2020 0000 3302 0000 4440"), grid("0033 0000 2020 0000 0444")]
    assert fit_object_colormap(states, targets, [grid("1110 0000 1100 0000 1000")])
    # A size-4 object (and a fourth size rank) never appears in train.
    test = grid("1111 0000 1110 0000 1101")
    assert fit_object_colormap(states, targets, [test]) is None
    # Size 2 -> 3 is seen only once: not enough support.
    one = grid("1010 0000 1101")
    assert fit_object_colormap([one], [grid("2020 0000 3302")], [one]) is None


def test_object_colormap_split_form_handles_unseen_keys() -> None:
    # Size-3 objects -> 2, everything else -> 1, test has an unseen size 5.
    states = [grid("5550 0000 5505"), grid("0555 0000 5505 0000 5555")]
    targets = [grid("2220 0000 1101"), grid("0222 0000 1101 0000 1111")]
    test = grid("5550 0000 5555 5000")
    table = fit_object_colormap(states, targets, [test])
    assert table is not None and len(table) == 4
    json.dumps(table)
    assert apply_object_colormap(test, table) == grid("2220 0000 1111 1000")
