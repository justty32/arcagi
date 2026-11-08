"""Generator of generator settings: one level of meta search over ``gen_formula``.

Run: ``uv run python -m arcagi.blocks.gen_meta [--dry-run]``. Starting from the
formula generator's current ``config`` (node metainfo, default
``gen_formula.CONFIG``), try at most ``MAX_TRIALS`` settings: the current one
and single-knob mutations of it (extract features 0 / 10 / 20, two layers on /
off, minimum support 1 / 2, one-layer forms all / without ``sq`` and ``div``).
Each runs the generator without writing blocks on training.

Cheap score = ``explained - candidates / CANDIDATES_PER_TASK``: ``explained`` is
the number of training tasks in the union of supports of the live bodies, and
every ``CANDIDATES_PER_TASK`` scored candidates cost one task. Ties keep the
earlier setting (the current one first). The best setting is written to
``<root>/_gen/formula/_metainfo.json`` as ``config`` (read by ``gen_formula``);
every trial and its score go to ``<root>/_gen/_meta/_metainfo.json``. The tree
stops at ``LEVELS`` = 2: this node is hand-written and never generated.
"""

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from arcagi.dsl import formula as fm
from arcagi.tasks import Task, load_tasks

from . import REPO_ROOT, default_blocks_root, read_json, write_json
from . import gen_formula as gf
from .pool.budget import allocate, top_extracts

NODE = "_gen/_meta"
LEVELS = 2  # blocks <- generators <- this node; nothing generates this node
MAX_TRIALS = 8
CANDIDATES_PER_TASK = 1000
SHORT_FORMS = [op for op in fm.OPS if op not in ("sq", "div")]
ENTRY = """#!/bin/sh
# aos meta node: tune the formula generator's config on training (--dry-run:
# print the trials, write nothing).
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../../.." && pwd)
cd "$root" && exec "$root/.venv/bin/python" -m arcagi.blocks.gen_meta "$@"
"""


def mutations(base: dict) -> list[dict]:
    """``base`` then its single-knob mutations, at most ``MAX_TRIALS``."""
    full = list(fm.OPS)
    knobs = {
        "n_extracts": [0, 10, 20],
        "two_layer": [True, False],
        "min_support": [1, 2],
        "forms": [full, SHORT_FORMS],
    }
    base = {**gf.CONFIG, **base, "forms": list(base.get("forms", full))}
    out = [base]
    for key, values in knobs.items():
        out += [{**base, key: v} for v in values if v != base[key]]
    return out[:MAX_TRIALS]


def score(verdict: dict, stats: dict) -> float:
    explained = set().union(*(c.tasks for c in verdict["live"]))
    return round(len(explained) - stats["scored"] / CANDIDATES_PER_TASK, 3)


def trials(
    tasks: Sequence[Task], base: dict, budget: int | None, extracts: dict
) -> list[dict]:
    """Every tried setting with its stats and cheap score (no blocks written)."""
    rows = []
    for cfg in mutations(base):
        verdict, stats = gf.run(tasks, gf.LIVE_CAP, budget, extracts, cfg)
        explained = len(set().union(*(c.tasks for c in verdict["live"])))
        rows.append(
            {
                "config": cfg,
                "score": score(verdict, stats),
                "explained": explained,
                "scored": stats["scored"],
                "live": stats["live"],
                "covered": stats["covered"],
            }
        )
    return rows


def best(rows: Sequence[dict]) -> dict:
    return max(rows, key=lambda r: (r["score"], -rows.index(r)))


def write(root: Path, rows: list[dict], chosen: dict) -> None:
    node = root / NODE
    old = read_json(node / "_metainfo.json", {}) or {}
    meta = {"name": NODE, "kind": "generator", "cost": 1, "status": "live"}
    meta["doc"] = "Tunes the formula generator's config (one meta level, cap 2)."
    meta |= {"params": ["--dry-run"], "produces": "config", "levels": LEVELS}
    meta |= {"counter_uses": old.get("counter_uses", 0)}  # type: ignore[union-attr]
    meta |= {"targets": [gf.GENERATOR], "trials": rows, "best": chosen}
    write_json(node / "_metainfo.json", meta)
    entry = node / "_entry"
    entry.write_text(ENTRY, encoding="utf-8")
    os.chmod(entry, 0o755)
    gen = root / gf.GENERATOR / "_metainfo.json"
    gen_meta = read_json(gen, {}) or {}
    write_json(gen, {**gen_meta, "config": chosen["config"]})  # type: ignore[dict-item]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tune the formula generator.")
    parser.add_argument("--data-root", type=Path, default=REPO_ROOT / "data/ARC-AGI")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root or default_blocks_root()
    nested = args.data_root / "data" / "training"
    tasks = load_tasks(nested if nested.is_dir() else args.data_root / "training")
    current = (read_json(root / gf.GENERATOR / "_metainfo.json", {}) or {}).get(  # type: ignore[union-attr]
        "config"
    ) or {}
    budget = allocate()[gf.GENERATOR]
    rows = trials(tasks, current, budget, top_extracts(args.root))
    chosen = best(rows)
    for row in rows:
        print(json.dumps(row))
    print(json.dumps({"best": chosen["config"], "changed": chosen is not rows[0]}))
    if not args.dry_run:
        write(root, rows, chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
