"""Generator of predicate blocks: enumerate, score on training, keep the best.

Run: ``uv run python -m arcagi.blocks.gen_predicates --split training
--max-literals 2``. Candidates (the first ``pool.budget.allocate()`` of them,
printed) are single literals (``eq``/``ne``/``gt``/``lt``/
``rank``) and two-literal ``and``s over the object attributes. A candidate
*separates* a task when, for some connectivity, its truth equals "the object
changed" for every object of every train pair (both classes present). Score =
separated tasks - 0.5 * literals; evaluation tasks never take part.

Score <= 0 is not written. Candidates with the same separated task set keep the
shortest (then first enumerated); the others, and those whose task set is a
subset of a kept no-longer predicate's, are ``covered``. A plain ``eq``
literal is covered by the built-in single-attribute selector. At most
``--live-cap`` predicates stay live. Output: ``<root>/pred_<hash>/`` with
``_metainfo.json`` (kind=pred, generator), ``_rule.json`` and ``_entry``; the
generator node is ``<root>/_gen/pred_combiner/_metainfo.json``. With
``data_synth`` (``--no-synth`` off) task sets are first narrowed to tasks passing
the synthetic majority (``synth_score``).
"""

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from arcagi.dsl import predicates as pr
from arcagi.dsl.objects_props import CONNS, changed, extract, same_shapes
from arcagi.tasks import Task, load_tasks

from . import REPO_ROOT, default_blocks_root, read_json, write_json
from . import synth_score as ss
from .pool.budget import allocate, announce

GENERATOR = "_gen/pred_combiner"
LIVE_CAP = 60
COVERED_CAP = 40
BUILTIN = "builtin:eq_selector"
NUMERIC = ("size", "h", "w", "shape_count", "color_count", "size_rank")
BOOLEAN = ("is_largest", "is_smallest", "touches_border", "has_hole")
ENTRY_SCRIPT = """#!/bin/sh
# aos predicate block: stdin object props (or {"object":..,"group":[..]}) -> true|false
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
exec "$root/.venv/bin/python" -m arcagi.dsl.predicates "$here/_rule.json"
"""


def literal_pool() -> list[list]:
    """Single literals in canonical (simplicity) order."""
    lits: list[list] = []
    for c in range(10):
        lits += [["eq", "color", c], ["ne", "color", c]]
    for attr in BOOLEAN:
        lits += [["eq", attr, 1], ["eq", attr, 0]]
    for attr in NUMERIC:
        if attr != "size_rank":
            lits += [["rank", attr, "max"], ["rank", attr, "min"]]
        lits += [["eq", attr, v] for v in range(1, 11)]
        lits += [["gt", attr, v] for v in range(1, 10)]
        lits += [["lt", attr, v] for v in range(2, 11)]
    return lits


@dataclass
class Segment:
    """One (task, conn): every train object, its label and its group."""

    task: str
    groups: list[list[dict]] = field(default_factory=list)
    label: int = 0  # bit i set = object i changed

    @property
    def size(self) -> int:
        return sum(len(grp) for grp in self.groups)

    def mask(self, body: Sequence[object]) -> int:
        bits, i = 0, 0
        for grp in self.groups:
            for truth in pr.evaluate_group(body, grp):
                bits |= int(truth) << i
                i += 1
        return bits


def segments(tasks: Sequence[Task]) -> list[Segment]:
    out = []
    for task in tasks:
        states = [ex.input for ex in task.train]
        targets = [ex.output for ex in task.train]
        if any(t is None for t in targets) or not same_shapes(states, targets):  # type: ignore[arg-type]
            continue
        for conn in CONNS:
            seg, i = Segment(task.task_id), 0
            for state, target in zip(states, targets, strict=True):
                objs = extract(state, conn)
                seg.groups.append([o.props for o in objs])
                for o in objs:
                    seg.label |= int(changed(o, target)) << i  # type: ignore[arg-type]
                    i += 1
            full = (1 << i) - 1
            if 0 < seg.label < full:
                out.append(seg)
    return out


@dataclass
class Candidate:
    body: list
    tasks: frozenset[str]
    order: int

    @property
    def literals(self) -> int:
        return pr.literals(self.body)

    @property
    def score(self) -> float:
        return len(self.tasks) - 0.5 * self.literals

    @property
    def name(self) -> str:
        text = json.dumps(self.body, separators=(",", ":"))
        return "pred_" + hashlib.sha1(text.encode()).hexdigest()[:8]


def score_candidates(
    segs: Sequence[Segment], max_literals: int, budget: int | None = None
) -> list[Candidate]:
    """The first ``budget`` (default all) candidates with the tasks they separate."""
    lits = literal_pool()
    masks = [[seg.mask(lit) for seg in segs] for lit in lits]
    # Segments where the literal contains every changed object (AND prefilter).
    sup = [
        {k for k, seg in enumerate(segs) if m[k] & seg.label == seg.label}
        for m in masks
    ]
    found: list[Candidate] = []
    for i, lit in enumerate(lits):
        tasks = {segs[k].task for k in sup[i] if masks[i][k] == segs[k].label}
        found.append(Candidate(lit, frozenset(tasks), len(found)))
    cap = len(lits) ** 2 if budget is None else budget
    if max_literals >= 2:
        for i in range(len(lits)):
            for j in range(i + 1, len(lits)):
                if len(found) >= cap:
                    return found[:cap]
                common = sup[i] & sup[j]
                tasks = {
                    segs[k].task
                    for k in common
                    if masks[i][k] & masks[j][k] == segs[k].label
                }
                found.append(
                    Candidate(["and", lits[i], lits[j]], frozenset(tasks), len(found))
                )
    return found[:cap]


