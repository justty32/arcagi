"""How much do generated blocks memorise? Re-check their support on synthetic pairs.

Run (after ``scripts/synth_generate.py``)::

    nice -n 19 .venv/bin/python scripts/synth_overfit.py \\
        --out reports/synth-s5/overfit.json [--preview]

For every formula / pred / extract block in ``aos/blocks`` (read only;
``--status`` picks which statuses) the support set is recomputed with the
generators' own judgement (``gen_formula.problems`` + ``formula.holds``,
``gen_predicates.segments`` + ``Segment.mask``, ``gen_extract.score_candidates``
and ``objrule.gen.score``) on three views of each training task:

* ``orig``  - the original train pairs (what the generator scored on);
* ``synth`` - all synthetic pairs of ``data_synth`` (``train[n_original:]``);
* ``chunk`` - the synthetic pairs cut into chunks of ``--chunk`` pairs, i.e.
  resamples the size of a real task;
* ``heldout`` - original train + original test pairs: the in-distribution
  control (does the claim survive the task's own held-out test pair?).

A (block, task) claim is one task in the block's ``orig`` support. It is
*memorised* (strict) when the task drops out of the ``synth`` support, and
*mostly memorised* when it survives fewer than half of the chunks.
``--preview`` also re-runs each generator's full judge on the plug-in layout
(original + synthetic pairs) and diffs the live sets. Evaluation is never read.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arcagi.blocks import gen_extract as gx  # noqa: E402
from arcagi.blocks import gen_formula as gf  # noqa: E402
from arcagi.blocks import gen_predicates as gp  # noqa: E402
from arcagi.blocks.catalog import load_catalog  # noqa: E402
from arcagi.blocks.pool.budget import allocate, top_extracts  # noqa: E402
from arcagi.dsl import formula as fm  # noqa: E402
from arcagi.dsl import predicates as pr  # noqa: E402
from arcagi.objrule import gen as objgen  # noqa: E402
from arcagi.tasks import Task, load_tasks  # noqa: E402

TRAINING = ROOT / "data" / "ARC-AGI" / "data" / "training"
KINDS = ("formula", "pred", "extract")


def load_blocks(root: Path, statuses: set[str]) -> list[dict]:
    out = []
    for folder in sorted(root.iterdir()):
        meta_path, rule_path = folder / "_metainfo.json", folder / "_rule.json"
        if not (meta_path.is_file() and rule_path.is_file()):
            continue
        meta = json.loads(meta_path.read_text())
        if meta.get("kind") not in KINDS or meta.get("status") not in statuses:
            continue
        rule = json.loads(rule_path.read_text())
        out.append(
            {
                "name": folder.name,
                "kind": meta["kind"],
                "status": meta["status"],
                "rule": rule,
            }
        )
    return out


def views(synth_root: Path, chunk: int) -> tuple:
    """(original, synthetic-only, chunks[k], held-out) task lists; same ids."""
    manifest = json.loads((synth_root / "manifest.json").read_text())
    full = {t.task_id: t for t in load_tasks(synth_root / "training")}
    orig, synth, heldout, chunks = [], [], [], defaultdict(list)
    for task_id, entry in sorted(manifest["tasks"].items()):
        task, n = full[task_id], entry["n_original"]
        orig.append(Task(task_id, task.train[:n], task.test))
        heldout.append(Task(task_id, task.train[:n] + task.test, task.test))
        pairs = task.train[n:]
        synth.append(Task(task_id, pairs, task.test))
        for k in range(len(pairs) // chunk):
            chunks[k].append(
                Task(task_id, pairs[k * chunk : (k + 1) * chunk], task.test)
            )
    return orig, synth, [chunks[k] for k in sorted(chunks)], heldout


def support(blocks: list[dict], tasks: list[Task]) -> dict[str, set[str]]:
    """Block name -> ids of ``tasks`` it supports (generator judgement)."""
    out: dict[str, set[str]] = {b["name"]: set() for b in blocks}
    by_kind = defaultdict(list)
    for b in blocks:
        by_kind[b["kind"]].append(b)
    if by_kind["formula"]:
        extracts: dict = {}
        for b in by_kind["formula"]:
            extracts |= b["rule"].get("extracts", {})
        probs = gf.problems(tasks, extracts)
        for b in by_kind["formula"]:
            body = b["rule"]["body"]
            out[b["name"]] = {p.task for p in probs if fm.holds(body, p.xs, p.ys)}
    if by_kind["pred"]:
        segs = gp.segments(tasks)
        for b in by_kind["pred"]:
            body = b["rule"]["body"]
            out[b["name"]] = {s.task for s in segs if s.mask(body) == s.label}
    grid = [b for b in by_kind["extract"] if isinstance(b["rule"]["body"], list)]
    obj = [b for b in by_kind["extract"] if isinstance(b["rule"]["body"], dict)]
    if grid:
        sels = []
        for b in grid:
            if b["rule"]["body"][1] not in sels:
                sels.append(b["rule"]["body"][1])
        found = {json.dumps(c.body): c.tasks for c in gx.score_candidates(tasks, sels)}
        for b in grid:
            out[b["name"]] = set(found.get(json.dumps(b["rule"]["body"]), ()))
    if obj:
        scored = objgen.score(tasks, [b["rule"]["body"] for b in obj])
        for b, (_, ids) in zip(obj, scored, strict=True):
            out[b["name"]] = set(ids)
    return out


def measure(blocks: list[dict], orig, synth, chunks, heldout) -> dict:
    s_orig, s_synth = support(blocks, orig), support(blocks, synth)
    s_held = support(blocks, heldout)
    s_chunks = [support(blocks, c) for c in chunks]
    rows, per_block = [], []
    for b in blocks:
        name, claims = b["name"], sorted(s_orig[b["name"]])
        kept = 0
        for task_id in claims:
            rate = sum(task_id in sc[name] for sc in s_chunks) / max(len(s_chunks), 1)
            strict = task_id in s_synth[name]
            kept += strict
            rows.append(
                {
                    "block": name,
                    "kind": b["kind"],
                    "status": b["status"],
                    "task": task_id,
                    "synth_pass": strict,
                    "heldout_pass": task_id in s_held[name],
                    "chunk_pass_rate": round(rate, 3),
                }
            )
        per_block.append(
            {
                "block": name,
                "kind": b["kind"],
                "status": b["status"],
                "orig_support": len(claims),
                "synth_kept": kept,
                "synth_new": len(s_synth[name] - set(claims)),
                "body": b["rule"]["body"],
            }
        )
    return {"claims": rows, "blocks": per_block}


def summarise(result: dict) -> dict:
    out = {}
    groups = defaultdict(list)
    for r in result["claims"]:
        groups[r["kind"]].append(r)
        groups[f"{r['kind']}/{r['status']}"].append(r)
        groups["all"].append(r)
    for key, rows in sorted(groups.items()):
        n = len(rows)
        strict = sum(not r["synth_pass"] for r in rows)
        mostly = sum(r["chunk_pass_rate"] < 0.5 for r in rows)
        held = sum(not r["heldout_pass"] for r in rows)
        out[key] = {
            "claims": n,
            "memorised": strict,
            "memorised_rate": round(strict / n, 3) if n else None,
            "mostly_memorised": mostly,
            "mostly_rate": round(mostly / n, 3) if n else None,
            "heldout_fail": held,
            "heldout_fail_rate": round(held / n, 3) if n else None,
        }
    blocks = result["blocks"]
    out["blocks"] = {
        "total": len(blocks),
        "with_support": sum(b["orig_support"] > 0 for b in blocks),
        "all_support_lost": sum(
            b["orig_support"] > 0 and b["synth_kept"] == 0 for b in blocks
        ),
    }
    return out


def preview(blocks_root: Path, synth_root: Path) -> dict:
    """Live sets of each generator on training vs the plug-in layout."""
    budget = allocate()
    pr.install(load_catalog(blocks_root).predicates())
    out = {}
    for label, path in (("training", TRAINING), ("synth", synth_root / "training")):
        tasks = load_tasks(path)
        t0 = time.perf_counter()
        verdict, _ = gf.run(
            tasks, budget=budget[gf.GENERATOR], extracts=top_extracts(blocks_root)
        )
        live = {"formula": [c.name for c in verdict["live"]]}
        segs = gp.segments(tasks)
        cands = gp.score_candidates(segs, 2, budget[gp.GENERATOR])
        live["pred"] = [c.name for c in gp.judge(cands)["live"]]
        cands = gx.score_candidates(tasks, gx.selectors(sorted(pr.LIVE)))
        bodies = objgen.all_bodies()[: objgen.budget(gx.GENERATOR, len(cands))]
        for body, ids in objgen.score(tasks, bodies):
            cands.append(gx.Candidate(body, ids, len(cands)))
        live["extract"] = [c.name for c in gx.judge(cands)["live"]]
        out[label] = {"live": live, "seconds": round(time.perf_counter() - t0, 1)}
    diff = {}
    for kind in KINDS:
        a, b = set(out["training"]["live"][kind]), set(out["synth"]["live"][kind])
        diff[kind] = {
            "training_live": len(a),
            "synth_live": len(b),
            "kept": len(a & b),
            "dropped": sorted(a - b),
            "added": sorted(b - a),
        }
    return {"diff": diff, "seconds": {k: v["seconds"] for k, v in out.items()}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--blocks", type=Path, default=ROOT / "aos" / "blocks")
    parser.add_argument("--synth", type=Path, default=ROOT / "data_synth")
    parser.add_argument("--chunk", type=int, default=3)
    parser.add_argument("--status", nargs="+", default=["live", "covered"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(argv)
    t0 = time.perf_counter()
    pr.install(load_catalog(args.blocks).predicates())
    blocks = load_blocks(args.blocks, set(args.status))
    orig, synth, chunks, heldout = views(args.synth, args.chunk)
    result = measure(blocks, orig, synth, chunks, heldout)
    report = {
        "schema": "arcagi-synth-overfit/1",
        "statuses": args.status,
        "chunk": args.chunk,
        "n_chunks": len(chunks),
        "summary": summarise(result),
        **result,
    }
    if args.preview:
        report["preview"] = preview(args.blocks, args.synth)
    report["seconds"] = round(time.perf_counter() - t0, 1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report["summary"], indent=1))
    if "preview" in report:
        print(
            json.dumps(
                {
                    k: {x: v[x] for x in ("training_live", "synth_live", "kept")}
                    for k, v in report["preview"]["diff"].items()
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
