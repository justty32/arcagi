"""Exact main-line verdict: rerun a generator's training scoring with LLM bodies added.

``pred_verdict`` reproduces ``arcagi.blocks.gen_predicates.main`` in memory
(same segments, budget from ``pool.budget.allocate``, same ``judge`` and live
cap) with the LLM predicate bodies appended as extra candidates, and reports
which bucket each lands in: ``live`` / ``covered`` / ``over_cap`` /
``dropped``. A body the generator already enumerates is judged as that
candidate (``enumerated: true``). Read-only: nothing is written.
"""

import json
from collections.abc import Sequence

from . import tasks as tk


def pred_verdict(bodies: Sequence[list]) -> list[dict]:
    from arcagi.blocks import gen_predicates as gp
    from arcagi.blocks.pool.budget import allocate
    from arcagi.tasks import load_tasks

    tasks = load_tasks(tk.DATA_ROOT / "training")
    segs = gp.segments(tasks)
    budget = allocate()[gp.GENERATOR]
    cands = gp.score_candidates(segs, 2, budget)
    by_body = {json.dumps(c.body): c for c in cands}
    mine = []
    for body in bodies:
        key = json.dumps(body)
        if key in by_body:
            mine.append((body, by_body[key], True))
            continue
        tasks_ = frozenset(s.task for s in segs if s.mask(body) == s.label)
        cand = gp.Candidate(body, tasks_, len(cands))
        cands.append(cand)
        by_body[key] = cand
        mine.append((body, cand, False))
    verdict = gp.judge(cands, gp.LIVE_CAP)
    bucket = {}
    for name in ("live", "over_cap", "dropped"):
        for c in verdict[name]:
            bucket[id(c)] = (name, None)
    for c, by in verdict["covered"]:
        bucket[id(c)] = ("covered", by)
    out = []
    for body, cand, enumerated in mine:
        name, by = bucket.get(id(cand), ("covered", "beyond covered cap"))
        rank = None
        if name == "live":
            rank = verdict["live"].index(cand) + 1
        out.append(
            {
                "body": body,
                "name": cand.name,
                "score": cand.score,
                "tasks": len(cand.tasks),
                "verdict": name,
                "covered_by": by,
                "live_rank": rank,
                "enumerated": enumerated,
                "budget": budget,
            }
        )
    return out
