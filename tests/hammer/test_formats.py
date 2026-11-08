from pathlib import Path

from arcagi.hammer import check
from arcagi.hammer import formats as fm

TASKSET = Path(__file__).resolve().parents[2] / "data" / "r08" / "taskset.json"


def test_init_root_passes_check(tmp_path):
    root = fm.init_root(tmp_path / "t", TASKSET)
    assert check.check_root(root) == []
    ops = fm.load_ops(root)
    assert {o["id"] for o in ops} >= {"gate_g1", "decomp_halves", "decomp_nest"}
    h = fm.env_hash(ops)
    ops[0]["payload"]["params"]["m"] = 5
    assert fm.env_hash(ops) != h


def test_check_catches_bad_op(tmp_path):
    root = fm.init_root(tmp_path / "t", TASKSET)
    ops = fm.load_ops(root)
    ops[0]["status"] = "alive"
    del ops[1]["tried_env_hashes"]
    fm.write_ops(root, ops)
    err = check.check_root(root)
    assert any("status alive" in e for e in err)
    assert any("tried_env_hashes" in e for e in err)
