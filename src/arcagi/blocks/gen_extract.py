"""Generator of extract blocks: enumerate extractions, score on training.

Run: ``uv run python -m arcagi.blocks.gen_extract --split training [--dry-run]``.
Grid scope: ``[prop, [sel, conn, *args]]`` (``arcagi.dsl.extract``), sel in
largest / smallest / unique_color / unique_shape / all / color c / live pred_*,
prop in ``SCORED``; it *supports* a task when on every train pair its value is
one output property (the output grid, its only fg color, height / width / fg
cell count; colors / numbers need >= 2 values; same-shape tasks: color only).
Object scope (``arcagi.objrule.gen``): per-object targets of same-shape tasks,
count capped by the pool budget. Score = supported training tasks (narrowed to
synthetic-majority ones with ``data_synth``, ``synth_score``; ``config`` from
``gen_meta``). Score 0 is not written; the shortest of a support set (or
superset, no longer) is live, the rest ``covered``; at most ``--live-cap`` live.
Writes ``extract_<hash>/`` and ``_gen/extract/``."""

import argparse
import hashlib
import json
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from arcagi.dsl import extract as ex
from arcagi.dsl import grid as g
from arcagi.dsl import predicates as pr
from arcagi.dsl.objects_props import CONNS
from arcagi.objrule import gen as objgen
from arcagi.tasks import Grid, Task, load_tasks

from . import REPO_ROOT, default_blocks_root, read_json, write_json
from . import synth_score as ss
from .catalog import load_catalog

GENERATOR = "_gen/extract"
LIVE_CAP = 60
COVERED_CAP = 40
SCORED = ("subgrid", "object", "color", "size", "count")
# Tunable settings (``config`` in the node metainfo, chosen by ``gen_meta``).
CONFIG = {"props": list(SCORED), "conns": list(CONNS), "pred_selectors": True}
CONFIG |= {"object_scope": True, "min_support": 1}
ENTRY_SCRIPT = """#!/bin/sh
# aos extract block: stdin grid (or {"grid": ..}) -> extracted JSON value
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../.." && pwd)
exec "$root/.venv/bin/python" -m arcagi.dsl.extract "$here/_rule.json"
"""
GEN_ENTRY = """#!/bin/sh
# aos generator node: enumerate extract blocks on training (args e.g. --dry-run)
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../../.." && pwd)
cd "$root" && exec "$root/.venv/bin/python" -m arcagi.blocks.gen_extract \
    --split training "$@"
"""


def selectors(pred_names: Sequence[str], conns: Sequence[str] = CONNS) -> list[list]:
    """Every selector in canonical (simplicity) order."""
    out: list[list] = []
    for conn in conns:
        out += [[op, conn] for op in ex.SINGLE]
        out.append(["all", conn])
        out += [["color", conn, c] for c in range(10)]
        out += [["pred", conn, name] for name in pred_names]
    return out


def _fg(grid: Grid, bg: int) -> set[int]:
    return set(g.color_counts(grid)) - {bg}


def targets(pairs: Sequence[tuple[Grid, Grid]], prop: str) -> list[list]:
    """Per pair, the candidate target values keyed by target kind."""
    rows = []
    for inp, out in pairs:
        if prop in ex.GRID_PROPS:
            rows.append({"grid": [list(r) for r in out]})
            continue
        h, w = g.shape(out)
        if prop == "color":
            row: dict = {}
            rows.append(row)
            if len(_fg(inp, g.background(inp))) < 2:  # nothing to choose from
                continue
            fg = _fg(out, g.background(inp))
            if len(fg) == 1:
                row["fg_color"] = next(iter(fg))
            if len(set(g.color_counts(out))) == 1:
                row["uniform"] = out[0][0]
        else:
            obg = g.background(out)
            fg_cells = sum(v != obg for r in out for v in r)
            rows.append({"h": h, "w": w, "fg_cells": fg_cells})
    return rows


def supports(values: Sequence[object], rows: Sequence[dict], prop: str) -> bool:
    for key in rows[0]:
        if all(r.get(key) == v for r, v in zip(rows, values, strict=True)):
            if prop in ex.GRID_PROPS or len({json.dumps(v) for v in values}) >= 2:
                return True
    return False


