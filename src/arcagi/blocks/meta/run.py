"""Two-fold meta experiment on an empty scratch library (nothing live touched).

Run: ``python -m arcagi.blocks.meta --scratch DIR [--out result.json]``. The
empty base copies ``aos/blocks`` without ``extract_*`` / ``formula_*`` /
``pred_*`` and with generator configs cleared; the pool is an empty scratch pool
(``$ARCAGI_POOL``: equal budgets, no income). Training tasks are split by sorted
index (odd / even); generators mine on one fold and are scored on the other
(``library.heldout``), then the folds swap. Per fold: ablation A0 (defaults, no
synthetic threshold), A1 (defaults + threshold, the baseline), A1 again with
shuffled task order (noise), then single-knob extract and formula settings
(``gen_meta``) + threshold. A setting is adopted when its paired task-level net
wins over A1 are > 0 in both folds. Every build is one meta-ledger row.
"""

import json
import os
import random
import shutil
from pathlib import Path

from arcagi.tasks import load_tasks

from .. import REPO_ROOT, read_json, write_json
from .. import gen_formula as gf
from .. import gen_meta as gm
from .. import synth_score as ss
from . import ledger, library

GENERATED = ("extract_", "formula_", "pred_")
TRAINING = REPO_ROOT / "data" / "ARC-AGI" / "data" / "training"


def empty_base(scratch: Path) -> Path:
    """Scratch blocks root without generated blocks, plus an empty pool."""
    base = scratch / "base"
    if base.exists():
        shutil.rmtree(base)
    src = REPO_ROOT / "aos" / "blocks"
    skip = lambda d, names: [n for n in names if n.startswith(GENERATED)]  # noqa: E731
    shutil.copytree(src, base, ignore=lambda d, n: skip(d, n) if d == str(src) else [])
    for meta in (base / "_gen").glob("*/_metainfo.json"):
        data = read_json(meta, {}) or {}
        data.pop("config", None)  # type: ignore[union-attr]
        write_json(meta, data)
    pool = scratch / "pool"
    pool.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "aos" / "pool" / "config.json", pool / "config.json")
    os.environ["ARCAGI_POOL"] = str(pool)
    return base


def fresh(base: Path, root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(base, root)
    os.environ["ARCAGI_BLOCKS"] = str(root)
    return root


def _row(label, layer, target, setting, root, built, res, timer, n, **kw) -> dict:
    return ledger.append(
        {
            "run_id": label,
            "layer": layer,
            "target_gen": target,
            "setting": setting,
            "seed": "none (deterministic generators)",
            "blocks_root_hash": ledger.blocks_root_hash(root),
            "cost_wall_s": timer.wall,
            "cost_cpu_s": timer.cpu,
            "n_tasks": n,
            "n_candidates": built.n_candidates,
            "score_main": res["score"],
            "score_div": None,
            "explained": res["explained"],
            "bad_claims": res["bad"],
            "kinds": res["kinds"],
            **kw,
        }
    )


def fold(name, mine, held, base, scratch, views, formula_base, run_id) -> dict:
    """All builds of one fold; returns held-out results by setting label."""
    off = ss.Views(views.chunks, narrow=False)
    out: dict[str, dict] = {}

    def go(label, layer, target, setting, cfgs, v, reuse=None, tasks=mine, **kw):
        root = scratch / name / label.replace("/", "_")
        if reuse is not None:
            shutil.rmtree(root, ignore_errors=True)
            shutil.copytree(reuse[1], root)
            os.environ["ARCAGI_BLOCKS"] = str(root)
        else:
            fresh(base, root)
        with ledger.Timer() as t:
            built = library.build(tasks, root, v, cfgs, reuse[0] if reuse else None)
            res = library.heldout(built, held, views)
        ref = out.get("A1")
        cmp = library.paired(res, ref["res"]) if ref else None
        rid = f"{run_id}/{name}/{label}"
        _row(
            rid,
            layer,
            target,
            setting,
            root,
            built,
            res,
            t,
            len(mine),
            note=name,
            baseline_ref=f"{run_id}/{name}/A1" if ref else None,
            delta=round(res["score"] - ref["res"]["score"], 3) if ref else None,
            sigma=0.0,
            paired=cmp,
            **kw,
        )
        out[label] = {
            "res": res,
            "built": built,
            "root": root,
            "paired": cmp,
            "setting": setting,
        }
        print(
            json.dumps(
                {
                    "run": rid,
                    "score": res["score"],
                    "explained": res["explained"],
                    "bad": res["bad"],
                    "paired": cmp,
                }
            ),
            flush=True,
        )

    go("A0", 0, "all", {"synth": False}, {}, off, accepted=None)
    go("A1", 0, "all", {"synth": True}, {}, views, accepted=None)
    shuffled = list(mine)
    random.Random(0).shuffle(shuffled)
    go(
        "A1-shuffled",
        0,
        "all",
        {"synth": True, "order": "shuffled"},
        {},
        views,
        tasks=shuffled,
        accepted=None,
    )
    for i, cfg in enumerate(gm.extract_mutations({})[1:], 1):
        go(
            f"extract/{i}",
            1,
            "_gen/extract",
            cfg,
            {"extract": cfg},
            views,
            accepted=None,
        )
    a1 = (out["A1"]["built"], out["A1"]["root"])
    for i, cfg in enumerate(gm.mutations(formula_base)[1:], 1):
        go(
            f"formula/{i}",
            1,
            gf.GENERATOR,
            cfg,
            {"formula": cfg},
            views,
            reuse=a1,
            accepted=None,
        )
    for label, row in out.items():
        row.pop("built")
    return out


def main(scratch: Path, out_path: Path | None = None) -> dict:
    views = ss.load()
    if views is None:
        raise SystemExit("data_synth missing: run scripts/synth_generate.py")
    base = empty_base(scratch)
    tasks = sorted(load_tasks(TRAINING), key=lambda t: t.task_id)
    odd, even = tasks[1::2], tasks[0::2]
    real = read_json(REPO_ROOT / "aos/blocks" / gf.GENERATOR / "_metainfo.json", {})
    formula_base = (real or {}).get("config") or {}  # type: ignore[union-attr]
    run_id = "r06-meta-" + ledger.base_commit()
    folds = {
        "odd->even": fold("odd", odd, even, base, scratch, views, formula_base, run_id),
        "even->odd": fold(
            "even", even, odd, base, scratch, views, formula_base, run_id
        ),
    }
    labels = [k for k in folds["odd->even"] if "/" in k]
    verdict = {}
    for label in labels:
        nets = [folds[f][label]["paired"]["net"] for f in folds]
        verdict[label] = {
            "nets": nets,
            "accepted": all(n > 0 for n in nets),
            "setting": folds["odd->even"][label]["setting"],
        }
    summary = {
        "folds": {
            f: {
                k: {
                    "score": v["res"]["score"],
                    "explained": v["res"]["explained"],
                    "bad": v["res"]["bad"],
                    "kinds": v["res"]["kinds"],
                    "paired": v["paired"],
                }
                for k, v in rows.items()
            }
            for f, rows in folds.items()
        },
        "verdict": verdict,
    }
    ledger.append(
        {
            "run_id": run_id + "/verdict",
            "layer": 1,
            "target_gen": "_gen/extract+_gen/formula",
            "setting": {"rule": "both folds net>0"},
            "accepted": [k for k, v in verdict.items() if v["accepted"]],
            "note": json.dumps({k: v["nets"] for k, v in verdict.items()}),
        }
    )
    if out_path:
        out_path.write_text(json.dumps(summary, indent=1, default=str))
    return summary
