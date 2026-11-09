"""One-generation block-4 pipeline and measured G1..G7 acceptance."""

import copy
import random
import subprocess
from pathlib import Path

from arcagi.hammer.formats import read_json, write_json

from . import (
    boundary,
    check,
    crossover,
    effect,
    fitness,
    genome,
    guards,
    ledger,
    mutate,
)
from . import select as selection
from .refs import sha12

ACCEPT = genome.REPORTS / "b4/accept.json"
MAX_DRAWS = 20


def _protected(doc: dict) -> dict:
    tree = genome.expanded(doc)
    frozen = tree["frozen.json"]
    return {
        "truth": sha12(tree["truth"]),
        **{key: sha12(frozen[key]) for key in ("holdout", "taskset")},
        **{key: sha12(frozen["budgets"][key]) for key in ("L", "epochs")},
    }


def _evo_status() -> list[str]:
    process = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=guards.REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in process.stdout.splitlines() if "evo" in line]


def _accept(
    parent: dict,
    children: list[dict],
    before: dict,
    after: dict,
    regression: dict,
    status: list[str],
) -> dict:
    fits = [read_json(Path(c["directory"]) / "fit.json") for c in children]
    documents = {parent["genome_sha"]: parent}
    documents.update(
        {
            c["genome_sha"]: read_json(Path(c["directory"]) / "tree.json")
            for c in children
        }
    )
    checks = []
    for child in children:
        directory = Path(child["directory"])
        parents = read_json(directory / "parents.json")["parents"]
        checks.append(
            check.check(directory / "tree.json", [documents[sha] for sha in parents])
        )
    redraws = [
        read_json(Path(c["directory"]) / "parents.json")["redraws"] for c in children
    ]
    effects = [read_json(Path(c["directory"]) / "effect.json") for c in children]
    effective = len(effects) == 8 and all(e["changed"] for e in effects[:7])
    errors = [
        error
        for c in children
        for error in fitness.verify_fit(
            Path(c["directory"]) / "fit.json", c["genome_sha"]
        )
    ]
    wall = sum(f["wall_s"] for f in fits if f["quick_ran"])
    hits = [f for f in fits if f["cache_hit"]]
    protected = _protected(parent)
    seals = [
        _protected(read_json(Path(c["directory"]) / "tree.json")) for c in children
    ]
    ref_errors = [
        error
        for c in children
        for error in check.references(read_json(Path(c["directory"]) / "tree.json"))
    ]
    changed = len(before.keys() ^ after.keys()) + sum(
        before[key] != after[key] for key in before.keys() & after.keys()
    )
    result = {
        "G1": {
            "pass": len(checks) == 8
            and all(c["ok"] for c in checks)
            and effective
            and all(n <= MAX_DRAWS for n in redraws),
            "children": len(checks),
            "legal": sum(c["ok"] for c in checks),
            "redraws": redraws,
            "max_redraws": max(redraws, default=0),
            "effective_children": sum(bool(e["changed"]) for e in effects[:7]),
        },
        "G2": {
            "pass": not errors
            and wall <= 1800
            and all(
                all(k in f["comparison"] for k in ("d_auc_L", "sigma", "z"))
                for f in fits
            ),
            "scored": len(fits),
            "quick_wall_s": wall,
            "errors": errors,
        },
        "G3": {
            "pass": bool(hits) and all(not f["quick_ran"] for f in hits),
            "cache_hits": len(hits),
            "quick_calls_on_hits": sum(f["quick_ran"] for f in hits),
        },
        "G4": {
            "pass": all(s == protected for s in seals),
            "matching": sum(s == protected for s in seals),
            "parent": protected,
            "children": seals,
        },
        "G5": {
            "pass": not ref_errors,
            "errors": len(ref_errors),
            "details": ref_errors,
        },
        "G6": {
            "pass": all(c["ok"] for c in checks),
            "bounds_or_leak_errors": sum(
                e.startswith(("bounds", "leak")) for c in checks for e in c["errors"]
            ),
            "inherited_taint": sum(len(c["inherited_taint"]) for c in checks),
        },
        "G7": {
            **regression,
            "pass": regression["pass"] and changed == 0 and not status,
            "live_files": len(before),
            "live_files_differ": changed,
            "evo_status_rows": len(status),
            "evo_status": status,
        },
    }
    return {
        "schema": "think2-ga-accept/1",
        "checks": result,
        "pass": all(c["pass"] for c in result.values()),
    }


