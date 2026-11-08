"""Synthetic-set majority check for generated blocks (soft plug-in of S5's set).

``data_synth/training/<id>.json`` holds each task's original train pairs first
(``manifest.json``: ``n_original``) then 24 synthetic pairs, cut here into
``CHUNKS`` resamples of ``CHUNK`` pairs (the size of a real task). A claim
(block, task in its training support) *passes* when the block, judged by its
generator's own rule, still supports the task on at least ``MAJORITY`` of the
chunks. ``apply_majority`` narrows every candidate's support to passing tasks
before the generator judges; blocks with ledger income are only flagged
(``synth_protected``), never narrowed, so the threshold cannot retire them.
Evaluation is never read.
"""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from arcagi.tasks import Task, load_tasks

from . import REPO_ROOT

DEFAULT_ROOT = REPO_ROOT / "data_synth"
CHUNK = 3
CHUNKS = 8
MAJORITY = 0.5


@dataclass
class Views:
    """Synthetic chunks: ``chunks[k][task_id]`` is a ``CHUNK``-pair task."""

    chunks: list[dict[str, Task]]
    narrow: bool = True  # False: rate and flag only (ablation "no threshold")


def load(root: Path | None = None) -> Views | None:
    """Chunks of ``root`` (default ``data_synth``), or None when it is absent."""
    root = Path(root) if root is not None else DEFAULT_ROOT
    if not (root / "manifest.json").is_file():
        return None
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    chunks: list[dict[str, Task]] = [{} for _ in range(CHUNKS)]
    for task in load_tasks(root / "training"):
        n = manifest["tasks"][task.task_id]["n_original"]
        pairs = task.train[n:]
        for k in range(min(len(pairs) // CHUNK, CHUNKS)):
            part = pairs[k * CHUNK : (k + 1) * CHUNK]
            chunks[k][task.task_id] = Task(task.task_id, part, task.test)
    return Views(chunks)


def _union(cands: Iterable) -> set[str]:
    return set().union(*(set(c.tasks) for c in cands))


def _tally(cands: Sequence, hits: list[dict[str, set[str]]]) -> dict:
    """name -> {task: pass rate} from per-chunk ``hits[k][name]`` task sets."""
    return {
        c.name: {t: sum(t in h.get(c.name, ()) for h in hits) / CHUNKS for t in c.tasks}
        for c in cands
    }


def formula_rates(cands: Sequence, views: Views, extracts: dict) -> dict:
    from arcagi.dsl import formula as fm

    from . import gen_formula as gf  # lazy: the generators import this module

    need, hits = _union(cands), []
    for chunk in views.chunks:
        probs = gf.problems([chunk[t] for t in sorted(need) if t in chunk], extracts)
        by_task: dict[str, list] = {}
        for p in probs:
            by_task.setdefault(p.task, []).append(p)
        hits.append(
            {
                c.name: {
                    t
                    for t in c.tasks
                    if any(fm.holds(c.body, p.xs, p.ys) for p in by_task.get(t, ()))
                }
                for c in cands
            }
        )
    return _tally(cands, hits)


def pred_rates(cands: Sequence, views: Views) -> dict:
    from . import gen_predicates as gp

    need, hits = _union(cands), []
    for chunk in views.chunks:
        segs = gp.segments([chunk[t] for t in sorted(need) if t in chunk])
        by_task: dict[str, list] = {}
        for seg in segs:
            by_task.setdefault(seg.task, []).append(seg)
        cache: dict[tuple[int, str], int] = {}

        def mask(seg, body: list) -> int:
            if body[0] == "and":
                return mask(seg, body[1]) & mask(seg, body[2])
            key = (id(seg), json.dumps(body))
            if key not in cache:
                cache[key] = seg.mask(body)
            return cache[key]

        hits.append(
            {
                c.name: {
                    t
                    for t in c.tasks
                    if any(mask(s, c.body) == s.label for s in by_task.get(t, ()))
                }
                for c in cands
            }
        )
    return _tally(cands, hits)


def extract_rates(cands: Sequence, views: Views) -> dict:
    from arcagi.objrule import gen as objgen

    from . import gen_extract as gx

    grid = [c for c in cands if isinstance(c.body, list)]
    obj = [c for c in cands if isinstance(c.body, dict)]
    sels: list = []
    for c in grid:
        if c.body[1] not in sels:
            sels.append(c.body[1])
    hits = []
    for chunk in views.chunks:
        found: dict[str, set[str]] = {}
        tasks = [chunk[t] for t in sorted(_union(grid)) if t in chunk]
        if grid:
            for f in gx.score_candidates(tasks, sels):
                found[json.dumps(f.body)] = set(f.tasks)
        row = {
            c.name: found.get(json.dumps(c.body), set()) & set(c.tasks) for c in grid
        }
        tasks = [chunk[t] for t in sorted(_union(obj)) if t in chunk]
        if obj:
            scored = objgen.score(tasks, [c.body for c in obj])
            for c, (_, ids) in zip(obj, scored, strict=True):
                row[c.name] = set(ids) & set(c.tasks)
        hits.append(row)
    return _tally(cands, hits)


def pass_rates(kind: str, body, support: Iterable[str], views: Views, extracts=None):
    """One block: {task in ``support``: fraction of the 8 chunks it passes}."""

    @dataclass
    class One:
        body: object
        tasks: frozenset
        name: str = "one"

    one = [One(body, frozenset(support))]
    if kind == "formula":
        return formula_rates(one, views, extracts or {})["one"]
    if kind == "pred":
        return pred_rates(one, views)["one"]
    return extract_rates(one, views)["one"]


def apply_majority(
    cands: Sequence, rates: dict, protected: Iterable[str], narrow: bool = True
) -> dict:
    """Narrow supports to majority-passing tasks (protected or not ``narrow``:
    flag only).

    Sets ``orig_tasks``, ``synth_tasks`` (passing) and ``synth_rate`` (mean pass
    rate over the original support) on every candidate."""
    keep_names, claims, failed, kept = set(protected), 0, 0, []
    for c in cands:
        rate = rates.get(c.name, {})
        c.orig_tasks = set(c.tasks)
        c.synth_tasks = {t for t in c.tasks if rate.get(t, 0.0) >= MAJORITY}
        c.synth_rate = round(sum(rate.values()) / len(rate), 3) if rate else None
        claims += len(c.orig_tasks)
        failed += len(c.orig_tasks) - len(c.synth_tasks)
        c.synth_protected = c.name in keep_names
        if c.synth_protected:
            kept.append(c.name)
        if c.synth_protected or not narrow:
            continue
        c.tasks = type(c.tasks)(c.synth_tasks)
    return {"claims": claims, "failed": failed, "protected": sorted(kept)}


def check(
    kind: str, cands: Sequence, views: Views | None, extracts=None, narrow=True
) -> dict:
    """Rate scored candidates of a generator and narrow them (protected: income;
    ``narrow=False``: measure only)."""
    from .pool.budget import income

    if views is None:
        return {"synth": "off"}
    live = [c for c in cands if c.tasks]
    if kind == "formula":
        rates = formula_rates(live, views, extracts or {})
    elif kind == "pred":
        rates = pred_rates(live, views)
    else:
        rates = extract_rates(live, views)
    paid = {n for n, v in income().items() if v > 0}
    return apply_majority(live, rates, paid, narrow and views.narrow)


def fail_rate(blocks: Sequence) -> float | None:
    """Share of original-support claims of ``blocks`` failing the majority."""
    claims = sum(len(getattr(c, "orig_tasks", c.tasks)) for c in blocks)
    ok = sum(len(getattr(c, "synth_tasks", c.tasks)) for c in blocks)
    return round(1 - ok / claims, 3) if claims else None


def meta_fields(c) -> dict:
    """Synthetic-check fields for a written block's ``_metainfo.json``."""
    if not hasattr(c, "synth_tasks"):
        return {}
    out = {"synth_rate": c.synth_rate, "synth_support": sorted(c.synth_tasks)}
    return out | ({"synth_protected": True} if c.synth_protected else {})


def add_args(parser) -> None:
    """``--synth-root`` / ``--no-synth`` for a generator CLI."""
    parser.add_argument("--synth-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--no-synth", action="store_true", help="skip the check")


def from_args(args) -> Views | None:
    return None if args.no_synth else load(args.synth_root)
