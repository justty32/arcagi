"""Features, formula evaluation / fitting, shape prediction and formula primitives."""

import pytest

from arcagi.dsl import features
from arcagi.dsl import formula as fm
from arcagi.dsl import formula_prims as fp


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


def test_features_compute() -> None:
    f = features.compute(grid("100 022 000"))
    assert set(f) == set(features.NAMES)
    assert (f["h"], f["w"], f["n_color"], f["n_fg"], f["n_bg"]) == (3, 3, 2, 3, 6)
    assert (f["n_obj"], f["n_obj8"], f["max_obj_size"], f["min_obj_size"]) == (
        2,
        1,
        2,
        1,
    )
    assert (f["max_obj_w"], f["min_obj_w"], f["cnt_0"], f["cnt_2"]) == (2, 1, 6, 2)
    assert features.compute(grid("00 00"))["max_obj_h"] == 0
    assert features.fg_color(grid("100 022 000")) == 2


def test_evaluate_and_validate() -> None:
    feats = {"h": 3, "w": 5}
    assert fm.evaluate(["lin", "h", 2, -1], feats) == 5
    assert fm.evaluate(["mul", "h", "w"], feats) == 15
    assert fm.evaluate(["sq", "w"], feats) == 25
    assert fm.evaluate(["max", "h", "w"], feats) == 5
    assert fm.evaluate(["min", "h", "w"], feats) == 3
    assert fm.evaluate(["const", 4], feats) == 4
    with pytest.raises(ValueError):
        fm.evaluate(["div", "h", 2], feats)
    assert fm.validate(["lin", "h", 4, 3])
    assert not fm.validate(["lin", "h", 5, 0])
    assert not fm.validate(["mul", "h", "nope"])
    assert fm.length(["lin", "h", 1, 0]) < fm.length(["lin", "h", 2, 0])


def _xs(**cols):
    base = features.compute(grid("1"))
    n = len(next(iter(cols.values())))
    return [{**base, **{k: v[i] for k, v in cols.items()}} for i in range(n)]


def test_fit_forms() -> None:
    xs = _xs(h=[2, 3, 5], w=[4, 4, 1])
    assert fm.fit(xs, [2, 3, 5]) == ["lin", "h", 1, 0]
    assert fm.fit(xs, [5, 7, 11]) == ["lin", "h", 2, 1]
    assert fm.fit(xs, [4, 9, 25]) == ["sq", "h"]
    assert fm.fit(xs, [8, 12, 5]) == ["mul", "h", "w"]
    assert fm.fit(xs, [4, 4, 5]) == ["max", "h", "w"]


def test_fit_two_pairs_library_only() -> None:
    xs = _xs(h=[2, 3])
    assert fm.fit(xs, [5, 7]) is None
    assert fm.fit(xs, [5, 7], [["lin", "h", 2, 1]]) == ["lin", "h", 2, 1]


def test_fit_rejects_constants_and_mismatch() -> None:
    xs = _xs(h=[2, 3, 5])
    assert fm.fit(xs, [3, 3, 3]) is None  # a constant is not a formula
    assert fm.fit(xs[:1], [2]) is None
    assert fm.fit(_xs(h=[2, 3, 5], w=[7, 1, 9]), [100, 1, 50]) is None
    assert fm.fit_dim(xs, [3, 3, 3]) == ["const", 3]


def test_fit_library_first() -> None:
    xs = _xs(h=[2, 3, 5], w=[2, 3, 5])
    assert fm.fit(xs, [2, 3, 5]) == ["lin", "h", 1, 0]
    assert fm.fit(xs, [2, 3, 5], {"lib": ["lin", "w", 1, 0]}) == ["lin", "w", 1, 0]
    assert fm.fit(xs, [2, 3, 5], [["sq", "w"]]) == ["lin", "h", 1, 0]


def test_predict_shapes() -> None:
    pairs = [
        (grid("12 30"), grid("1122 1122 3300 3300")),
        (grid("1 2 3"), grid("11 11 22 22 33 33")),
    ]
    assert fm.predict_shapes(pairs, [grid("123")]) is None  # 2 pairs, no library
    pairs.append((grid("1"), grid("11 11")))
    assert fm.predict_shapes(pairs, [grid("123")]) == [(2, 6)]
    const = [(grid("12 30"), grid("5")), (grid("123"), grid("6"))]
    assert fm.predict_shapes(const, [grid("1")]) == [(1, 1)]
    odd = [(grid("12 30"), grid("5")), (grid("123"), grid("6 6 6 6 6 6 6"))]
    assert fm.predict_shapes(odd, [grid("1")]) is None


def test_upscale_by_color_count() -> None:
    """Scale factor = number of foreground colors (varies across pairs)."""
    states = [grid("10 02"), grid("123 000 000"), grid("0000 0400")]
    targets = [
        fp.upscale_n(s, ["lin", "n_color", 1, 0], ["lin", "n_color", 1, 0])
        for s in states
    ]
    assert targets[0] == grid("1100 1100 0022 0022")
    prim = fp.FORMULA_PRIMS["upscale_n"]
    fp.install({})
    cands = prim.candidates(states, targets)
    assert cands
    assert all(prim.apply(s, *cands[0]) == t for s, t in zip(states, targets))
    assert prim.candidates(states, states) == []  # same size: not applicable
    assert prim.candidates(states[:2], targets[:2]) == []  # 2 pairs: library only
    fp.install({"f": {"kind": "formula", "body": ["lin", "n_color", 1, 0]}})
    try:
        assert prim.candidates(states[:2], targets[:2]) == [("f", "f")]
    finally:
        fp.install({})


def test_canvas_and_resize_and_library_names() -> None:
    states = [grid("0100 0100"), grid("002 000 202")]
    targets = [grid("11"), grid("222")]
    fp.install({"formula_x": {"kind": "formula", "body": ["lin", "n_fg", 1, 0]}})
    try:
        cands = fp.FORMULA_PRIMS["canvas"].candidates(states, targets)
        assert cands == [(["const", 1], "formula_x", "fg")]
        assert fp.canvas(states[1], *cands[0]) == targets[1]
    finally:
        fp.install({})
    assert fp.resize_crop(grid("10 34"), ["const", 1], ["const", 3]) == grid("100")
    assert fp.FORMULA_PRIMS["tile_n"].candidates([grid("1")], [grid("11")]) == []
