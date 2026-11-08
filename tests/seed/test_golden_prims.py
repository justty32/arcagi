"""``golden_prims.json`` (handed to the C++ port) agrees with the Python
implementation and covers every primitive with odd data."""

import json
from pathlib import Path

from arcagi.seed import PRIMS, EvalError, interp, run

GOLDEN = Path(__file__).with_name("golden_prims.json")


def _walk(v):
    yield v
    if isinstance(v, list):
        for e in v:
            yield from _walk(e)


def _plain(v):
    return [_plain(e) for e in v] if isinstance(v, tuple) else v


def test_golden_matches_python():
    doc = json.loads(GOLDEN.read_text())
    assert set(doc["cases"]) == set(PRIMS)
    for name, cases in doc["cases"].items():
        assert len(cases) >= 20, name
        for c in cases:
            prog = interp.from_json(c["program"])
            assert prog[0] == name
            try:
                got = _plain(run(prog, c["input"]))
            except EvalError:
                got = "ERR"
            want = c["output"]
            assert got == want, (name, c)


def test_golden_covers_odd_data():
    doc = json.loads(GOLDEN.read_text())
    int_only = {"add", "sub", "mul", "neg", "mod", "lt", "max", "min", "range"}
    bool_only = {"and", "or", "not"}
    for name, cases in doc["cases"].items():
        vals = [
            v for c in cases for v in _walk([c["input"], c["output"], c["program"]])
        ]
        if name not in bool_only:
            assert any(
                isinstance(v, int) and not isinstance(v, bool) and v < 0 for v in vals
            ), name
        if name in int_only | bool_only:
            continue
        lists = [v for c in cases for v in _walk(c["input"]) if isinstance(v, list)]
        assert any(v == [] for v in lists), name
        assert any(
            len({len(e) for e in v if isinstance(e, list)}) > 1 for v in lists
        ), name


def test_golden_is_reproducible():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_golden_prims", Path(__file__).with_name("make_golden_prims.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.generate() == json.loads(GOLDEN.read_text())
