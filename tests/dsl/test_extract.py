"""Extraction expressions and the extract-parameterised primitives."""

import json
import subprocess
import sys

import pytest

from arcagi.dsl import extract as ex
from arcagi.dsl.extract_prims import EXTRACT_PRIMS, install


def grid(text: str) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(ch) for ch in line) for line in text.split())


G = grid("00000 01100 01100 00003 02200")


def test_selectors_and_props() -> None:
    assert ex.run(["bbox", ["largest", "4same"]], G) == [1, 1, 2, 2]
    assert ex.run(["color", ["smallest", "4same"]], G) == 3
    assert ex.run(["count", ["all", "4same"]], G) == 3
    assert ex.run(["size", ["color", "4same", 2]], G) == 2
    assert ex.run(["subgrid", ["largest", "4same"]], G) == [[1, 1], [1, 1]]
    assert ex.run(["cells", ["unique_shape", "4same"]], grid("101 000 110")) == [
        [2, 0],
        [2, 1],
    ]
    assert ex.run(["color", ["pred", "4same", ["eq", "size", 1]]], G) == 3
    wrapped = {
        "kind": "extract",
        "in": "grid",
        "out": "json",
        "body": ["size", ["largest", "8multi"]],
    }
    assert ex.run(wrapped, G) == 4


def test_object_masks_other_cells() -> None:
    g2 = grid("000 120 020")
    assert ex.run(["object", ["color", "4same", 2]], g2) == [[2], [2]]
    assert ex.run(["subgrid", ["all", "4same"]], g2) == [[1, 2], [0, 2]]
    assert ex.run(["object", ["color", "4same", 1]], g2) == [[1]]


def test_ambiguity_and_validation() -> None:
    tie = grid("000 101 000")
    with pytest.raises(ValueError):
        ex.run(["bbox", ["largest", "4same"]], tie)
    with pytest.raises(ValueError):
        ex.run(["nope", ["largest", "4same"]], G)
    assert not ex.validate(["color", ["color", "4same"]])
    assert ex.validate(["color", ["pred", "8multi", "pred_x"]])


def test_install_and_named_run() -> None:
    install({"extract_t": {"kind": "extract", "body": ["color", ["largest", "4same"]]}})
    try:
        assert ex.run("extract_t", G) == 1
    finally:
        install({})


def test_crop_extract_candidates_direct_then_live() -> None:
    prim = EXTRACT_PRIMS["crop_extract"]
    states = [G, grid("0000 0330 0330 0300 0005")]
    targets = [grid("11 11"), grid("33 33 30")]
    found = prim.candidates(states, targets)
    assert found and all(prim.apply(s, *found[0]) == t for s, t in zip(states, targets))
    json.dumps(found)
    install({"extract_l": {"body": found[0][0]}})
    try:
        assert prim.candidates(states, targets) == [("extract_l",)]
    finally:
        install({})
    assert prim.candidates(states, states) == []


def test_fill_recolor_keep_count() -> None:
    a, b = grid("000 011 020"), grid("000 220 002")
    fill = EXTRACT_PRIMS["fill_extract"]
    found = fill.candidates([a, b], [grid("11 11"), grid("2")])
    assert found and fill.apply(a, *found[0]) == grid("111 111 111")
    recolor = EXTRACT_PRIMS["recolor_extract"]
    found = recolor.candidates([a, b], [grid("000 011 010"), grid("000 220 002")])
    assert found and recolor.apply(a, *found[0]) == grid("000 011 010")
    keep = EXTRACT_PRIMS["keep_extract"]
    assert keep.candidates([a], [a]) == []
    found = keep.candidates([a, b], [grid("000 011 000"), grid("000 220 000")])
    assert found and keep.apply(b, *found[0]) == grid("000 220 000")
    count = EXTRACT_PRIMS["paint_count"]
    c1, c2 = grid("1010 0001 0000"), grid("1000 0010 0000")
    found = count.candidates([c1, c2], [grid("555"), grid("55")])
    assert found and count.apply(c1, *found[0]) == grid("555")
    assert count.candidates([c1, c2], [grid("55"), grid("55")]) == []


def test_cli(tmp_path) -> None:
    (tmp_path / "_rule.json").write_text(
        json.dumps({"body": ["count", ["all", "4same"]]})
    )
    out = subprocess.run(
        [sys.executable, "-m", "arcagi.dsl.extract", str(tmp_path / "_rule.json")],
        input=json.dumps({"grid": [list(r) for r in G]}),
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "3"


def test_paint_count_with_extracted_color() -> None:
    count = EXTRACT_PRIMS["paint_count"]
    a, b = grid("110 000 000"), grid("202 000 200")
    found = count.candidates([a, b], [grid("11"), grid("222")])
    assert found and count.apply(b, *found[0]) == grid("222")
    assert count.apply(a, *found[0]) == grid("11")
