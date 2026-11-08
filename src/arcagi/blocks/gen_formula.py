"""Generator of formula blocks: enumerate, score on training, keep the best.

Run: ``uv run python -m arcagi.blocks.gen_formula --split training [--dry-run]``.
Targets per task: output height / width and, when every pair divides evenly,
the repeat counts ``rep_y = h_out / h_in`` and ``rep_x = w_out / w_in``; the
features are those of the train input (``arcagi.dsl.features``) plus those of
the top 20 extract blocks by ledger (``pool.budget.top_extracts``). Candidates:
base one-layer bodies, one-layer bodies reading an extract feature, then (only
on problems no one-layer body fits) two-layer bodies proposed from those
problems' first pair; ``pool.budget.allocate()`` caps the total (printed),
two-layer at most ``formula.TWO_CAP``. A body *supports* a task when it
reproduces some target on every train pair and that target takes at least two
values (constants are not formulas). Score = number of supported tasks;
evaluation tasks never take part.

Score 0 is not written. Bodies with the same support set keep the shortest
(then first enumerated); the others, and those whose support lies inside the
union of supports of kept no-longer bodies (greedy, simplest first), are
``covered``. At most ``--live-cap`` stay live.
Output: ``<root>/formula_<hash>/{_metainfo.json,_rule.json,_entry}`` and the
generator node ``<root>/_gen/formula/{_metainfo.json,_entry}``.
"""

import argparse
import hashlib
import json
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import zip_longest
from pathlib import Path

from arcagi.dsl import background as bgc
from arcagi.dsl import features as ft
from arcagi.dsl import formula as fm
from arcagi.dsl import grid as g
from arcagi.tasks import Task, load_tasks

from . import REPO_ROOT, default_blocks_root, read_json, write_json
from .pool.budget import allocate, announce, top_extracts

GENERATOR = "_gen/formula"
LIVE_CAP = 40
COVERED_CAP = 60
TARGETS = ("h_out", "w_out", "rep_y", "rep_x")
# Tunable settings (``config`` in the node metainfo, chosen by ``gen_meta``).
CONFIG = {"n_extracts": 20, "two_layer": True, "min_support": 1, "forms": fm.OPS}
ENTRY_SCRIPT = """#!/bin/sh
# aos formula block: stdin grid JSON (or {"grid":..} or a feature dict) -> int
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
exec "$root/.venv/bin/python" -m arcagi.dsl.formula "$here/_rule.json"
"""
GEN_ENTRY = """#!/bin/sh
# aos generator node: enumerate formula blocks on training (args pass through,
# e.g. --dry-run).
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../../.." && pwd)
cd "$root" && exec "$root/.venv/bin/python" -m arcagi.blocks.gen_formula \\
    --split training "$@"
"""


@dataclass
class Problem:
    """One (task, target): train input features and target values."""

    task: str
    target: str
    xs: list[dict[str, int]]
    ys: list[int]
    hit: bool = False  # some scored body fits it


