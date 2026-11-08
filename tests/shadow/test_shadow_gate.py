"""Shadow gate: support, synthetic chunks, duplicates, macro loadability, gen_llm."""

import json
from pathlib import Path

from arcagi.blocks import gen_llm
from arcagi.blocks.catalog import load_catalog
from arcagi.shadow import gate
from arcagi.shadow.__main__ import main as shadow_main
from arcagi.shadow.blocks import from_rule, load_path
from arcagi.shadow.reference import confusion
from arcagi.shadow.support import views

FLIP = [
    ([[1, 2, 0], [0, 0, 3]], [[0, 2, 1], [3, 0, 0]]),
    ([[4, 0], [5, 6]], [[0, 4], [6, 5]]),
]
ROT = [  # 180-degree rotation: flip_lr fails on these
    ([[1, 2], [0, 3]], [[3, 0], [2, 1]]),
    ([[4, 0, 0], [0, 0, 5]], [[5, 0, 0], [0, 0, 4]]),
    ([[7, 8], [0, 0]], [[0, 0], [8, 7]]),
]


def _pair(p) -> dict:
    return {"input": p[0], "output": p[1]}


def _synth(root: Path, tasks: dict[str, tuple[list, list]]) -> Path:
    """A tiny data_synth: original pairs first, then synthetic ones."""
    (root / "training").mkdir(parents=True)
    manifest = {"tasks": {}}
    for tid, (orig, synth) in tasks.items():
        doc = {
            "train": [_pair(p) for p in orig + synth],
            "test": [{"input": orig[0][0], "output": orig[0][1]}],
        }
        (root / "training" / f"{tid}.json").write_text(json.dumps(doc))
        manifest["tasks"][tid] = {"n_original": len(orig), "n_synth": len(synth)}
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


def _macro(name: str, steps: list) -> dict:
    block = from_rule(name, {"kind": "transform", "body": steps})
    return load_path_like(block)


def load_path_like(block: dict) -> dict:
    block["program"] = block["rule"]["body"]
    block["body"] = block["program"]
    return block


def test_views_and_macro_gate(tmp_path: Path) -> None:
    # "good": synthetic pairs are flips too; "bad": synthetic pairs are rotations.
    synth = _synth(tmp_path / "s", {"good": (FLIP, FLIP * 3), "bad": (FLIP, ROT * 2)})
    orig, chunks = views(synth)
    assert [t.task_id for t in orig] == ["bad", "good"]
    assert len(chunks["good"]) == 2 and len(chunks["bad"][0].train) == 3
    flip = _macro("m_flip", [["flip_lr"]])
    learner = _macro("m_cm", [["colormap", [[1, 2]]]])
    (res, cm) = gate.run([flip, learner], orig, chunks, tmp_path / "noblocks")
    assert res["support"] == ["bad", "good"]
    assert res["chunk_rates"] == {"bad": 0.0, "good": 1.0}
    assert not res["pass"] and res["reasons"][0].startswith("synth majority 1/2")
    assert cm["reasons"][0].startswith("macro: steps not in registry")
    synth2 = _synth(tmp_path / "s2", {"good": (FLIP, FLIP * 3)})
    (res,) = gate.run([flip], *views(synth2), tmp_path / "noblocks")
    assert res["pass"] and res["synth_frac"] == 1.0


def test_duplicate_of() -> None:
    block = {"name": "llm_x", "kind": "formula", "body": ["lin", "h", 1, 0]}
    live = [
        {
            "name": "formula_a",
            "kind": "formula",
            "body": ["h"],
            "support": frozenset({"t"}),
        },
        {"name": "pred_b", "kind": "pred", "body": ["h"], "support": frozenset({"u"})},
    ]
    assert gate.duplicate_of(block, {"t"}, live) == "formula_a"
    assert gate.duplicate_of(block, {"u"}, live) is None
    same = {"name": "llm_y", "kind": "pred", "body": ["h"]}
    assert gate.duplicate_of(same, set(), live) == "pred_b"


def test_confusion() -> None:
    results = [
        {"name": "a", "support": ["t"], "reasons": []},
        {"name": "b", "support": ["t"], "reasons": ["synth majority 0/1 < 0.67"]},
        {"name": "c", "support": ["t"], "reasons": ["duplicate of live z"]},
    ]
    ref = {n: {"majority": n != "b", "strict": n == "a"} for n in "abc"}
    out = confusion(results, ref)
    assert out["majority"]["agreement"] == 1.0
    assert out["strict"]["good/bad"] == 1 and out["strict"]["n"] == 3


def test_gen_llm_writes_loadable_blocks(tmp_path: Path, capsys) -> None:
    synth = _synth(tmp_path / "s", {"good": (FLIP, FLIP * 3)})
    cands = tmp_path / "cands"
    for digest, rule in {
        "aaa": {
            "kind": "transform",
            "in": "grid",
            "out": "grid",
            "body": [["flip_lr"]],
        },
        "bbb": {
            "kind": "formula",
            "in": "features",
            "out": "int",
            "body": ["div", "h", 2],
        },
    }.items():
        (cands / digest).mkdir(parents=True)
        (cands / digest / "_rule.json").write_text(json.dumps(rule | {"source": "llm"}))
    root = tmp_path / "blocks"
    root.mkdir()
    argv = ["--candidates", str(cands), "--root", str(root), "--synth", str(synth)]
    assert gen_llm.main(argv + ["--out", str(tmp_path / "v.json")]) == 0
    report = json.loads((tmp_path / "v.json").read_text())
    assert report["written"] == ["llm_aaa"]
    catalog = load_catalog(root)
    block = catalog.blocks["llm_aaa"]
    assert block.kind == "macro" and block.status == "live"
    assert block.meta["source"] == "llm" and block.meta["origin"] == "aaa"
    assert catalog.macros() == {"llm_aaa": (("flip_lr",),)}
    assert load_path(root / "llm_aaa")["kind"] == "macro"
    # The shadow CLI re-reads the written folder and never writes blocks.
    assert (
        shadow_main([str(root), "--synth", str(synth), "--blocks-root", str(root)]) == 0
    )
    assert (
        "duplicate of live"
        not in capsys.readouterr().out.split("llm_aaa")[1].split("\n")[0]
    )