@dataclass
class Candidate:
    body: list | dict  # dict: object-scope body
    tasks: frozenset[str]
    order: int

    @property
    def length(self) -> int:
        return ex.length(self.body)

    @property
    def score(self) -> int:
        return len(self.tasks)

    @property
    def name(self) -> str:
        text = json.dumps(self.body, separators=(",", ":"))
        return "extract_" + hashlib.sha1(text.encode()).hexdigest()[:8]


def _task_pairs(task: Task) -> list[tuple[Grid, Grid]] | None:
    pairs = [(e.input, e.output) for e in task.train]
    return None if any(o is None for _, o in pairs) else pairs  # type: ignore[return-value]


def score_candidates(
    tasks: Sequence[Task], sels: Sequence[list], scored: Sequence[str] = SCORED
) -> list[Candidate]:
    """Every (prop in ``scored``, selector) with the set of tasks it supports."""
    support: dict[tuple[int, int], set[str]] = {}
    for task in tasks:
        pairs = _task_pairs(task)
        if pairs is None:
            continue
        grid_task = any(g.shape(i) != g.shape(o) for i, o in pairs)
        rows = {p: targets(pairs, p) for p in scored}
        for si, sel in enumerate(sels):
            try:
                picked = [ex.select(i, sel) for i, _ in pairs]
            except (ValueError, KeyError, IndexError):
                continue
            for pi, prop in enumerate(scored):
                if (prop != "color" and not grid_task) or not rows[prop][0]:
                    continue
                try:
                    values = [
                        ex.prop(i, prop, objs)
                        for (i, _), objs in zip(pairs, picked, strict=True)
                    ]
                except (ValueError, KeyError, IndexError):
                    continue
                if supports(values, rows[prop], prop):
                    support.setdefault((pi, si), set()).add(task.task_id)
    found = []
    for si, sel in enumerate(sels):
        for pi, prop in enumerate(scored):
            tasks_ = frozenset(support.get((pi, si), ()))
            found.append(Candidate([prop, sel], tasks_, len(found)))
    return found


def judge(
    cands: Sequence[Candidate], live_cap: int = LIVE_CAP, least: int = 1
) -> dict[str, list]:
    """Split candidates into live / covered / over_cap / dropped (score < least)."""
    least = max(least, 1)
    scored = [c for c in cands if c.score >= least]
    best: dict[frozenset[str], Candidate] = {}
    for c in sorted(scored, key=lambda c: (c.length, c.order)):
        best.setdefault(c.tasks, c)
    rank = lambda c: (-c.score, c.length, c.order)  # noqa: E731
    covered = [(c, best[c.tasks].name) for c in scored if best[c.tasks] is not c]
    live: list[Candidate] = []
    for c in sorted((c for c in scored if best[c.tasks] is c), key=rank):
        # Dominated: a kept, no longer candidate supports a superset of tasks.
        dom = next(
            (k for k in live if c.tasks <= k.tasks and k.length <= c.length), None
        )
        if dom is None:
            live.append(c)
        else:
            covered.append((c, dom.name))
    covered.sort(key=lambda pair: rank(pair[0]))
    return {
        "live": live[:live_cap],
        "covered": covered[:COVERED_CAP],
        "over_cap": live[live_cap:],
        "dropped": [c for c in cands if c.score < least],
    }


def _write_block(root: Path, c: Candidate, status: str, by: str | None) -> None:
    folder = root / c.name
    old = read_json(folder / "_metainfo.json", {}) or {}
    meta = {"name": c.name, "kind": "extract", "params": [], "cost": 1}
    meta["doc"] = "Generated extraction " + json.dumps(c.body)
    meta |= {"status": status, "counter_uses": old.get("counter_uses", 0)}  # type: ignore[union-attr]
    meta |= {"generator": GENERATOR, "score": c.score, "length": c.length}
    meta |= {"support_tasks": sorted(c.tasks)} | ss.meta_fields(c)
    meta |= {"covered_by": by} if by else {}
    write_json(folder / "_metainfo.json", meta)
    write_json(
        folder / "_rule.json",
        {"kind": "extract", "in": "grid", "out": "json", "body": c.body},
    )
    entry = folder / "_entry"
    entry.write_text(ENTRY_SCRIPT, encoding="utf-8")
    os.chmod(entry, 0o755)


