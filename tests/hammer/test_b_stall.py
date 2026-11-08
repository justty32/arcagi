"""r09 line B: stall judge replays r08 curves (reports/curve-r09/stall-replay)."""

from pathlib import Path

from arcagi.hammer import stall

R08 = Path(__file__).resolve().parents[2] / "reports" / "curve-r08"


def test_pool_starves():
    rows = stall.r08_curve_rows(R08 / "pool" / "curve.csv")
    assert stall.judge_stall(rows) == "starve"


def test_meta_saturates():
    rows = stall.r08_meta_rows(R08 / "meta" / "rounds.json")
    assert stall.judge_stall(rows) == "saturate"


def test_stop_and_ok():
    flat = [{"kind": "epoch", "epoch": i,
             "after": {"solved_L": 4, "solved_H24": 1, "lib_bits": 3.0,
                       "gate_in": 2, "near_best_L": 0.5}} for i in range(3)]
    assert stall.judge_stall(flat) == "stop"
    assert stall.judge_stall(flat[:2]) == "ok"
    flat[2]["after"]["solved_L"] = 5
    assert stall.judge_stall(flat) == "ok"
