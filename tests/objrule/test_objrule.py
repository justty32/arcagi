"""Per-object rules: object-view extraction, fitting and the primitives."""

import json

import pytest

from arcagi.dsl import extract as ex
from arcagi.objrule import OBJRULE_PRIMS, view
from arcagi.objrule.fit import MIN_OBJECTS


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def body(op: str, prop: str, conn: str = "4same") -> dict:
    return view.make(op, conn, prop)


def at(g, y, x, conn="4same"):
    return ex.anchor_at(g, conn, (y, x))


G = grid("1000200 0000000 0000000 1000000 0000033")


def test_selectors_and_props() -> None:
    a = at(G, 0, 0)
    assert ex.run_on_object(body("nearest", "color"), G, a) == 1  # (3,0) gap 2
    assert ex.run_on_object(body("nearest_other_color", "color"), G, a) == 2
    assert ex.run_on_object(body("nearest_same_color", "dir_to"), G, a) == "down"
    assert ex.run_on_object(body("nearest_same_color", "dist_to"), G, a) == 2
    assert ex.run_on_object(body("nearest_aligned_other_color", "dir_to"), G, a) == (
        "right"
    )
    assert ex.run_on_object(body("largest", "color"), G, a) == 3
    assert ex.run_on_object(body("this", "size_rank"), G, a) == 2
    assert ex.run_on_object(body("this", "wall_dir"), G, at(G, 0, 4)) == "up"
    t = grid("120 000")
    assert ex.run_on_object(body("touching", "color"), t, at(t, 0, 0)) == 2
    with pytest.raises(ValueError):  # (4,5) is not aligned with (0,0)
        ex.run_on_object(body("largest", "dir_to"), G, a)
    with pytest.raises(ValueError):
        ex.run_on_object(body("touching", "color"), G, a)
    assert not view.validate(body("this", "dir_to"))
    assert not view.validate(body("nearest", "wall_dir"))
    assert all(view.validate(b) for b in view.bodies(view.OPROPS))


def _check(name, states, targets):
    prim = OBJRULE_PRIMS[name]
    found = prim.candidates(states, targets)
    assert found
    json.dumps(found)
    assert all(prim.apply(s, *found[0]) == t for s, t in zip(states, targets))
    return found


def test_recolor_from_touching_marker() -> None:
    s1 = grid("000000 553000 550000 000000 055400 000000")
    t1 = grid("000000 333000 330000 000000 044400 000000")
    s2 = grid("000000 255000 000000 000550 000556 000000")
    t2 = grid("000000 222000 000000 000660 000666 000000")
    found = _check("recolor_from", [s1, s2], [t1, t2])
    assert found[0][3]["prop"] == "color"
    test = grid("5510 0000 7550")
    assert OBJRULE_PRIMS["recolor_from"].apply(test, *found[0]) == grid(
        "1110 0000 7770"
    )


def test_move_from_toward_nearest_other_color() -> None:
    s1 = grid("200800 000000 000000 000002 000000 000008")
    t1 = grid("002800 000000 000000 000000 000002 000008")
    s2 = grid("800000 000000 200000 000208")
    t2 = grid("800000 200000 000000 000028")
    found = _check("move_from", [s1, s2], [t1, t2])
    assert found[0][3]["prop"] == "dir_to"


def test_extend_from_toward_same_color() -> None:
    s1 = grid("10001 00000 20000 00000 20000")
    t1 = grid("11111 00000 20000 20000 20000")
    s2 = grid("030 000 030")
    t2 = grid("030 030 030")
    _check("extend_from", [s1, s2], [t1, t2])


def test_not_applicable_is_empty() -> None:
    a, b = grid("12 00"), grid("120 000")
    for prim in OBJRULE_PRIMS.values():
        assert prim.candidates([a], [b]) == []  # shape change
        assert prim.candidates([a], [a]) == []  # nothing changes
    # Fewer than MIN_OBJECTS targeted objects: no candidates.
    s, t = grid("5520 0000"), grid("2220 0000")
    assert MIN_OBJECTS == 3
    assert OBJRULE_PRIMS["recolor_from"].candidates([s], [t]) == []
