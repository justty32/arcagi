"""``$ref`` resolution in macro programs (aos N-45 semantics) and folding."""

import json
from pathlib import Path

import pytest

from arcagi.blocks.catalog import RefError, expand_steps, load_macro_program
from arcagi.srcspace import fold_refs, node_count, unfold_refs


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_plain_macro_unchanged(tmp_path):
    _write(tmp_path / "m" / "program.json", [["flip_lr"], ["upscale", 2, 2]])
    assert load_macro_program(tmp_path / "m") == (("flip_lr",), ("upscale", 2, 2))


def test_ref_step_spliced_relative_to_file(tmp_path):
    _write(tmp_path / "m_a" / "program.json", [["flip_lr"], ["rot90"]])
    _write(
        tmp_path / "m_b" / "program.json", [{"$ref": "../m_a/program.json"}, ["rot180"]]
    )
    _write(tmp_path / "m_c" / "program.json", [["x"], {"$ref": "../m_b/program.json"}])
    assert load_macro_program(tmp_path / "m_c") == (
        ("x",),
        ("flip_lr",),
        ("rot90",),
        ("rot180",),
    )


def test_ref_pointer_and_list_concat(tmp_path):
    _write(tmp_path / "lib.json", {"a": [["flip_lr"]], "b": [["rot90"], ["rot180"]]})
    with pytest.raises(RefError):  # #/b/0/0 is a string, not a program list
        expand_steps([{"$ref": "lib.json#/b/0/0"}], tmp_path)
    steps = [{"$ref": ["lib.json#/a", "lib.json#/b"]}]
    assert expand_steps(steps, tmp_path) == [["flip_lr"], ["rot90"], ["rot180"]]


def test_cycle_and_missing_file_make_macro_unloadable(tmp_path):
    _write(tmp_path / "m_a" / "program.json", [{"$ref": "../m_b/program.json"}])
    _write(tmp_path / "m_b" / "program.json", [{"$ref": "../m_a/program.json"}])
    _write(tmp_path / "m_s" / "program.json", [{"$ref": "program.json"}])
    _write(tmp_path / "m_m" / "program.json", [{"$ref": "nope.json"}])
    for name in ("m_a", "m_s", "m_m"):
        assert load_macro_program(tmp_path / name) is None
    with pytest.raises(RefError):
        expand_steps([{"$ref": "m_a/program.json"}], tmp_path)


def test_malformed_directive_left_untouched(tmp_path):
    steps = [{"$ref": ""}, {"$ref": 3}, {"$ref": "x.json#a"}, {"$ref": "#/a"}]
    assert expand_steps(steps, tmp_path) == steps
    _write(tmp_path / "m" / "program.json", [{"$ref": 3}])
    assert load_macro_program(tmp_path / "m") is None


def test_fold_unfold_and_node_count(tmp_path):
    _write(tmp_path / "m_a" / "program.json", [["flip_lr"], ["rot90"]])
    macros = {"../m_a/program.json": [["flip_lr"], ["rot90"]]}
    program = [["x"], ["flip_lr"], ["rot90"], ["y", 1]]
    folded = fold_refs(program, macros)
    assert folded == [["x"], {"$ref": "../m_a/program.json"}, ["y", 1]]
    assert unfold_refs(folded, tmp_path / "m_a") == program
    assert node_count(folded) < node_count(program)
