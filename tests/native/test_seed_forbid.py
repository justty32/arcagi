"""S1 ``forbid`` (root AST pattern pruning) in ``native/bin/arcbatch-forbid``
(``make -C native forbid``; reports/seed-forbid-1110/).

- Without ``forbid`` the output equals ``bin/arcbatch`` (timing fields aside).
- With pure-equivalence patterns the found program is the same and
  nodes_to_first only drops by the candidates skipped before the hit.
- ``?x`` repeated must bind identical subprograms; ``?c`` only matches ints.
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "native" / "bin" / "arcbatch"
NEW = ROOT / "native" / "bin" / "arcbatch-forbid"
DATA = ROOT / "data" / "ARC-AGI" / "data" / "training"
needs_bin = pytest.mark.skipif(not (OLD.exists() and NEW.exists()),
                               reason="run make -C native all forbid")
TASKS = ["68b16354", "beb8660c", "1e0a9b12", "d10ecb37", "44f52bb0", "ce4f8723"]
TIMING = {"seconds", "task_seconds", "wall_seconds"}
EQUIV = [["neg", ["neg", "?x"]], ["reverse", ["reverse", "?x"]], ["not", ["not", "?x"]],
         ["transpose", ["transpose", "?x"]], ["add", 0, "?x"], ["add", "?x", 0],
         ["sort", ["sort", "?x"]], ["max", "?x", "?x"], ["min", "?x", "?x"]]


def _run(binary, configs, tmp_path, tasks=TASKS):
    cfg = tmp_path / "cfg.jsonl"
    cfg.write_text("".join(json.dumps(c) + "\n" for c in configs))
    args = [str(binary)] + (["--batch"] if binary == NEW else [])
    args += ["--mode", "seed", "--threads", "2", "--configs", str(cfg)]
    for t in tasks:
        args += ["--task", str(DATA / f"{t}.json")]
    out = subprocess.run(args, capture_output=True, text=True, check=True, timeout=300)
    return [json.loads(x) for x in out.stdout.splitlines() if x.strip()]


def _strip(r):
    return {k: v for k, v in r.items() if k not in TIMING}


def _by(rows, config):
    return {r["task_id"]: r for r in rows if r["config"] == config and not r.get("summary")}


@needs_bin
@pytest.mark.parametrize("decomp", [True, False])
def test_default_unchanged(tmp_path, decomp):
    cfg = [{"name": "base", "budget": 20000, "decomp": decomp}]
    old = _run(OLD, cfg, tmp_path)
    new = _run(NEW, cfg, tmp_path)
    assert [_strip(r) for r in old] == [_strip(r) for r in new]
    assert all("forbidden" not in r for r in new)


@needs_bin
def test_equivalence_patterns_keep_programs(tmp_path):
    rows = _run(NEW, [{"name": "base", "budget": 20000, "decomp": False},
                      {"name": "fb", "budget": 20000, "decomp": False, "forbid": EQUIV}], tmp_path)
    base, fb = _by(rows, "base"), _by(rows, "fb")
    assert sum(r["forbidden"] for r in fb.values()) > 0
    assert any(r["program"] for r in base.values())
    for t in TASKS:
        b, f = base[t], fb[t]
        assert f["program"] == b["program"], t
        assert (f["train_ok"], f["test_ok"]) == (b["train_ok"], b["test_ok"]), t
        if b["nodes_to_first"] is not None:
            assert f["nodes_to_first"] + f["forbidden"] == b["nodes_to_first"], t
    summ = [r for r in rows if r.get("summary") and r["config"] == "fb"][0]
    assert summ["forbidden"] == sum(r["forbidden"] for r in fb.values())


@needs_bin
def test_wildcards(tmp_path):
    t = ["007bbfb7"]  # unsolved: the whole budget is enumerated
    cfg = lambda name, pats: {"name": name, "budget": 20000, "decomp": False, "forbid": pats}
    rows = _run(NEW, [cfg("arity", [["add", "?x"]]),            # wrong arity: never matches
                      cfg("same", [["add", "?x", "?x"]]),        # only add(a, a)
                      cfg("any", [["add", "?x", "?y"]]),         # every add
                      cfg("cint", [["add", "?c", "?c2"]]),       # add of two int constants
                      cfg("cself", [["?c", "?x"]])], tmp_path, t)  # head is a STR: ?c never matches
    n = {r["config"]: r["forbidden"] for r in rows if not r.get("summary")}
    assert n["arity"] == 0 and n["cself"] == 0
    assert 0 < n["same"] < n["any"]
    assert 0 < n["cint"] < n["any"]
