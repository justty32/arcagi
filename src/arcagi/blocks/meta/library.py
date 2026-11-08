"""Build a generated library on one fold and score it on the other.

``build`` runs the three generators (pred -> extract -> formula, the order their
inputs need) on the mining tasks into a scratch blocks root, optionally with the
synthetic-majority threshold. ``heldout`` re-judges the live blocks on the other
fold with each generator's own rule, then rates every claim on the synthetic
chunks: a task is *explained* when some live block supports it and passes the
majority; a *bad claim* is a supported task failing it. Net score per task =
explained - ``LAMBDA`` x bad claims (net marginal contribution over the empty
library: primitives are the same in every setting, so they cancel).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from arcagi.dsl import formula as fm
from arcagi.objrule import gen as objgen
from arcagi.tasks import Task

from .. import gen_extract as gx
from .. import gen_formula as gf
from .. import gen_predicates as gp
from .. import synth_score as ss
from ..pool.budget import allocate, top_extracts

LAMBDA = 1.0
KINDS = ("pred", "extract", "formula")


@dataclass
class Built:
    live: dict[str, list] = field(default_factory=dict)  # kind -> live candidates
    stats: dict[str, dict] = field(default_factory=dict)
    extracts: dict = field(default_factory=dict)

    @property
    def n_candidates(self) -> int:
        return sum(s.get("scored", 0) for s in self.stats.values())


def build(
    tasks: Sequence[Task],
    root: Path,
    views: ss.Views | None,
    configs: dict[str, dict] | None = None,
    reuse: Built | None = None,
) -> Built:
    """Run the generators on ``tasks`` writing into ``root``; ``reuse`` keeps
    its pred / extract results (already in ``root``) and reruns formula only."""
    cfg, out, budget = configs or {}, Built(), allocate()
    if reuse is not None:
        out.live = {k: reuse.live[k] for k in ("pred", "extract")}
        out.stats = {k: reuse.stats[k] for k in ("pred", "extract")}
    else:
        verdict, stats = gp.run(tasks, 2, budget[gp.GENERATOR], synth=views)
        gp.write_blocks(root, verdict, stats)
        out.live["pred"], out.stats["pred"] = verdict["live"], stats
        verdict, stats = gx.run(tasks, root, config=cfg.get("extract"), synth=views)
        gx.write_blocks(root, verdict, stats)
        out.live["extract"], out.stats["extract"] = verdict["live"], stats
    out.extracts = top_extracts(root)
    verdict, stats = gf.run(
        tasks,
        gf.LIVE_CAP,
        budget[gf.GENERATOR],
        out.extracts,
        cfg.get("formula"),
        views,
    )
    gf.write_blocks(root, verdict, stats)
    out.live["formula"], out.stats["formula"] = verdict["live"], stats
    return out


@dataclass
class _Claim:
    name: str
    body: object
    tasks: frozenset


def support(kind: str, cands: Sequence, tasks: Sequence[Task], extracts: dict):
    """name -> ids of ``tasks`` each block supports (its generator's rule)."""
    if not cands:
        return {}
    if kind == "formula":
        probs = gf.problems(tasks, extracts)
        return {
            c.name: {p.task for p in probs if fm.holds(c.body, p.xs, p.ys)}
            for c in cands
        }
    if kind == "pred":
        segs = gp.segments(tasks)
        return {
            c.name: {s.task for s in segs if s.mask(c.body) == s.label} for c in cands
        }
    out, grid = {}, [c for c in cands if isinstance(c.body, list)]
    sels = []
    for c in grid:
        sels += [c.body[1]] if c.body[1] not in sels else []
    found = {json.dumps(f.body): f.tasks for f in gx.score_candidates(tasks, sels)}
    out = {c.name: set(found.get(json.dumps(c.body), ())) for c in grid}
    obj = [c for c in cands if isinstance(c.body, dict)]
    if obj:
        for c, (_, ids) in zip(obj, objgen.score(tasks, [c.body for c in obj])):
            out[c.name] = set(ids)
    return out


def rates(kind: str, claims: Sequence[_Claim], views: ss.Views, extracts: dict):
    if kind == "formula":
        return ss.formula_rates(claims, views, extracts)
    return (
        ss.pred_rates(claims, views)
        if kind == "pred"
        else ss.extract_rates(claims, views)
    )


def heldout(built: Built, tasks: Sequence[Task], views: ss.Views) -> dict:
    """Per held-out task: explained (0/1), bad claims, net; and per-kind totals."""
    per = {t.task_id: {"explained": 0, "bad": 0} for t in tasks}
    kinds = {}
    for kind in KINDS:
        cands = built.live.get(kind, [])
        sup = support(kind, cands, tasks, built.extracts)
        claims = [_Claim(c.name, c.body, frozenset(sup[c.name])) for c in cands]
        claims = [c for c in claims if c.tasks]
        rate = rates(kind, claims, views, built.extracts) if claims else {}
        n_claims = n_bad = 0
        for c in claims:
            for t in c.tasks:
                ok = rate[c.name][t] >= ss.MAJORITY
                per[t]["explained"] |= int(ok)
                per[t]["bad"] += int(not ok)
                n_claims, n_bad = n_claims + 1, n_bad + int(not ok)
        kinds[kind] = {"live": len(cands), "claims": n_claims, "bad": n_bad}
    for row in per.values():
        row["net"] = row["explained"] - LAMBDA * row["bad"]
    explained = sum(r["explained"] for r in per.values())
    bad = sum(r["bad"] for r in per.values())
    return {
        "per_task": per,
        "explained": explained,
        "bad": bad,
        "kinds": kinds,
        "score": round(explained - LAMBDA * bad, 3),
    }


def paired(a: dict, b: dict) -> dict:
    """Task-level wins / losses of held-out result ``a`` over ``b``."""
    wins = sum(a["per_task"][t]["net"] > r["net"] for t, r in b["per_task"].items())
    loss = sum(a["per_task"][t]["net"] < r["net"] for t, r in b["per_task"].items())
    return {"wins": wins, "losses": loss, "net": wins - loss}
