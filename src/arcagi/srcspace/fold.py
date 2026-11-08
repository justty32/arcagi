"""Fold repeated step runs into ``$ref`` directives and back (aos N-45).

``fold_refs`` replaces every contiguous run of steps equal to a macro's steps
with ``{"$ref": path}`` (longest macro first, left to right). ``unfold_refs``
splices them back using the same resolver as ``blocks.catalog``.
"""

import json
import os
from pathlib import Path

from arcagi.blocks.catalog import expand_steps, load_catalog

from .emit import is_ref

type Steps = list


def _plain(value: object) -> object:
    """Tuples -> lists so trace programs compare equal to JSON programs."""
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def fold_refs(program: Steps, macros: dict[str, Steps]) -> Steps:
    """Replace runs equal to ``macros[path]`` by ``{"$ref": path}``.

    ``macros`` maps a ``$ref`` path to its fully expanded steps; runs shorter
    than two steps are never folded.
    """
    program = _plain(program)  # type: ignore[assignment]
    order = sorted(
        ((path, _plain(steps)) for path, steps in macros.items() if len(steps) >= 2),
        key=lambda kv: (-len(kv[1]), kv[0]),  # type: ignore[arg-type]
    )
    out: Steps = []
    i = 0
    while i < len(program):
        for path, steps in order:
            size = len(steps)  # type: ignore[arg-type]
            if program[i : i + size] == steps:
                out.append({"$ref": path})
                i += size
                break
        else:
            out.append(program[i])
            i += 1
    return out


def unfold_refs(program: Steps, base: Path) -> Steps:
    """Splice every ``$ref`` step (resolved relative to ``base``)."""
    return expand_steps(_plain(program), Path(base))  # type: ignore[return-value]


def macro_refs(
    root: Path | None = None, *, frm: Path | None = None
) -> dict[str, Steps]:
    """``$ref`` path (relative to ``frm``, default ``root/<x>``) -> expanded steps.

    Covers live and covered ``kind=macro`` blocks; the default path form is the
    one a sibling block folder writes: ``../m_x/program.json``.
    """
    catalog = load_catalog(root)
    if catalog.root is None:
        return {}
    found: dict[str, Steps] = {}
    for name, steps in catalog.macros(include_covered=True).items():
        folder = catalog.blocks[name].path
        rel = (
            Path("..") / folder.name / "program.json"
            if frm is None
            else Path(_relative(folder / "program.json", frm))
        )
        found[rel.as_posix()] = _plain(steps)  # type: ignore[assignment]
    return found


def _relative(target: Path, frm: Path) -> str:
    return os.path.relpath(target.resolve(), Path(frm).resolve())


def name_steps_to_refs(program: Steps, names: dict[str, str]) -> Steps:
    """Turn ``[macro_name]`` steps into ``{"$ref": names[macro_name]}``."""
    out: Steps = []
    for step in _plain(program):  # type: ignore[union-attr]
        if isinstance(step, list) and len(step) == 1 and step[0] in names:
            out.append({"$ref": names[step[0]]})
        else:
            out.append(step)
    return out


def node_count(value: object) -> int:
    """Nodes of the JSON tree; a ``$ref`` directive counts as one node."""
    if is_ref(value):
        return 1
    if isinstance(value, (list, tuple)):
        return 1 + sum(node_count(v) for v in value)
    if isinstance(value, dict):
        return 1 + sum(node_count(v) for v in value.values())
    return 1


def canonical(value: object) -> str:
    return json.dumps(_plain(value), separators=(",", ":"), ensure_ascii=False)
