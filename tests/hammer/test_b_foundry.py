"""r09 line B: a hand-written test-replay wax (P48 task 67e8384a) goes through
foundry.ingest and yields comb incubating rows (does not count for M2(c))."""

import json
import shutil
from pathlib import Path

import pytest

from arcagi.grow import prog as pg
from arcagi.hammer import formats as fm
from arcagi.hammer import foundry as fd

REPO = Path(__file__).resolve().parents[2]
WAX = REPO / "reports" / "curve-r09" / "foundry" / "test-wax-67e8384a.jsonl"


@pytest.mark.skipif(not (REPO / "native" / "bin" / "arcbatch").exists(),
                    reason="arcbatch not built")
def test_ingest_test_wax(tmp_path):
    root = fm.init_root(tmp_path / "t", REPO / "data" / "r09" / "taskset.json")
    wax = root / "foundry" / "wax" / WAX.name
    shutil.copy(WAX, wax)
    rows = fd.ingest(root, wax, epoch=0)
    assert len(rows) >= 1
    assert all(o["kind"] == "comb" and o["status"] == "incubating"
               and o["by"] == "foundry" and o["evidence"]["test_replay"]
               for o in rows)
    led = fm.load_ledger(root)[-1]
    assert led["kind"] == "foundry" and led["evals"]["llm_tax"] == 0
    assert fm.load_frozen(root)["priors"]
    assert fd.new_wax(root) == []


def test_hole_out():
    body, consts = fd.hole_out(("repeat", 7, ("repeat", 1, ("$in",))),
                               [[[0, 1], [1, 0]]])
    assert consts == [7]
    assert body == ("repeat", (pg.HOLE_PREFIX + "0",), ("repeat", 1, ("$in",)))
    assert json.dumps(body)
