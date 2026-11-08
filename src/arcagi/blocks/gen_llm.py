"""LLM "generator": shadow-gate S2 candidates and write passers as blocks.

Run: ``uv run python -m arcagi.blocks.gen_llm [--dry-run] [--out verdicts.json]``.
Reads ``aos/llm/candidates/<hash>/_rule.json`` (read only; four-kind shell
pred / extract / formula / transform), turns each into a shadow block named
``llm_<hash>`` (transform -> ``kind=macro`` with ``program.json``), runs the
shadow gate (``arcagi.shadow``: training support, synthetic-set majority,
no live duplicate) and writes each passer to ``aos/blocks/llm_<hash>/`` with
``source: llm`` and ``origin: <hash>``. Only adds or refreshes ``llm_*``
folders; nothing else under the blocks root is touched.
"""

import argparse
import json
import os
import time
from pathlib import Path

from arcagi.shadow import gate
from arcagi.shadow.blocks import load_path
from arcagi.shadow.support import views

from . import REPO_ROOT, default_blocks_root, read_json, write_json

GENERATOR = "_gen/llm"
CANDIDATES = REPO_ROOT / "aos" / "llm" / "candidates"
SHELL = {"pred": ("object", "bool"), "formula": ("features", "int")}
MACRO_ENTRY = """#!/bin/sh
# aos block entry: stdin {"grid": [[...]], "params": [...]} -> stdout grid JSON.
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
exec "$root/.venv/bin/python" -m arcagi.blocks.run "$(basename "$here")"
"""


def candidates(root: Path = CANDIDATES) -> list[dict]:
    """Shadow blocks of every candidate, with its rule and provenance."""
    out = []
    for rule_path in sorted(Path(root).glob("*/_rule.json")):
        rule = json.loads(rule_path.read_text())
        block = load_path(rule_path) if isinstance(rule, dict) else None
        if block is None:
            continue
        origin = rule_path.parent.name
        block["name"] = "llm_" + origin
        block["origin"] = origin
        block["candidate"] = rule
        block["candidate_meta"] = read_json(rule_path.parent / "_metainfo.json", {})
        out.append(block)
    return out


def _entry_script(kind: str) -> str:
    if kind == "macro":
        return MACRO_ENTRY
    from . import gen_extract, gen_formula, gen_predicates

    module = {"extract": gen_extract, "formula": gen_formula, "pred": gen_predicates}
    return module[kind].ENTRY_SCRIPT


def write_block(root: Path, block: dict, result: dict) -> Path:
    """Write ``llm_<hash>/`` as a live block the catalog loads by ``kind``."""
    folder = root / block["name"]
    old = read_json(folder / "_metainfo.json", {}) or {}
    rule, cand_meta = block["candidate"], block["candidate_meta"] or {}
    meta = {
        "name": block["name"],
        "kind": block["kind"],
        "doc": f"LLM candidate {block['origin']} ({rule['kind']}) "
        + json.dumps(block["body"], separators=(",", ":"))[:200],
        "params": [],
        "cost": 1,
        "status": "live",
        "counter_uses": old.get("counter_uses", 0),  # type: ignore[union-attr]
        "generator": GENERATOR,
        "source": "llm",
        "origin": block["origin"],
        "model": rule.get("model"),
        "prompt_hash": rule.get("prompt_hash"),
        "llm_origin": cand_meta.get("origin", []),  # type: ignore[union-attr]
        "score": len(result["support"]),
        "support_tasks": result["support"],
        "shadow": {k: result[k] for k in ("synth_ok", "synth_frac")},
    }
    write_json(folder / "_metainfo.json", meta)
    if block["kind"] == "macro":
        write_json(folder / "program.json", block["program"])
    else:
        shell = {"kind": block["kind"], "in": rule.get("in"), "out": rule.get("out")}
        if block["kind"] in SHELL:
            shell["in"], shell["out"] = SHELL[block["kind"]]
        write_json(folder / "_rule.json", shell | {"body": block["body"]})
    entry = folder / "_entry"
    entry.write_text(_entry_script(block["kind"]), encoding="utf-8")
    os.chmod(entry, 0o755)
    return folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow-gate LLM candidates.")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--root", type=Path, default=None, help="blocks root")
    parser.add_argument("--synth", type=Path, default=REPO_ROOT / "data_synth")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    start = time.monotonic()
    root = args.root or default_blocks_root()
    blocks = candidates(args.candidates)
    orig, chunks = views(args.synth)
    results = gate.run(blocks, orig, chunks, root)
    written = []
    for block, result in zip(blocks, results, strict=True):
        result["origin"] = block["origin"]
        result["llm_kind"] = block["candidate"]["kind"]
        if result["pass"] and not args.dry_run:
            written.append(write_block(root, block, result).name)
    report = {
        "schema": "arcagi-gen-llm/1",
        "summary": gate.summary(results),
        "written": written,
        "seconds": round(time.monotonic() - start, 2),
        "results": results,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(gate.table(results))
    print(json.dumps(report["summary"] | {"written": written}))
    return 0


__all__ = ["candidates", "main", "write_block"]

if __name__ == "__main__":
    raise SystemExit(main())
