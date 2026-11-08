"""Shared subtree mining, slot anti-unification and block promotion."""

import json

from arcagi.blocks.catalog import load_catalog, load_macro_program
from arcagi.srcspace import (
    promote,
    shared_slot_subtrees,
    shared_subtrees,
    slot_primitives,
)
from arcagi.srcspace.slots import fold_slots, promote_slots, slot_combos
from arcagi.srcspace.subtree import has_task_constant

A = ("flip_lr",)
B = ("crop_object", "4same", "smallest")


def _programs():
    return {
        "t1": [(A, B, ("upscale", 2, 2))],
        "t2": [(A, B, ("upscale", 3, 3)), (("crop_bbox",),)],
        "t3": [(("rot90",), A, B)],
        "t4": [(A, ("crop_object", "8multi", "largest"))],
    }


def test_shared_subtrees_plain():
    subs = shared_subtrees(_programs(), 3)
    assert [s.steps for s in subs] == [(A, B)]
    assert subs[0].tasks == ("t1", "t2", "t3")
    assert subs[0].status == "live"
    assert shared_subtrees(_programs(), 3, macros={"m_ab": (A, B)}) == []


def test_task_constants_rejected():
    assert has_task_constant(("resize_crop", 3, 3))
    assert has_task_constant(("paint", [[1, 2, 3]] * 3))
    assert not has_task_constant(("upscale", 3, 3))
    progs = {t: [(A, ("canvas", 3, 3, 0))] for t in ("a", "b", "c")}
    assert shared_subtrees(progs, 3) == []


def test_covered_when_cheaper_program_exists():
    heads = {"a": ("rot90",), "b": ("rot180",), "c": ("flip_ud",)}
    progs = {t: [(h, A, B), (("crop_bbox",),)] for t, h in heads.items()}
    assert shared_subtrees(progs, 3)[0].status == "covered"


def test_slot_subtrees_and_primitive(tmp_path):
    subs = shared_slot_subtrees(_programs(), 3)
    sub = next(s for s in subs if s.template[0] == ["flip_lr"])
    assert sub.template == [["flip_lr"], ["crop_object", {"$slot": 1}, {"$slot": 2}]]
    assert sub.tasks == ("t1", "t2", "t3", "t4")
    folder = promote_slots(sub, root=tmp_path)
    meta = json.loads((folder / "_metainfo.json").read_text())
    assert meta["kind"] == "slot_macro" and meta["params"] == ["$1", "$2"]
    assert slot_combos(meta)[0] == ("4same", "smallest")
    assert len(slot_combos(meta, 3)) == 3
    catalog = load_catalog(tmp_path)
    assert catalog.macros() == {}  # not a plain macro
    prims = slot_primitives(catalog)
    prim = prims[folder.name]
    grid = ((0, 0, 0), (0, 5, 0), (0, 0, 0))
    assert prim.apply(grid, "4same", "smallest") == ((5,),)
    assert ("4same", "smallest") in prim.candidates([grid], [((5,),)])
    folded = fold_slots(
        [["flip_lr"], ["crop_object", "8multi", "largest"]], {folder.name: sub.template}
    )
    assert folded == [[folder.name, "8multi", "largest"]]


def test_promote_writes_ref_to_existing_macro(tmp_path):
    (tmp_path / "m_a").mkdir()
    (tmp_path / "m_a" / "program.json").write_text('[["flip_lr"],["rot90"]]')
    (tmp_path / "m_a" / "_metainfo.json").write_text('{"name":"m_a","kind":"macro"}')
    sub = shared_subtrees(
        {t: [(("flip_lr",), ("rot90",), ("rot180",))] for t in "abc"}, 3
    )[0]
    folder = promote(
        sub, root=tmp_path, macros={"../m_a/program.json": [["flip_lr"], ["rot90"]]}
    )
    assert json.loads((folder / "program.json").read_text()) == [
        {"$ref": "../m_a/program.json"},
        ["rot180"],
    ]
    assert load_macro_program(folder) == (("flip_lr",), ("rot90",), ("rot180",))
    assert load_catalog(tmp_path).blocks[folder.name].kind == "macro"
