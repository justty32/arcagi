"""Block folders: catalog loading, status filtering, macros, sync and run."""

import json
import subprocess
import sys
from pathlib import Path

from arcagi.blocks import REPO_ROOT
from arcagi.blocks.catalog import load_catalog
from arcagi.blocks.run import apply_block
from arcagi.blocks.sync import sync


def _block(root: Path, name: str, **meta) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "_metainfo.json").write_text(json.dumps({"name": name, **meta}))
    return folder


def test_missing_root_gives_empty_catalog(tmp_path: Path) -> None:
    catalog = load_catalog(tmp_path / "nope")
    assert catalog.root is None and not catalog.blocks
    assert catalog.status("flip_lr") == "live" and not catalog.retired
    assert catalog.macros() == {}


def test_status_and_retired_filter(tmp_path: Path) -> None:
    _block(tmp_path, "flip_lr", kind="primitive", status="live", cost=2)
    _block(tmp_path, "gravity", kind="primitive", status="retired")
    _block(tmp_path, "odd", kind="primitive", status="weird", extra=1)
    (tmp_path / "broken").mkdir()
    catalog = load_catalog(tmp_path)
    assert catalog.retired == {"gravity"}
    assert catalog.status("odd") == "live"
    assert catalog.cost("flip_lr") == 2.0 and catalog.cost("unknown") == 1.0
    assert "broken" not in catalog.blocks


def test_macros_load_program_and_skip_covered(tmp_path: Path) -> None:
    live = _block(tmp_path, "m_a", kind="macro", status="live")
    (live / "program.json").write_text('[["rot90"],["upscale",2,2]]')
    covered = _block(tmp_path, "m_b", kind="macro", status="covered")
    (covered / "program.json").write_text('[["flip_lr"]]')
    gone = _block(tmp_path, "m_c", kind="macro", status="retired")
    (gone / "program.json").write_text('[["flip_ud"]]')
    catalog = load_catalog(tmp_path)
    assert catalog.macros() == {"m_a": (("rot90",), ("upscale", 2, 2))}
    assert set(catalog.macros(include_covered=True)) == {"m_a", "m_b"}


def test_sync_preserves_status_and_counters(tmp_path: Path) -> None:
    sync(tmp_path)
    meta_path = tmp_path / "flip_lr" / "_metainfo.json"
    meta = json.loads(meta_path.read_text())
    assert meta["kind"] == "primitive" and meta["status"] == "live"
    assert (
        json.loads((tmp_path / "colormap" / "_metainfo.json").read_text())["kind"]
        == "learner"
    )
    meta.update(status="retired", counter_uses=7, note="keep")
    meta_path.write_text(json.dumps(meta))
    sync(tmp_path)
    again = json.loads(meta_path.read_text())
    assert (again["status"], again["counter_uses"], again["note"]) == (
        "retired",
        7,
        "keep",
    )
    assert (tmp_path / "flip_lr" / "_entry").stat().st_mode & 0o111


def test_run_primitive_learner_and_macro(tmp_path: Path) -> None:
    assert apply_block("flip_lr", ((1, 2),), []) == ((2, 1),)
    assert apply_block("colormap", ((1, 0),), [[[1, 5]]]) == ((5, 0),)
    macro = _block(tmp_path, "m_x", kind="macro")
    (macro / "program.json").write_text('[["flip_lr"],["upscale",1,2]]')
    assert apply_block("m_x", ((1, 2),), [], tmp_path) == ((2, 2, 1, 1),)


def test_run_module_cli() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "arcagi.blocks.run", "rot90"],
        input='{"grid":[[1,2]],"params":[]}',
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    assert json.loads(completed.stdout) == [[1], [2]]


def test_catalog_import_does_not_pull_registry() -> None:
    code = (
        "import sys, arcagi.blocks.catalog; "
        "assert 'arcagi.dsl.registry' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True, cwd=REPO_ROOT)
