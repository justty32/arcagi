import json

from arcagi.solvers import gated, guard
from arcagi.tasks import Example, SolverTask

A = ((1, 0), (0, 1))
B = ((0, 1), (1, 0))
C = ((2, 2), (2, 2))
TRAIN = [(((1, 1), (1, 1)), ((1, 1), (1, 1))), (((0, 0), (0, 0)), ((0, 0), (0, 0)))]
TEST_IN = [((1, 0), (0, 0))]


def cand(program, out, **kw):
    return guard.Candidate(program, (out,), "python", **kw)


def judge(cands, gates, **kw):
    return guard.judge(cands, TRAIN, TEST_IN, gates=gates, **kw)


def test_support_demotes_single_program_output():
    cands = [cand("p1", A), cand("p2", B), cand("p3", B)]
    v = judge(cands, {"support"})
    assert v.chosen.candidate.program == "p2"
    assert v.reason.startswith("switched")
    assert not v.abstained


def test_support_keeps_order_when_nothing_is_supported():
    v = judge([cand("p1", A), cand("p2", B)], {"support"})
    assert v.chosen.candidate.program == "p1" and v.reason == "kept"


def test_unseen_color_distrusts_and_abstains():
    v = judge([cand("p1", C)], {"unseen"})
    assert v.abstained and v.predictions == [[list(r) for r in TEST_IN[0]]]
    assert "unseen colors [2]" in v.ranked[0].reasons[0]


def test_unseen_allows_colors_from_test_input_or_train_outputs():
    assert guard.unseen_colors([A], [((0, 0),)], [((1, 1),)]) == set()
    assert guard.unseen_colors([C], [((0, 0),)], [((1, 1),)]) == {2}


def test_synth_drop_and_demote():
    cands = [
        cand("p1", A, synth_ok=3, synth_total=4),
        cand("p2", B, synth_ok=4, synth_total=4),
    ]
    dropped = judge(cands, {"synth"}, synth_demote=False)
    assert dropped.chosen.candidate.program == "p2"
    assert "synth 3/4" in dropped.ranked[1].reasons[0]
    alone = judge(cands[:1], {"synth"}, synth_demote=False)
    assert alone.abstained
    demoted = judge(cands[:1], {"synth"}, synth_demote=True)
    assert demoted.chosen.candidate.program == "p1"


def test_synth_inactive_without_pairs():
    v = judge([cand("p1", A)], {"synth"}, synth_demote=False)
    assert v.reason == "kept"


def test_table_gate_on_thin_rows():
    assert guard.memorizes((10, 6))
    assert not guard.memorizes((10, 5))  # exactly half is not a majority
    assert not guard.memorizes((3, 3))  # small tables are exempt
    assert not guard.memorizes(None)
    v = judge([cand("p1", A, table=(8, 8)), cand("p2", B)], {"table"})
    assert v.chosen.candidate.program == "p2"


def test_shape_law():
    keep = [(((0,),), ((1,),))]
    assert guard.shape_breaks([((1, 1),)], keep, [((0,),)]) == "train keeps input shape"
    assert guard.shape_breaks([((1,),)], keep, [((0,),)]) is None


def test_unknown_gate_rejected():
    try:
        judge([], {"nope"})
    except ValueError:
        return
    raise AssertionError


def test_no_candidates_abstains():
    assert judge([], guard.GATES).abstained


def _task():
    train = (Example(((1, 0),), ((2, 0),)), Example(((0, 1),), ((0, 2),)))
    return SolverTask("t", train, (((1, 1),),))


def test_evaluate_reruns_programs_and_synth():
    task = _task()
    progs = [('[["colormap", [[1, 2]]]]', "python"), ('[["flip_lr"]]', "cpp")]
    synth = [(((1,),), ((2,),)), (((1,),), ((3,),))]
    cands = gated.evaluate(task, progs, synth)
    assert len(cands) == 1  # flip_lr fails train on re-run and is dropped
    assert cands[0].tests == (((2, 2),),)
    assert (cands[0].synth_ok, cands[0].synth_total) == (1, 2)
    assert cands[0].table is None


def test_table_stats_counts_thin_rows():
    task = _task()
    # Key (1, -1, -1, -1, 0) changes once on train: a thin row.
    rows = [[1, -1, -1, -1, 0, 2], [1, -1, -1, 0, -1, 2], [9, 9, 9, 9, 9, 2]]
    prog = gated.from_json(json.dumps([["local_rule", "n4", rows]]))
    assert gated.table_stats(prog, [e.input for e in task.train], 0) == (3, 3)


def test_trace_programs_and_main(tmp_path):
    trace = {
        "metadata": {"source": "native"},
        "attempts": [
            {
                "kind": "program",
                "program": '[["colormap", [[1, 2]]]]',
                "data": {"origin": "cpp"},
            },
            {"kind": "near_miss", "program": "[]"},
        ],
    }
    assert gated.trace_programs(trace) == [('[["colormap", [[1, 2]]]]', "cpp")]
    task = {
        "train": [
            {"input": [[1, 0]], "output": [[2, 0]]},
            {"input": [[0, 1]], "output": [[0, 2]]},
        ],
        "test": [{"input": [[1, 1]]}],
    }
    request = tmp_path / "req.json"
    request.write_text(json.dumps({"task_id": "t", "task": task}))
    full = {
        "schema_version": "arcagi-trace/1",
        "attempts": [],
        "selected": None,
        **trace,
    }

    def runner(_req, out, trace_path):
        trace_path.write_text(json.dumps(full))

    out = tmp_path / "out.json"
    assert gated.main([str(request), str(out)], runner=runner) == 0
    assert json.loads(out.read_text()) == {"t": [[[2, 2]]]}
