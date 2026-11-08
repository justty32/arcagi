"""C++ seed language (``arcbatch --mode seed|seed-run|seed-sub``) against the
Python reference ``arcagi.seed``: golden primitives, bank-program values and
whole-task enumeration (program, nodes, nodes_to_first, near)."""

import json
import subprocess
from pathlib import Path

import pytest

from arcagi.seed import enum as S_enum
from arcagi.seed import interp
from arcagi.seed.library import Library

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "native" / "bin" / "arcbatch"
DATA = ROOT / "data" / "ARC-AGI" / "data" / "training"
needs_bin = pytest.mark.skipif(not BIN.exists(), reason="run make -C native")
TASKS = ["68b16354", "beb8660c", "1e0a9b12", "d10ecb37", "44f52bb0", "ce4f8723"]


def _arcbatch(*args):
    out = subprocess.run([str(BIN), *map(str, args)], capture_output=True, text=True,
                         check=True, timeout=300)
    return out.stdout


def _jsonl(text):
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def _norm(v):
    return [_norm(x) for x in v] if isinstance(v, tuple) else v


@needs_bin
def test_golden_prims(tmp_path):
    gold = json.loads((ROOT / "tests" / "seed" / "golden_prims.json").read_text())
    cases = [c for cs in gold["cases"].values() for c in cs]
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text("".join(json.dumps({"id": i, "program": c["program"],
                                        "inputs": [c["input"]]}) + "\n"
                            for i, c in enumerate(cases)))
    got = _jsonl(_arcbatch("--batch", "--mode", "seed-run", "--programs", jobs))
    bad = [(c["program"], c["output"], g["values"][0]) for c, g in zip(cases, got)
           if g["values"][0] != c["output"]
           or type(g["values"][0]) is not type(c["output"])]
    assert len(got) == len(cases) == 747
    assert not bad, bad[:5]


@needs_bin
def test_bank_programs_match_python(tmp_path):
    jobs, expect = [], []
    for tid in TASKS:
        t = json.loads((DATA / f"{tid}.json").read_text())
        en = S_enum.Enumerator([(e["input"], e["output"]) for e in t["train"]],
                               Library(), 3000)
        S_enum.search(en)
        inputs = [e["input"] for e in t["train"] + t["test"]]
        for level in en.bank:
            for es in level.values():
                for e in es[:40]:
                    vals = []
                    for x in inputs:
                        try:
                            vals.append(_norm(interp.run(e.prog, x)))
                        except interp.EvalError:
                            vals.append("ERR")
                    jobs.append({"id": len(jobs), "program": interp.to_json(e.prog),
                                 "inputs": inputs})
                    expect.append(vals)
    p = tmp_path / "jobs.jsonl"
    p.write_text("".join(json.dumps(j) + "\n" for j in jobs))
    got = _jsonl(_arcbatch("--batch", "--mode", "seed-run", "--programs", p))
    assert [g["values"] for g in got] == expect


@needs_bin
@pytest.mark.parametrize("decomp", [False, True])
def test_whole_task_matches_python(tmp_path, decomp):
    lst = tmp_path / "tasks.txt"
    lst.write_text("\n".join(TASKS) + "\n")
    cfg = tmp_path / "c.jsonl"
    cfg.write_text(json.dumps({"name": "c", "budget": 30000, "decomp": decomp}) + "\n")
    rows = _jsonl(_arcbatch("--batch", "--mode", "seed", "--tasks", lst, "--data-dir", DATA,
                            "--configs", cfg, "--threads", 2))
    by = {r["task_id"]: r for r in rows if not r.get("summary")}
    for tid in TASKS:
        t = json.loads((DATA / f"{tid}.json").read_text())
        res = S_enum.solve([(e["input"], e["output"]) for e in t["train"]], Library(),
                           30000, None, decompose=decomp)
        c = by[tid]
        assert c["program"] == (interp.to_json(res.program) if res.program else None), tid
        assert (c["nodes"], c["nodes_to_first"]) == (res.nodes, res.nodes_to_first), tid
        assert c["near"] == [[interp.to_json(p), s] for p, s in res.near], tid


@needs_bin
def test_seed_sub_matches_enumerator(tmp_path):
    """One zip_pos-like subproblem with an extra leaf, sub=True, and cond."""
    from arcagi.seed.cond import cond_witness
    from arcagi.seed.types import INT, parse

    xs = [3, 5, 0, 2, 7]
    outs = [4, 6, 1, 3, 8]
    pos = [0, 1, 2, 3, 4]
    consts = (-1, 0, 1, 2)
    en = S_enum.Enumerator(list(zip(xs, outs)), Library(), 500, None,
                           in_type=INT, out_type=INT,
                           extra=((("$i",), INT, tuple(pos)),), sub=True, consts=consts)
    S_enum.search(en)
    job = {"id": "s", "budget": 500, "examples": [[x, y] for x, y in zip(xs, outs)],
           "in_type": "int", "out_type": "int",
           "extra": [{"leaf": "$i", "type": "int", "vals": pos}],
           "sub": True, "consts": list(consts), "cond_limit": 50}
    p = tmp_path / "sub.jsonl"
    p.write_text(json.dumps(job) + "\n")
    (got,) = _jsonl(_arcbatch("--batch", "--mode", "seed-sub", "--subproblems", p))
    assert got["program"] == (interp.to_json(en.found) if en.found else None)
    assert got["nodes"] == en.nodes
    if en.found is None:
        prog, used = cond_witness(en, 50)
        assert got["cond"]["used"] == used
    assert parse("int") == INT
