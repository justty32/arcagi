"""Generator of formula blocks: enumerate, score on training, keep the best.

Run: ``uv run python -m arcagi.blocks.gen_formula --split training [--dry-run]``.
Targets per task: output height / width and, when every pair divides evenly,
the repeat counts ``rep_y = h_out / h_in`` and ``rep_x = w_out / w_in``; the
features are those of the train input (``arcagi.dsl.features``). A body
*supports* a task when it reproduces some target on every train pair and that
target takes at least two values (constants are not formulas). Score = number
of supported tasks; evaluation tasks never take part.

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
from pathlib import Path

from arcagi.dsl import background as bgc
from arcagi.dsl import formula as fm
from arcagi.dsl import grid as g
from arcagi.dsl.features import compute
from arcagi.tasks import Task, load_tasks

from . import REPO_ROOT, default_blocks_root, read_json, write_json

GENERATOR = "_gen/formula"
LIVE_CAP = 40
COVERED_CAP = 60
TARGETS = ("h_out", "w_out", "rep_y", "rep_x")
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


def problems(tasks: Sequence[Task]) -> list[Problem]:
    out = []
    for task in tasks:
        pairs = [(ex.input, ex.output) for ex in task.train]
        if len(pairs) < 2 or any(o is None for _, o in pairs):
            continue
        bg = bgc.task_background([grid for pair in pairs for grid in pair])
        with bgc.task_context(bg):  # same background as the search sees
            xs = [compute(i) for i, _ in pairs]
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


def score_candidates(probs: Sequence[Problem]) -> list[Candidate]:
    """Every enumerated body with the tasks (and targets) it supports."""
    cands = [Candidate(list(b), i) for i, b in enumerate(fm.ALL_BODIES)]
    for p in probs:
        for c in cands:
            if fm.holds(c.body, p.xs, p.ys):
                c.tasks.add(p.task)
                c.targets.add(p.target)
    return cands


def judge(cands: Sequence[Candidate], live_cap: int = LIVE_CAP) -> dict[str, list]:
    """Split scored candidates into live / covered / dropped (score 0)."""
    scored = [c for c in cands if c.score > 0]
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
        "dropped": [c for c in cands if c.score == 0],
    }


def _write_block(root: Path, c: Candidate, status: str, by: str | None) -> None:
    folder = root / c.name
    old = read_json(folder / "_metainfo.json", {}) or {}
    meta = {
        "name": c.name,
        "kind": "formula",
        "doc": "Generated integer formula " + json.dumps(c.body),
        "params": [],
        "cost": 1,
        "status": status,
        "counter_uses": old.get("counter_uses", 0),  # type: ignore[union-attr]
        "generator": GENERATOR,
        "score": c.score,
        "length": c.length,
        "targets": sorted(c.targets),
        "support_tasks": sorted(c.tasks),
    }
    if by:
        meta["covered_by"] = by
    write_json(folder / "_metainfo.json", meta)
    write_json(
        folder / "_rule.json",
        {
            "kind": "formula",
            "in": "features",
            "out": "int",
            "body": c.body,
            "score": c.score,
        },
    )
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
    write_json(
        node / "_metainfo.json",
        {
            "name": GENERATOR,
            "kind": "generator",
            "doc": "Enumerates <=1-op, <=2-feature integer formulas for output "
            "size / repeat counts; scored on training.",
            "params": ["live_cap"],
            "cost": 1,
            "status": "live",
            "counter_uses": old.get("counter_uses", 0),  # type: ignore[union-attr]
            "produces": "formula",
            "gen_seconds": stats["gen_seconds"],
            "last_run": stats,
        },
    )
    entry = node / "_entry"
    entry.write_text(GEN_ENTRY, encoding="utf-8")
    os.chmod(entry, 0o755)
    return written


def run(tasks: Sequence[Task], live_cap: int = LIVE_CAP) -> tuple[dict, dict]:
    """Score ``tasks`` and judge; returns (verdict, stats)."""
    start = time.perf_counter()
    probs = problems(tasks)
    cands = score_candidates(probs)
    verdict = judge(cands, live_cap)
    stats = {
        "tasks": len(tasks),
        "problems": len(probs),
        "scored": len(cands),
        "live": len(verdict["live"]),
        "covered": len(verdict["covered"]),
        "over_cap": len(verdict["over_cap"]),
        "dropped": len(verdict["dropped"]),
        "gen_seconds": round(time.perf_counter() - start, 2),
    }
    return verdict, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate formula blocks.")
    parser.add_argument("--split", default="training")
    parser.add_argument("--data-root", type=Path, default=REPO_ROOT / "data/ARC-AGI")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--live-cap", type=int, default=LIVE_CAP)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.split != "training":
        parser.error("formulas are scored on training only")
    nested = args.data_root / "data" / args.split
    tasks = load_tasks(nested if nested.is_dir() else args.data_root / args.split)
    verdict, stats = run(tasks, args.live_cap)
    stats = {"split": args.split, **stats}
    if not args.dry_run:
        write_blocks(args.root or default_blocks_root(), verdict, stats)
    print(json.dumps(stats))
    for c in verdict["live"][:8]:
        print(f"{c.name} {c.score} {json.dumps(c.body)} {sorted(c.targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
