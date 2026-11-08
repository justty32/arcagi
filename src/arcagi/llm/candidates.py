"""Candidate blocks from train-passing LLM rules (``aos/llm/candidates/<hash>/``).

Each folder has ``_rule.json`` (the four-kind shell, exactly what a block in
``aos/blocks/`` would hold) and ``_metainfo.json`` (provenance: ``source``
``"llm"``, origin tasks, model; ``rescore`` adds training support). A passing
transform also yields its inline sub-rules (extract bodies, predicate ASTs,
formula bodies) as separate candidates, since those are the reusable parts.
"""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

from . import LLM_ROOT
from .verify import SHELL

ROOT = LLM_ROOT / "candidates"


def digest(kind: str, body: object) -> str:
    text = kind + ":" + json.dumps(body, separators=(",", ":"), sort_keys=True)
    return hashlib.sha1(text.encode()).hexdigest()[:10]


def shell(kind: str, body: object) -> dict:
    inp, out = SHELL[kind]
    if (
        kind == "extract"
        and isinstance(body, list)
        and body[:1] in (["subgrid"], ["object"])
    ):
        out = "grid"
    return {"kind": kind, "in": inp, "out": out, "body": body}


def components(program: list) -> Iterator[tuple[str, object]]:
    """Inline (kind, body) sub-rules inside a program's step parameters."""
    from arcagi.dsl import extract as ex
    from arcagi.dsl import formula as fm
    from arcagi.dsl import predicates as pr

    def walk(node: object, top: bool) -> Iterator[tuple[str, object]]:
        if not isinstance(node, (list, dict)):
            return
        if not top:
            if isinstance(node, dict) and ex.is_object(node):
                try:
                    yield "extract", ex.unwrap_object(node)
                except (ValueError, KeyError, TypeError):
                    pass
                return
            if ex.validate(node):
                yield "extract", node
            elif isinstance(node, list) and node[:1] != ["const"] and fm.validate(node):
                yield "formula", node
            elif isinstance(node, list) and pr.validate(node) and _is_pred(node):
                yield "pred", node
        kids = node.values() if isinstance(node, dict) else node
        for kid in kids:
            yield from walk(kid, False)

    for step in program:
        for param in step[1:]:
            yield from walk(param, False)


def _is_pred(node: list) -> bool:
    return bool(node) and node[0] in (
        "eq",
        "ne",
        "gt",
        "lt",
        "rank",
        "and",
        "or",
        "not",
    )


def write(
    kind: str, body: object, *, task_id: str, split: str, model: str, role: str
) -> Path:
    """Create or extend the candidate folder; returns it."""
    folder = ROOT / digest(kind, body)
    folder.mkdir(parents=True, exist_ok=True)
    rule = folder / "_rule.json"
    if not rule.exists():
        rule.write_text(json.dumps(shell(kind, body), indent=2) + "\n")
    meta_path = folder / "_metainfo.json"
    meta = (
        json.loads(meta_path.read_text())
        if meta_path.exists()
        else {
            "name": "llm_" + folder.name,
            "kind": kind,
            "source": "llm",
            "status": "candidate",
            "origin": [],
        }
    )
    entry = {"task": task_id, "split": split, "model": model, "role": role}
    if entry not in meta["origin"]:
        meta["origin"].append(entry)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return folder


def emit(
    rule: dict, program: list, *, task_id: str, split: str, model: str
) -> list[str]:
    """Write the rule and its components; returns candidate folder names."""
    made = [
        write(
            rule["kind"],
            rule["body"],
            task_id=task_id,
            split=split,
            model=model,
            role="solution",
        ).name
    ]
    for kind, body in components(program):
        made.append(
            write(
                kind, body, task_id=task_id, split=split, model=model, role="component"
            ).name
        )
    return sorted(set(made))


def all_folders() -> list[Path]:
    return sorted(p for p in ROOT.glob("*/_rule.json")) if ROOT.exists() else []