def write_blocks(root: Path, verdict: dict[str, list], stats: dict) -> list[str]:
    """Write extract folders and the generator node; retire stale extract folders."""
    written = []
    for c in verdict["live"]:
        _write_block(root, c, "live", None)
        written.append(c.name)
    for c, by in verdict["covered"]:
        _write_block(root, c, "covered", by)
        written.append(c.name)
    for folder in sorted(root.glob("extract_*")):
        meta = read_json(folder / "_metainfo.json", None)
        if folder.name not in written and isinstance(meta, dict):
            write_json(folder / "_metainfo.json", {**meta, "status": "retired"})
    write_node(root, stats)
    return written


def write_node(root: Path, stats: dict) -> None:
    node = root / GENERATOR
    old = read_json(node / "_metainfo.json", {}) or {}
    meta = {**old, "name": GENERATOR, "kind": "generator", "cost": 1}  # type: ignore[dict-item]
    meta["doc"] = "Enumerates selector x property extractions; scored on training."
    meta |= {"params": ["live_cap", "config"], "status": "live", "produces": "extract"}
    meta |= {"counter_uses": old.get("counter_uses", 0), "last_run": stats}  # type: ignore[union-attr]
    meta |= {"gen_seconds": stats["gen_seconds"]}
    write_json(node / "_metainfo.json", meta)
    entry = node / "_entry"
    entry.write_text(GEN_ENTRY, encoding="utf-8")
    os.chmod(entry, 0o755)


def run(
    tasks: Sequence[Task],
    root: Path,
    live_cap: int = LIVE_CAP,
    config: dict | None = None,
    synth: ss.Views | None = None,
) -> tuple[dict, dict]:
    """Score and judge ``tasks`` under ``config`` (see ``CONFIG``) with the live
    predicates of ``root``; ``synth``: synthetic-majority narrowing first."""
    start, cfg = time.monotonic(), {**CONFIG, **(config or {})}
    pr.install(preds := load_catalog(root).predicates())
    names = sorted(preds) if cfg["pred_selectors"] else []
    cands = score_candidates(tasks, selectors(names, cfg["conns"]), cfg["props"])
    n_grid = len(cands)
    if cfg["object_scope"]:
        bodies = objgen.all_bodies()[: objgen.budget(GENERATOR, n_grid)]
        for body, ids in objgen.score(tasks, bodies):
            cands.append(Candidate(body, ids, len(cands)))
    checked = ss.check("extract", cands, synth)
    verdict = judge(cands, live_cap, cfg["min_support"])
    stats = {"tasks": len(tasks), "scored": len(cands)}
    stats |= {"object_scored": len(cands) - n_grid}
    stats |= {k: len(verdict[k]) for k in verdict} | {"synth": checked}
    return verdict, stats | {"gen_seconds": round(time.monotonic() - start, 2)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate extract blocks.")
    parser.add_argument("--split", default="training")
    parser.add_argument("--data-root", type=Path, default=REPO_ROOT / "data/ARC-AGI")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--live-cap", type=int, default=LIVE_CAP)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    ss.add_args(parser)
    args = parser.parse_args(argv)
    if args.split != "training":
        parser.error("extractions are scored on training only")
    root = args.root or default_blocks_root()
    nested = args.data_root / "data" / args.split
    tasks = load_tasks(nested if nested.is_dir() else args.data_root / args.split)
    tasks = tasks[: args.limit] if args.limit else tasks
    cfg = (read_json(root / GENERATOR / "_metainfo.json", {}) or {}).get("config")  # type: ignore[union-attr]
    verdict, stats = run(tasks, root, args.live_cap, cfg, ss.from_args(args))
    stats = {"split": args.split, **stats}
    _ = args.dry_run or write_blocks(root, verdict, stats)
    print(json.dumps(stats))
    for c in verdict["live"][:5]:
        print(f"{c.name} {c.score} {json.dumps(c.body)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