def problems(tasks: Sequence[Task], extracts: dict | None = None) -> list[Problem]:
    out = []
    for task in tasks:
        pairs = [(ex.input, ex.output) for ex in task.train]
        if len(pairs) < 2 or any(o is None for _, o in pairs):
            continue
        bg = bgc.task_background([grid for pair in pairs for grid in pair])
        with bgc.task_context(bg):  # same background as the search sees
            xs = [ft.compute(i, extracts or {}) for i, _ in pairs]
        shapes = [(g.shape(i), g.shape(o)) for i, o in pairs]  # type: ignore[arg-type]
        values: dict[str, list[int]] = {
            "h_out": [o[0] for _, o in shapes],
            "w_out": [o[1] for _, o in shapes],
        }
        if all(o[0] % i[0] == 0 and o[1] % i[1] == 0 for i, o in shapes):
            values["rep_y"] = [o[0] // i[0] for i, o in shapes]
            values["rep_x"] = [o[1] // i[1] for i, o in shapes]
        for target, ys in values.items():
            if len(set(ys)) >= 2:
                out.append(Problem(task.task_id, target, xs, ys))
    return out


@dataclass
class Candidate:
    body: list
    order: int
    tasks: set[str] = field(default_factory=set)
    targets: set[str] = field(default_factory=set)
    extracts: dict = field(default_factory=dict)  # sources of extract features

    @property
    def length(self) -> int:
        return fm.length(self.body)

    @property
    def score(self) -> int:
        return len(self.tasks)

    @property
    def name(self) -> str:
        text = json.dumps(self.body, separators=(",", ":"))
        return "formula_" + hashlib.sha1(text.encode()).hexdigest()[:8]


def score_candidates(probs: Sequence[Problem], bodies=fm.ALL_BODIES, start: int = 0):
    """Every body (default: base one-layer) with the tasks / targets it supports."""
    cands = [Candidate(list(b), start + i) for i, b in enumerate(bodies)]
    for p in probs:
        for c in cands:
            if fm.holds(c.body, p.xs, p.ys):
                p.hit = True
                c.tasks.add(p.task)
                c.targets.add(p.target)
    return cands


def judge(cands: Sequence[Candidate], live_cap: int = LIVE_CAP, least: int = 1):
    """Split candidates into live / covered / dropped (score below ``least``)."""
    scored = [c for c in cands if c.score >= max(least, 1)]
    best: dict[frozenset[str], Candidate] = {}
    for c in sorted(scored, key=lambda c: (c.length, c.order)):
        best.setdefault(frozenset(c.tasks), c)
    live, covered = [], []
    for c in scored:
        winner = best[frozenset(c.tasks)]
        if winner is c:
            live.append(c)
        else:
            covered.append((c, winner.name))
    # Greedy cover, simplest first: a body whose support is explained by the
    # union of kept no-longer bodies is covered (by the one overlapping most).
    kept: list[Candidate] = []
    union: set[str] = set()
    for c in sorted(live, key=lambda c: (c.length, -c.score, c.order)):
        if c.tasks <= union:
            dom = max(kept, key=lambda k: (len(k.tasks & c.tasks), -k.order))
            covered.append((c, dom.name))
        else:
            kept.append(c)
            union |= c.tasks
    rank = lambda c: (-c.score, c.length, c.order)  # noqa: E731
    kept.sort(key=rank)
    covered.sort(key=lambda pair: rank(pair[0]))
    return {
        "live": kept[:live_cap],
        "covered": covered[:COVERED_CAP],
        "over_cap": kept[live_cap:],
        "dropped": [c for c in cands if c.score < max(least, 1)],
    }


def _write_block(root: Path, c: Candidate, status: str, by: str | None) -> None:
    folder = root / c.name
    old = read_json(folder / "_metainfo.json", {}) or {}
    meta = {"name": c.name, "kind": "formula", "params": [], "cost": 1}
    meta["doc"] = "Generated integer formula " + json.dumps(c.body)
    meta |= {"status": status, "counter_uses": old.get("counter_uses", 0)}  # type: ignore[union-attr]
    meta |= {"generator": GENERATOR, "score": c.score, "length": c.length}
    meta |= {"targets": sorted(c.targets), "support_tasks": sorted(c.tasks)}
    if by:
        meta["covered_by"] = by
    write_json(folder / "_metainfo.json", meta)
    rule = {"kind": "formula", "in": "features", "out": "int", "body": c.body}
    rule |= {"score": c.score} | ({"extracts": c.extracts} if c.extracts else {})
    write_json(folder / "_rule.json", rule)
    entry = folder / "_entry"
    entry.write_text(ENTRY_SCRIPT, encoding="utf-8")
    os.chmod(entry, 0o755)


def write_blocks(root: Path, verdict: dict[str, list], stats: dict) -> list[str]:
    """Write formula folders and the generator node; retire stale ones."""
    written = []
    for c in verdict["live"]:
        _write_block(root, c, "live", None)
        written.append(c.name)
    for c, by in verdict["covered"]:
        _write_block(root, c, "covered", by)
        written.append(c.name)
    for folder in sorted(root.glob("formula_*")):
        meta = read_json(folder / "_metainfo.json", None)
        if folder.name not in written and isinstance(meta, dict):
            write_json(folder / "_metainfo.json", {**meta, "status": "retired"})
    node = root / GENERATOR
    old = read_json(node / "_metainfo.json", {}) or {}
    doc = "Enumerates <=1-op, <=2-feature integer formulas (features include top "
    doc += "extracts), then two-layer ones on unfit problems; scored on training."
    meta = {**old, "name": GENERATOR, "kind": "generator", "doc": doc, "cost": 1}  # type: ignore[dict-item]
    meta |= {"params": ["live_cap", "config"], "status": "live", "produces": "formula"}
    meta |= {"counter_uses": old.get("counter_uses", 0), "last_run": stats}  # type: ignore[union-attr]
    write_json(node / "_metainfo.json", meta | {"gen_seconds": stats["gen_seconds"]})
    entry = node / "_entry"
    entry.write_text(GEN_ENTRY, encoding="utf-8")
    os.chmod(entry, 0o755)
    return written


def _sources(body: Sequence[object]) -> list[str]:
    return [src for n in body[1:] if isinstance(n, str) and (src := ft.source(n))]


def bodies(extracts: dict, budget: int | None, cfg: dict = CONFIG) -> tuple:
    """One-layer bodies (``cfg`` forms) and the two-layer cap, <= ``budget``."""
    names = (*ft.NAMES, *ft.names_of(extracts))
    ext = [b for b in fm.enumerate_bodies(names) if _sources(b)]
    one = [b for b in (*fm.ALL_BODIES, *ext) if b[0] in cfg["forms"]]
    cap = budget if budget is not None else len(one) + fm.TWO_CAP
    two_cap = min(fm.TWO_CAP, cap // 4) if cfg["two_layer"] else 0
    one = one[: max(cap - two_cap, 0)]
    return one, min(two_cap, cap - len(one))


def two_layer(names: Sequence[str], unfit: Sequence[Problem], cap: int) -> list:
    """At most ``cap`` two-layer bodies fitting the first pair of an unfit problem,
    simplest first, taken round-robin over the problems (proposed from data;
    scoring still needs every pair)."""
    space = fm.enumerate_two(names, len(names) ** 2 * 32)
    queues = [[b for b in space if fm.holds(b, [p.xs[0]], [p.ys[0]])] for p in unfit]
    rr = [b for row in zip_longest(*queues) for b in row if b is not None]
    out = {json.dumps(b): b for b in rr}  # first occurrence keeps its place
    return sorted(list(out.values())[: max(cap, 0)], key=fm.length)


def run(
    tasks: Sequence[Task],
    live_cap: int = LIVE_CAP,
    budget: int | None = None,
    extracts: dict | None = None,
    config: dict | None = None,
) -> tuple[dict, dict]:
    """Score ``tasks`` and judge under ``config`` (see ``CONFIG``)."""
    start, cfg = time.perf_counter(), {**CONFIG, **(config or {})}
    ext = dict(list((extracts or {}).items())[: cfg["n_extracts"]])
    probs = problems(tasks, ext)
    one, two_cap = bodies(ext, budget, cfg)
    cands = score_candidates(probs, one)
    unfit = [p for p in probs if not p.hit]
    two = two_layer((*ft.NAMES, *ft.names_of(ext)), unfit, two_cap)
    cands += score_candidates(unfit, two, len(one))
    for c in cands:
        c.extracts = {src: ext[src] for src in _sources(c.body)}
    verdict = judge(cands, live_cap, cfg["min_support"])
    sizes = {"tasks": tasks, "problems": probs, "extracts": ext, "scored": cands}
    sizes |= {"one_layer": one, "two_layer": two, "unfit_problems": unfit}
    sizes |= {k: verdict[k] for k in ("live", "covered", "over_cap", "dropped")}
    stats: dict = {"budget": budget, **{k: len(v) for k, v in sizes.items()}}
    stats["gen_seconds"] = round(time.perf_counter() - start, 2)
    return verdict, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate formula blocks.")
    parser.add_argument("--split", default="training")
    parser.add_argument("--data-root", type=Path, default=REPO_ROOT / "data/ARC-AGI")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--live-cap", type=int, default=LIVE_CAP)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--budget", type=int, default=None, help="default: pool")
    args = parser.parse_args(argv)
    if args.split != "training":
        parser.error("formulas are scored on training only")
    budget = args.budget or allocate()[GENERATOR]
    announce(GENERATOR, budget)
    nested = args.data_root / "data" / args.split
    tasks = load_tasks(nested if nested.is_dir() else args.data_root / args.split)
    node = (args.root or default_blocks_root()) / GENERATOR / "_metainfo.json"
    cfg = (read_json(node, {}) or {}).get("config")  # type: ignore[union-attr]
    verdict, stats = run(tasks, args.live_cap, budget, top_extracts(args.root), cfg)
    stats = {"split": args.split, **stats}
    if not args.dry_run:
        write_blocks(args.root or default_blocks_root(), verdict, stats)
    print(json.dumps(stats))
    for c in verdict["live"][:8]:
        print(f"{c.name} {c.score} {json.dumps(c.body)} {sorted(c.targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
