"""Lossless JSON <-> Janet round trips over every block and solved program."""

from pathlib import Path

import pytest

from arcagi.blocks import REPO_ROOT
from arcagi.srcspace import from_janet, janet_bridge, to_janet
from arcagi.srcspace.emit import json_text
from arcagi.srcspace.parse import JanetSyntaxError
from arcagi.srcspace.roundtrip import block_objects, roundtrip, trace_programs

BLOCKS = REPO_ROOT / "aos" / "blocks"
TRACES = REPO_ROOT / "artifacts" / "r04" / "dsl-training-traces.jsonl"


def _objects():
    objects = list(block_objects(BLOCKS))
    if TRACES.exists():
        objects += list(trace_programs([TRACES]))
    return objects


@pytest.fixture(scope="module")
def report():
    if not BLOCKS.is_dir():
        pytest.skip("no aos/blocks")
    return roundtrip(_objects())


def test_all_blocks_and_programs_round_trip(report):
    assert report.checked > 300
    assert report.failures == []


def test_janet_parses_every_emitted_text(report):
    results = janet_bridge.check_all(report.texts)
    if results and results[0] is None:
        pytest.skip("janet not installed")
    assert all(results)


def test_program_form_matches_design():
    program = [["crop_object", "4same", "smallest"], ["upscale", 2]]
    text = to_janet(program)
    assert text.strip() == '(prog (crop-object "4same" "smallest") (upscale 2))'
    assert from_janet(text) == program


def test_body_symbols_and_strings_stay_distinct():
    body = ["lin", "n_obj", 1, 0, "1", True, None, 1.5, "nil", "a b", 'x\n"y']
    text = to_janet(body)
    assert text.startswith("(lin n_obj 1 0")
    assert json_text(from_janet(text)) == json_text(body)


@pytest.mark.parametrize(
    "obj",
    [
        [],
        {},
        {"kind": "formula", "body": ["max", "h", "e"], "extracts": {"e": ["count"]}},
        [["odd-name", 1], ["prog"], ["def", [[1, 2, 3]] * 3]],
        [["recolor_from", "4same", "c", 1, {"scope": "object", "sel": ["t"]}]],
        ["é", "\x01", -0.0, 10**20, 1e-05],
        [{"$ref": "../m_a/program.json"}, ["m_a"], {"$ref": "x.json#/0"}],
    ],
)
def test_edge_cases_round_trip(obj):
    text = to_janet(obj)
    assert json_text(from_janet(text)) == json_text(obj)
    if janet_bridge.check(text) is False:
        pytest.fail(f"janet rejected: {text}")


def test_ref_renders_as_def_and_call(tmp_path: Path):
    (tmp_path / "m_x").mkdir()
    (tmp_path / "m_x" / "program.json").write_text('[["flip_lr"],["rot90"]]')
    (tmp_path / "m_y").mkdir()
    program = [{"$ref": "../m_x/program.json"}, ["gravity", "down"]]
    text = to_janet(program, base=tmp_path / "m_y")
    assert '(def m-x "../m_x/program.json"' in text
    assert "(prog (flip-lr) (rot90))" in text
    assert '(prog (m-x) (gravity "down"))' in text
    assert from_janet(text) == program


def test_bad_text_raises():
    for text in ["(prog (a", '"open', "(a))", "(a) (b)", "{:a}"]:
        with pytest.raises(JanetSyntaxError):
            from_janet(text)