def run(
    parent: str | Path,
    out: str | Path,
    ledger_dir: str | Path,
    *,
    pop: int = 8,
    gens: int = 1,
    seed: int = 0,
    threads: int = 4,
    accept: Path | None = None,
) -> dict:
    """Evaluate parent plus 5 mutations, X1, X3 and one deliberate cache clone."""
    boundary.check_stop()
    if pop != 8 or gens != 1:
        raise ValueError("block 4 supports exactly --pop 8 --gens 1")
    if not 1 <= threads <= 4:
        raise ValueError("GA threads must be between 1 and 4")
    parent, out = Path(parent).resolve(), genome.destination(out)
    if not out.is_relative_to(genome.EVO.resolve()):
        raise ValueError("GA population must be below evo (quick.prepare boundary)")
    if parent.is_relative_to(out):
        raise ValueError("GA output and parent must not overlap")
    doc = read_json(parent)
    checked = check.check(parent, parent)
    if not checked["ok"]:
        raise ValueError("parent check failed: " + "; ".join(checked["errors"]))
    guide = mutate.load_guide(ledger_dir, doc)
    before = ledger.snapshot(guards.LIVE_ROOT)
    boundary.empty_directory(out)
    write_json(out / "live_before.json", before)
    rng = random.Random(seed)
    parent_dir = out / "g0/parent"
    genome.write(parent_dir / "tree.json", doc, parent.parent / "files")
    write_json(parent_dir / "check.json", checked)
    write_json(
        parent_dir / "parents.json",
        {"parents": [], "arm": "clone", "ops": [], "redraws": 0},
    )
    cache = out / "fit_cache.jsonl"
    fit = fitness.evaluate(parent_dir, checked, cache, threads=threads, seed=seed)
    candidates = [
        {"directory": str(parent_dir), "genome_sha": doc["genome_sha"], "fit": fit}
    ]
    mutants, seen = [], {doc["genome_sha"]}
    children = []
    for index in range(8):
        failed = []
        for redraw in range(MAX_DRAWS):
            boundary.check_stop()
            if index < 5:
                child, record = mutate.mutate(doc, rng, guide)
                parents = [doc]
                if child["genome_sha"] in seen:
                    failed.append(["duplicate_mutation"])
                    continue
            elif index < 7:
                a, b = rng.sample(mutants, 2)
                try:
                    child, record = crossover.cross(
                        a, b, rng, operator="X1" if index == 5 else "X3"
                    )
                except ValueError as exc:
                    failed.append([str(exc)])
                    continue
                parents = [a, b]
            else:
                child = copy.deepcopy(doc)
                parents = [doc]
                record = {
                    "parents": [doc["genome_sha"]],
                    "arm": "clone",
                    "ops": [],
                    "redraws": 0,
                }
            checked = check.check(child, parents, files_dir=parent.parent / "files")
            if not checked["ok"]:
                failed.append(checked["errors"])
                continue
            if index == 7:
                probed = {"changed": [], "detail": {}, "skipped": "clone"}
                break
            probed = effect.probe(doc, child, files_dir=parent.parent / "files")
            if probed["changed"]:
                break
            paths = ",".join(op["path"] for op in record["ops"])
            failed.append([f"no_effect:{paths}"])
        else:
            write_json(
                out / "generation_failure.json", {"child": index, "attempts": failed}
            )
            raise ValueError(f"child {index}: exceeded {MAX_DRAWS} draws")
        record.update(
            redraws=redraw, rejected=failed, meter_track=effect.meter_track(doc, child)
        )
        directory = out / "g1" / f"{index}_{child['genome_sha']}"
        child = genome.write(directory / "tree.json", child, parent.parent / "files")
        write_json(directory / "parents.json", record)
        write_json(directory / "check.json", checked)
        write_json(directory / "effect.json", probed)
        if index < 5:
            mutants.append(child)
            seen.add(child["genome_sha"])
        fit = fitness.evaluate(
            directory,
            checked,
            cache,
            parent_dir=parent_dir / "quick",
            threads=threads,
            seed=seed,
        )
        candidate = {
            "directory": str(directory),
            "genome_sha": child["genome_sha"],
            "fit": fit,
        }
        children.append(candidate)
        candidates.append(candidate)
    selected = selection.select(
        candidates, out / "g1/select.json", out / "hall", seed=seed
    )
    regression = ledger._regression()
    after = ledger.snapshot(guards.LIVE_ROOT)
    write_json(out / "live_after.json", after)
    report = _accept(doc, children, before, after, regression, _evo_status())
    report.update(
        out=str(out),
        seed=seed,
        selected=selected["selected"],
        limitations=[
            "M4 and X2 are disabled; no external op bank.",
            "M5 has no targets: hammer does not read node weight.",
            "Effect probes use two tasks at budget 64, not a full equivalence test.",
            "Selection demonstrates plumbing, not efficacy.",
            "Activity event ownership is provisional; non-comb history uses "
            "the block-3 proxy.",
        ],
    )
    boundary.check_stop()
    write_json(ACCEPT if accept is None else accept, report)
    return report
