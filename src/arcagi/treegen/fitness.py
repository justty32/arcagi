"""C25 evaluation, genome-keyed cache and activity-weighted conserved credit."""

import math
import shutil
from collections import Counter
from pathlib import Path

from arcagi.hammer.formats import NODES, append_jsonl, read_json, read_jsonl, write_json

from . import boundary, cost, credit, health, noise, quick

CFG = {"L": 25000, "epochs": 4, "clear_p": True}
METRICS = ("auc_L", "cost", "eff", "wall_s")


def activity_credit(root: Path) -> dict:
    """Reuse block-3 allocation with epoch-specific activity as layer-1 weights."""
    deltas = credit.amounts(cost.curves(root, range(5)))
    block_refs = health.load_script("think1_audit").block_refs
    events = Counter()
    owners = {
        "incubate": "grow",
        "promote": "judge",
        "demote": "judge",
        "retire": "judge",
    }
    for row in read_jsonl(root / "ledger.jsonl"):
        if row["kind"] in owners:
            events[(row["epoch"], owners[row["kind"]])] += 1
    rows, totals, diagnostics = [], {f"nodes/{name}": 0.0 for name in NODES}, {}
    for epoch, amount in deltas.items():
        boundary.check_stop()
        live = credit.live_ops(root, epoch)
        tasks, unassigned = credit.new_solves(root, epoch, block_refs)
        weights = {name: 1 + len(live[name]) + events[(epoch, name)] for name in NODES}
        allocated = credit.allocate(epoch, amount, weights, live, tasks)
        rows.extend(allocated)
        for row in allocated:
            if row["layer"] == 1 and row["to"] != "keep":
                totals[row["to"]] += row["amount"]
        diagnostics[str(epoch)] = {"activity": weights, "unassigned": unassigned}
    conservation, coverage = credit.check(rows, rows, totals, deltas)
    if not conservation["pass"] or not coverage["pass"]:
        raise ValueError("activity credit did not conserve")
    return {
        "credit_by_subtree": totals,
        "credit": rows,
        "activity": diagnostics,
        "conservation": conservation,
        "coverage": coverage,
    }


def comparison(parent_dir: Path, child_dir: Path, seed: int = 0) -> dict:
    """Keep undefined zero-sigma z as null and never claim significance for it."""
    result = noise.compare(parent_dir, child_dir, seed=seed)
    z = result["z"]
    return {
        "d_auc_L": result["delta_auc_L"],
        "sigma": result["sigma_auc_L"],
        "z": z,
        "degenerate": result["degenerate"],
        "significant": z is not None and abs(z) >= 2,
    }


def verify_fit(path: Path, sha: str, quick_dir: Path | None = None) -> list[str]:
    """Independently recompute efficiency and task AUC instead of trusting fit."""
    boundary.check_stop()
    errors = []
    try:
        fit = read_json(path)
        directory = quick_dir or path.parent / "quick"
        measured = read_json(directory / "quick.json")
        if measured["schema"] != "think2-quick/1":
            errors.append("fitness:invalid quick schema")
        if fit["genome_sha"] != sha or measured["genome_sha"] != sha:
            errors.append("fitness:genome_sha mismatch")
        for key in METRICS:
            a, b = fit[key], measured[key]
            if (
                type(a) not in (int, float)
                or not math.isfinite(a)
                or a < 0
                or type(b) not in (int, float)
                or not math.isfinite(b)
                or a != b
            ):
                errors.append(f"fitness:{key} differs from quick.json")
        auc = sum(row["auc"] for row in measured["per_task"].values())
        if auc != measured["auc_L"] or any(
            row["auc"] != sum(row["solved"]) for row in measured["per_task"].values()
        ):
            errors.append("fitness:auc_L differs from per_task")
        if not measured["per_task"] or any(
            len(row["solved"]) != 4
            or any(type(v) is not int or v not in (0, 1) for v in row["solved"])
            for row in measured["per_task"].values()
        ):
            errors.append("fitness:expected four binary epoch results per task")
        expected = round(auc / (measured["cost"] / 1_000_000), 4)
        if fit["eff"] != expected or measured["eff"] != expected:
            errors.append("fitness:eff recomputation mismatch")
        if any(measured["cfg"].get(k) != v for k, v in CFG.items()):
            errors.append("fitness:not C25")
        if not 1 <= measured["cfg"]["threads"] <= 4:
            errors.append("fitness:threads out of range")
        if fit.get("check", {}).get("ok") is not True:
            errors.append("fitness:missing successful F0 check")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ZeroDivisionError,
        OverflowError,
    ) as exc:
        errors.append(f"fitness:invalid:{exc}")
    return errors


def evaluate(
    directory: Path,
    checked: dict,
    cache: Path,
    *,
    parent_dir: Path | None = None,
    seed: int = 0,
    threads: int = 4,
) -> dict:
    """Evaluate or reuse one immutable genome, with no quick call on a hit."""
    boundary.check_stop()
    if not checked["ok"]:
        raise ValueError("fitness requires successful check")
    if not 1 <= threads <= 4:
        raise ValueError("GA threads must be between 1 and 4")
    doc = read_json(directory / "tree.json")
    sha = doc["genome_sha"]
    cached = {row["genome_sha"]: row for row in read_jsonl(cache)}.get(sha)
    qdir = directory / "quick"
    if cached is not None:
        source = Path(cached["directory"])
        errors = verify_fit(source / "fit.json", sha)
        if errors:
            raise ValueError("invalid fit_cache: " + "; ".join(errors))
        shutil.copytree(source / "quick", qdir)
        fit = {**read_json(source / "fit.json"), "cache_hit": True, "quick_ran": False}
    else:
        quick.prepare(directory / "tree.json", qdir / "root", **CFG)
        measured = quick.run(qdir / "root", epochs=4, threads=threads)
        if measured["guards"] != {"leak_new": "PASS", "leak_config": "PASS"}:
            raise ValueError("quick leak guard failed")
        activity = activity_credit(qdir / "root")
        write_json(qdir / "credit.json", activity)
        fit = {
            "schema": "think2-ga-fit/1",
            "genome_sha": sha,
            **{key: measured[key] for key in METRICS},
            "per_task": measured["per_task"],
            "credit_by_subtree": activity["credit_by_subtree"],
            "cache_hit": False,
            "quick_ran": True,
        }
    fit["check"] = checked
    # F0 counts refer to the genome, not the grown terminal quick tree.
    from .genome import expanded

    ops = expanded(doc)["ops.jsonl"]
    fit.update(n_live=sum(o["status"] == "live" for o in ops), n_ops=len(ops))
    fit["comparison"] = (
        comparison(parent_dir, qdir, seed)
        if parent_dir
        else comparison(qdir, qdir, seed)
    )
    write_json(directory / "fit.json", fit)
    errors = verify_fit(directory / "fit.json", sha)
    if errors:
        raise ValueError("; ".join(errors))
    if cached is None:
        append_jsonl(cache, {"genome_sha": sha, "directory": str(directory)})
    return fit
