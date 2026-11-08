import json

import arcagi.seed as seed
from arcagi.seed import Block, Library, run, solve
from arcagi.seed.types import parse
from arcagi.tasks import task_from_dict

A = ((1, 2, 3), (4, 5, 6))
B = ((7, 8), (9, 0), (1, 1))
C = ((3, 1, 4, 1), (5, 9, 2, 6), (5, 3, 5, 8))

LR = Block(
    name="b_lr",
    body=("map", ("lam", 1, ("reverse", ("$0",))), ("$h0",)),
    sig=parse("(list[list[int]]) -> list[list[int]]"),
    src_tasks=("t1",),
    saving=3.0,
    uses=2,
)
REV_FN = Block(
    name="b_revfn",
    body=("lam", 1, ("reverse", ("$0",))),
    sig=parse("(list[int]) -> list[int]"),
)
INSIDE = Block(  # hole under a lambda: filled syntactically, may use $0
    name="b_mapper",
    body=("map", ("lam", 1, ("$h0",)), ("$in",)),
    sig=parse("(list[int]) -> list[list[int]]"),
)


def rot2(g):
    return tuple(r[::-1] for r in g[::-1])


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "seedlib" / "blocks.json"
    Library([LR, REV_FN]).save(path)
    data = json.loads(path.read_text())
    assert data[0]["body"] == ["map", ["lam", 1, ["reverse", ["$0"]]], ["$h0"]]
    assert data[0]["sig"] == "(list[list[int]]) -> list[list[int]]"
    lib = Library.load(path)
    assert lib.blocks == [LR, REV_FN]
    assert LR.holes == 1 and REV_FN.holes == 0


def test_empty_and_missing(tmp_path):
    assert len(Library.load(tmp_path / "nope.json")) == 0
    p = tmp_path / "blocks.json"
    p.write_text("[]")
    assert len(Library.load(p)) == 0


def test_block_runs_with_syntactic_holes():
    lib = Library([LR, INSIDE])
    assert run(("blk", "b_lr", ("$in",)), A, lib) == ((3, 2, 1), (6, 5, 4))
    prog = ("blk", "b_mapper", ("sort", ("$0",)))
    assert run(prog, C, lib) == ((1, 1, 3, 4), (2, 5, 6, 9), (3, 5, 5, 8))


def test_holed_block_used_by_enumerator():
    train = [(A, rot2(A)), (B, rot2(B))]
    base = solve(train, Library(), 50_000)
    with_lib = solve(train, Library([LR]), 50_000)
    assert with_lib.program is not None and "blk" in repr(with_lib.program)
    assert run(with_lib.program, C, Library([LR])) == rot2(C)
    assert with_lib.nodes < base.nodes


def test_function_block_used_as_lambda():
    lib = Library([REV_FN])
    train = [(A, tuple(r[::-1] for r in A)), (B, tuple(r[::-1] for r in B))]
    res = solve(train, lib, 50_000)
    assert res.program == ("map", ("blk", "b_revfn"), ("$in",))


def _task(tid, pairs, test):
    return task_from_dict(
        {
            "train": [{"input": i, "output": o} for i, o in pairs],
            "test": [{"input": i, "output": o} for i, o in test],
        },
        task_id=tid,
    )


def test_enumerate_deterministic_with_workers():
    lr = [[[1, 2], [3, 4]], [[2, 1], [4, 3]]]
    tasks = [
        _task(
            "ud",
            [([[1, 2], [3, 4]], [[3, 4], [1, 2]]), ([[5, 6, 7]], [[5, 6, 7]])],
            [([[1], [2]], [[2], [1]])],
        ),
        _task("lr", [tuple(lr), ([[5, 6, 7]], [[7, 6, 5]])], [([[1, 0]], [[0, 1]])]),
        _task("hard", [([[1]], [[2, 3], [4, 5]]), ([[2]], [[9]])], [([[3]], [[1]])]),
    ]
    lib = Library([LR])
    one = seed.enumerate(lib, tasks, 5_000, workers=1)
    two = seed.enumerate(lib, tasks, 5_000, workers=2)
    key = [
        (s.task_id, s.program, s.train_ok, s.test_ok, s.nodes, s.nodes_to_first, s.near)
        for s in one
    ]
    assert key == [
        (s.task_id, s.program, s.train_ok, s.test_ok, s.nodes, s.nodes_to_first, s.near)
        for s in two
    ]
    assert [s.task_id for s in one] == ["ud", "lr", "hard"]
    assert one[0].test_ok and one[1].test_ok and not one[2].train_ok
    assert one[2].nodes == 5_000


ROT2 = Block(  # expanded size 5, enumerated as a single node
    name="b_rot2",
    body=("reverse", ("map", ("lam", 1, ("reverse", ("$0",))), ("$in",))),
    sig=parse("list[list[int]]"),
)


def test_blocks_cost_one_node():
    from arcagi.seed.enum import Enumerator
    from arcagi.seed.lam import leaf_entries

    assert seed.size(("blk", "b_lr", ("$in",))) == 2
    assert seed.size(("blk", "b_rot2")) == 1
    train = [(A, rot2(A)), (B, rot2(B))]
    res = solve(train, Library([ROT2]), 50_000)
    assert res.program == ("blk", "b_rot2")
    en = Enumerator(train, Library([LR]), 10**9)
    en.bank.append({})
    for prog, typ, vals in leaf_entries(
        en.lib, en.xs, en.in_type, en.consts, en._run_expanded
    ):
        en._offer(1, prog, typ, vals)
    en.bank.append({})
    for op in en.ops:
        if op.name == "b_lr":
            en._apply(2, op, (1,))
    progs = [e.prog for es in en.bank[2].values() for e in es]
    assert ("blk", "b_lr", ("$in",)) in progs
