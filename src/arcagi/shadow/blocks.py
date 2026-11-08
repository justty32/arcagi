"""Load shadow inputs: block folders or bare ``_rule.json`` files, and live blocks.

A shadow block is a dict ``{name, kind, status, rule, program, body}``:
``rule`` is the four-kind shell (pred / extract / formula), ``program`` the
step list of a macro, ``body`` whichever of the two identifies it. A
``transform`` rule (LLM shell) becomes a ``macro``.
"""

import json
from pathlib import Path

from arcagi.blocks.catalog import RefError, expand_steps

from . import KINDS


def from_rule(name: str, rule: dict, status: str = "candidate") -> dict | None:
    """Shadow block from a four-kind rule dict; None for unknown kinds."""
    kind = rule.get("kind")
    if kind == "transform":
        steps = rule.get("body")
        if not isinstance(steps, list):
            return None
        return {"name": name, "kind": "macro", "status": status, "rule": rule}
    if kind not in KINDS:
        return None
    return {"name": name, "kind": kind, "status": status, "rule": rule}


def _finish(block: dict) -> dict:
    if block["kind"] == "macro":
        steps = block.get("program", block["rule"].get("body"))
        block["program"] = [list(s) for s in steps]
        block["body"] = block["program"]
    else:
        block["body"] = block["rule"].get("body")
    return block


def load_path(path: Path) -> dict | None:
    """One block from a folder (``_metainfo.json`` + rule / program) or a rule file."""
    path = Path(path)
    if path.is_file():
        rule = json.loads(path.read_text())
        name = path.parent.name if path.name == "_rule.json" else path.stem
        block = from_rule(name, rule) if isinstance(rule, dict) else None
        return _finish(block) if block else None
    meta_path = path / "_metainfo.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    name, status = meta.get("name", path.name), meta.get("status", "candidate")
    program = path / "program.json"
    if meta.get("kind") == "macro" or program.is_file():
        try:
            steps = expand_steps(json.loads(program.read_text()), path)
        except (OSError, ValueError, RefError):
            return None
        if not isinstance(steps, list):
            return None
        block = {"name": name, "kind": "macro", "status": status, "rule": {}}
        return _finish(block | {"program": steps, "meta": meta})
    rule_path = path / "_rule.json"
    if not rule_path.is_file():
        return None
    rule = json.loads(rule_path.read_text())
    block = from_rule(name, rule, status) if isinstance(rule, dict) else None
    return _finish(block | {"meta": meta}) if block else None


def load_paths(paths: list[Path]) -> tuple[list[dict], list[str]]:
    """Blocks from every path (a folder of folders expands); unreadable paths."""
    blocks, bad = [], []
    for path in paths:
        path = Path(path)
        if path.is_dir() and not (path / "_metainfo.json").exists():
            if not (path / "_rule.json").exists():
                inner = sorted(p for p in path.iterdir() if p.is_dir())
                found, miss = load_paths(inner)
                blocks += found
                bad += miss
                continue
        block = load_path(path)
        if block is None:
            bad.append(str(path))
        else:
            blocks.append(block)
    return blocks, bad


def live_index(root: Path) -> list[dict]:
    """Live blocks of a gated kind under ``root``, with their recorded support."""
    out = []
    for folder in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        if not (folder / "_metainfo.json").is_file():
            continue
        try:
            block = load_path(folder)
        except (OSError, ValueError):
            continue
        if block is None or block["status"] != "live":
            continue
        meta = block.get("meta", {})
        tasks = meta.get("support_tasks") or meta.get("tasks") or []
        block["support"] = frozenset(tasks)
        out.append(block)
    return out


def loadable(block: dict) -> str | None:
    """Why the catalog / registry could not use the block, else None."""
    if block["kind"] != "macro":
        return None
    from arcagi.dsl.registry import ALL

    steps = block["program"]
    if not steps or not all(
        isinstance(s, list) and s and isinstance(s[0], str) for s in steps
    ):
        return "macro: malformed steps"
    missing = sorted({s[0] for s in steps if s[0] not in ALL})
    return f"macro: steps not in registry {missing}" if missing else None


__all__ = ["from_rule", "live_index", "load_path", "load_paths", "loadable"]