def judge(cands: Sequence[Candidate], live_cap: int = LIVE_CAP) -> dict[str, list]:
    """Split scored candidates into live / covered / dropped (score <= 0)."""
    scored = [c for c in cands if c.score > 0]
    best: dict[frozenset[str], Candidate] = {}
    for c in sorted(scored, key=lambda c: (c.literals, c.order)):
        best.setdefault(c.tasks, c)
    live, covered = [], []
    for c in scored:
        winner = best[c.tasks]
        if winner is not c:
            covered.append((c, winner.name))
        elif c.body[0] == "eq":
            covered.append((c, BUILTIN))
        else:
            live.append(c)
    rank = lambda c: (-c.score, c.literals, c.order)  # noqa: E731
    kept: list[Candidate] = []
    for c in sorted(live, key=rank):
        # Dominated: a kept predicate, no longer, separates a superset of tasks.
        dom = next(
            (k for k in kept if c.tasks <= k.tasks and k.literals <= c.literals), None
        )
        if dom is None:
            kept.append(c)
        else:
            covered.append((c, dom.name))
    live = kept
    covered.sort(key=lambda pair: rank(pair[0]))
    return {
        "live": live[:live_cap],
        "covered": covered[:COVERED_CAP],
        "over_cap": live[live_cap:],
        "dropped": [c for c in cands if c.score <= 0],
    }


def _write_pred(root: Path, c: Candidate, status: str, covered_by: str | None) -> None:
    folder = root / c.name
    old = read_json(folder / "_metainfo.json", {}) or {}
    meta = {"name": c.name, "kind": "pred", "params": [], "cost": 1}
    meta["doc"] = "Generated object predicate " + json.dumps(c.body)
    meta |= {"status": status, "counter_uses": old.get("counter_uses", 0)}  # type: ignore[union-attr]
    meta |= {"generator": GENERATOR, "score": c.score, "literals": c.literals}
    meta |= {"tasks": sorted(c.tasks)} | ss.meta_fields(c)
    meta |= {"covered_by": covered_by} if covered_by else {}
    write_json(folder / "_metainfo.json", meta)
    write_json(
        folder / "_rule.json",
        {"kind": "pred", "in": "object", "out": "bool", "body": c.body},
    )
    entry = folder / "_entry"
    entry.write_text(ENTRY_SCRIPT, encoding="utf-8")
    os.chmod(entry, 0o755)


def write_blocks(root: Path, verdict: dict[str, list], stats: dict) -> list[str]:
    """Write pred folders and the generator node; retire stale pred folders."""
    written = []
    for c in verdict["live"]:
        _write_pred(root, c, "live", None)
        written.append(c.name)
    for c, by in verdict["covered"]:
        _write_pred(root, c, "covered", by)
        written.append(c.name)
    for folder in sorted(root.glob("pred_*")):
        meta = read_json(folder / "_metainfo.json", None)
        if folder.name not in written and isinstance(meta, dict):
            write_json(folder / "_metainfo.json", {**meta, "status": "retired"})
    node = root / GENERATOR / "_metainfo.json"
    old = read_json(node, {}) or {}
    write_json(
        node,
        {
            "name": GENERATOR,
            "kind": "generator",
            "doc": "Enumerates literals and 2-literal ANDs; scored on training.",
            "params": ["max_literals", "live_cap"],
            "cost": 1,
            "status": "live",
            "counter_uses": old.get("counter_uses", 0),  # type: ignore[union-attr]
            "produces": "pred",
            "last_run": stats,
        },
    )
    return written


def run(
    tasks: Sequence[Task],
    max_literals: int = 2,
    budget: int | None = None,
    live_cap: int = LIVE_CAP,
    synth: ss.Views | None = None,
) -> tuple[dict, dict]:
    """Score and judge ``tasks``; ``synth``: synthetic-majority narrowing first."""
    segs = segments(tasks)
    cands = score_candidates(segs, max_literals, budget)
    checked = ss.check("pred", cands, synth)
    verdict = judge(cands, live_cap)
    stats = {"max_literals": max_literals, "budget": budget, "segments": len(segs)}
    stats |= {"scored": len(cands)} | {k: len(verdict[k]) for k in verdict}
    return verdict, stats | {"synth": checked}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate predicate blocks.")
    parser.add_argument("--split", default="training")
    parser.add_argument("--max-literals", type=int, default=2, choices=(1, 2))
    parser.add_argument("--data-root", type=Path, default=REPO_ROOT / "data/ARC-AGI")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--live-cap", type=int, default=LIVE_CAP)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--budget", type=int, default=None, help="default: pool")
    ss.add_args(parser)
    args = parser.parse_args(argv)
    budget = args.budget or allocate()[GENERATOR]
    announce(GENERATOR, budget)
    if args.split != "training":
        parser.error("predicates are scored on training only")
    nested = args.data_root / "data" / args.split
    tasks = load_tasks(nested if nested.is_dir() else args.data_root / args.split)
    synth = ss.from_args(args)
    verdict, stats = run(tasks, args.max_literals, budget, args.live_cap, synth)
    stats = {"split": args.split, **stats}
    if not args.dry_run:
        write_blocks(args.root or default_blocks_root(), verdict, stats)
    print(json.dumps(stats))
    for c in verdict["live"][:5]:
        print(f"{c.name} {c.score:g} {json.dumps(c.body)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
