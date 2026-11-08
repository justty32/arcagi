"""Training rescoring of candidates with the main-line generators' own scores.

Support (training only, never evaluation):

- ``transform``: tasks whose every train pair the program reproduces;
- ``extract``: ``gen_extract.targets`` / ``supports`` for the body's property
  (same-shape tasks: color only), as the extract generator scores;
- ``pred``: ``gen_predicates.segments`` - some connectivity's changed / kept
  objects match the predicate exactly; score = tasks - 0.5 x literals;
- ``formula``: ``gen_formula.problems`` the body holds on.

Verdict mirrors the generators' ``judge``: ``live`` when score > 0 and no
existing live / covered block of the same kind in ``aos/blocks/`` supports a
superset of tasks at no greater length, else ``covered`` (by that block) or
``dropped``; a transform supported by fewer than ``MIN_MACRO_TASKS`` tasks is
``solution_only`` (it solves its task but is no reusable macro). Written to
each candidate's ``_metainfo.json`` and returned.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from . import tasks as tk
from .candidates import all_folders
from .verify import _try, background

BLOCKS = tk.REPO_ROOT / "aos" / "blocks"
MIN_MACRO_TASKS = 3  # as library.find_macros: fewer tasks = a solution, not a block


def _tasks():
    from arcagi.tasks import load_tasks

    return load_tasks(tk.DATA_ROOT / "training")


def support_transform(body: list, raw: dict[str, dict]) -> set[str]:
    hit = set()
    for tid, task in raw.items():
        bg = background(task)
        if all(_try(body, i, bg)[0] == o for i, o in tk.pairs(task)):
            hit.add(tid)
    return hit


def support_extract(body: list, tasks) -> set[str]:
    from arcagi.blocks import gen_extract as ge
    from arcagi.dsl import extract as ex
    from arcagi.dsl import grid as g

    if isinstance(body, dict) and ex.is_object(body):
        from arcagi.objrule import gen as objgen

        ((_, ids),) = objgen.score(tasks, [ex.unwrap_object(body)])
        return set(ids)
    name, sel = ex.unwrap(body)
    hit = set()
    for task in tasks:
        pairs = [(e.input, e.output) for e in task.train]
        grid_task = any(g.shape(i) != g.shape(o) for i, o in pairs)
        if name != "color" and not grid_task:
            continue
        rows = ge.targets(pairs, name)
        if not rows[0]:
            continue
        try:
            values = [ex.prop(i, name, ex.select(i, sel)) for i, _ in pairs]
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        if ge.supports(values, rows, name):
            hit.add(task.task_id)
    return hit


def support_pred(body: list, segs) -> set[str]:
    return {s.task for s in segs if s.mask(body) == s.label}


def support_formula(body: list, probs) -> set[str]:
    from arcagi.dsl import formula as fm

    return {p.task for p in probs if fm.holds(body, p.xs, p.ys)}


def length(kind: str, body: object) -> float:
    from arcagi.dsl import extract as ex
    from arcagi.dsl import formula as fm
    from arcagi.dsl import predicates as pr
    from arcagi.dsl import program as pg

    if kind == "extract":
        return ex.length(body)
    if kind == "pred":
        return pr.literals(body)  # type: ignore[arg-type]
    if kind == "formula":
        return fm.length(body)  # type: ignore[arg-type]
    return pg.cost(tuple(tuple(s) for s in body))  # type: ignore[union-attr]


def existing(kind: str) -> list[tuple[str, set[str], float, object]]:
    """(name, support, length, body) of live / covered blocks of ``kind``."""
    out = []
    prefix = {"transform": "m_"}.get(kind, kind + "_")
    for meta_path in sorted(BLOCKS.glob(prefix + "*/_metainfo.json")):
        meta = json.loads(meta_path.read_text())
        if meta.get("status") == "retired":
            continue
        tasks = set(
            meta.get("support_tasks")
            or meta.get("tasks")
            or meta.get("source_tasks")
            or []
        )
        size = meta.get("length", meta.get("literals", meta.get("cost", 1)))
        rule = meta_path.parent / (
            "program.json" if kind == "transform" else "_rule.json"
        )
        body = json.loads(rule.read_text()) if rule.exists() else None
        body = body.get("body") if isinstance(body, dict) else body
        out.append((meta["name"], tasks, float(size), body))
    return out


def solved_r04() -> set[str]:
    """Training tasks the main-line r04 report solved (empty if absent)."""
    path = Path(str(tk.DEFAULT_REPORT).format(split="training"))
    if not path.exists():
        return set()
    return {t["task_id"] for t in json.loads(path.read_text())["tasks"] if t["correct"]}


def judge(kind: str, body: object, support: set[str]) -> dict:
    size = length(kind, body)
    score = len(support) - (0.5 * size if kind == "pred" else 0)
    verdict = {
        "support_tasks": sorted(support),
        "new_vs_r04": sorted(support - solved_r04()),
        "score": score,
        "length": size,
    }
    if score <= 0:
        return verdict | {"verdict": "dropped"}
    if kind == "transform" and len(support) < MIN_MACRO_TASKS:
        return verdict | {"verdict": "solution_only"}
    blocks = existing(kind)
    for name, _tasks, _size, other_body in blocks:
        if other_body == body:
            return verdict | {"verdict": "exists", "same_as": name}
    if kind == "pred" and isinstance(body, list) and body[:1] == ["eq"]:
        return verdict | {"verdict": "covered", "covered_by": "builtin selector"}
    for name, tasks, other, _body in blocks:
        if support <= tasks and other <= size:
            return verdict | {"verdict": "covered", "covered_by": name}
    return verdict | {"verdict": "live"}


def rescore(folders: Sequence[Path] | None = None) -> list[dict]:
    folders = [f.parent for f in all_folders()] if folders is None else list(folders)
    tasks = _tasks()
    raw = {t.task_id: tk.load(t.task_id, "training") for t in tasks}
    cache: dict[str, object] = {}
    results = []
    for folder in folders:
        rule = json.loads((folder / "_rule.json").read_text())
        kind, body = rule["kind"], rule["body"]
        if kind == "transform":
            sup = support_transform(body, raw)
        elif kind == "extract":
            sup = support_extract(body, tasks)
        elif kind == "pred":
            from arcagi.blocks import gen_predicates as gp

            segs = cache.setdefault("segs", gp.segments(tasks))
            sup = support_pred(body, segs)
        else:
            from arcagi.blocks import gen_formula as gf

            probs = cache.setdefault("probs", gf.problems(tasks))
            sup = support_formula(body, probs)
        res = judge(kind, body, sup)
        meta_path = folder / "_metainfo.json"
        meta = json.loads(meta_path.read_text())
        meta["rescore"] = res
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        results.append({"candidate": folder.name, "kind": kind} | res)
    return results
