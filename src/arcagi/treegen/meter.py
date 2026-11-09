"""Prepare isolated learning meters and verify reports against raw artifacts."""

import re
import time
from datetime import UTC, datetime
from os import getpid
from pathlib import Path

from arcagi.grow import prog
from arcagi.hammer import epoch
from arcagi.hammer.check import check_root
from arcagi.hammer.formats import read_json, read_jsonl, write_json, write_jsonl

from . import boundary, quick
from .meter_stats import B_REF, bits_table, compare, score, select_taskset  # noqa: F401
from .refs import expand, genome_sha, sha12

RUN_BASE = quick.EVO / "meter"
SCRATCH = quick.METER_SCRATCH
PREPARED = "meter.prepare.json"


def _destination(run_dir: str | Path) -> Path:
    path = Path(run_dir).resolve()
    if not any(
        path != p.resolve() and path.is_relative_to(p.resolve())
        for p in (RUN_BASE, SCRATCH)
    ):
        raise ValueError(
            "meter destination must be below ws/evo/meter or scratchpad/t4b"
        )
    return path


def fresh_run(label: str, sha: str, base: str | Path = RUN_BASE) -> Path:
    """Name an unoccupied run; creation still uses an exclusive mkdir."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", label):
        raise ValueError("invalid meter label")
    utc = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return _destination(Path(base) / f"{label}_{sha[:8]}_{utc}_{getpid()}")


def source_tasks(src: str | Path) -> list[str]:
    """Return the parent's ordered L16+P calibration universe."""
    doc = read_json(Path(src))
    tree = expand(doc["tree"], doc["defs"])
    tasks = tree["truth"]["train"]["taskset.json"]
    return tasks["L16"] + tasks["P"]


def _stripped(doc: dict, ids: list[str], strip: str, probe: Path) -> list[str]:
    ops = expand(doc["tree"], doc["defs"])["ops.jsonl"]
    if strip == "all":
        return [o["id"] for o in ops if o["kind"] == "comb"]
    # Direct hits mean a successful e0 program actually invokes the comb;
    # src_tasks alone is not evidence of direct use.
    rows = read_jsonl(probe / "epochs/0/solutions.jsonl")
    if {r["task_id"] for r in rows} != set(ids) or len(rows) != len(ids):
        raise ValueError("targeted strip needs exactly one parent e0 row per task")
    names = {
        name
        for r in rows
        if r["train_ok"]
        for name in prog.ops(prog.from_json(r["program"]))
    }
    return [
        o["id"]
        for o in ops
        if o["kind"] == "comb" and o["payload"].get("name") in names
    ]


def prepare_meter(
    src: str | Path,
    run_dir: str | Path,
    taskset_ids: list[str],
    strip: str = "all",
    *,
    L: int = 50_000,  # noqa: N803 - Public meter budget name.
    epochs: int = 4,
    threads: int = 1,
) -> dict:
    """Call quick.prepare, then strip combs and replace tasks on the copy only."""
    boundary.check_stop()
    if strip not in ("all", "targeted"):
        raise ValueError("strip must be all or targeted")
    if not 1 <= threads <= 4 or L <= 0 or epochs < 0:
        raise ValueError("need threads 1..4, positive L and nonnegative epochs")
    source, directory = Path(src).resolve(), _destination(run_dir)
    doc = read_json(source)
    if not doc or doc["genome_sha"] != genome_sha(doc["defs"], doc["tree"]):
        raise ValueError("source genome_sha mismatch")
    ids = list(taskset_ids)
    if (
        not ids
        or len(ids) != len(set(ids))
        or not set(ids) <= set(source_tasks(source))
    ):
        raise ValueError("taskset must be a nonempty unique subset of parent L16+P")
    tree = expand(doc["tree"], doc["defs"])
    cal = tree["truth"]["cal"]["ids.json"]
    if set(ids) & (set(cal["H8"]) | set(cal["H24"])):
        raise ValueError("meter taskset overlaps holdouts")
    # Refuse even an empty existing directory, including an earlier failed run.
    directory.mkdir(parents=True, exist_ok=False)
    root = directory / "root"
    metadata = quick.prepare(source, root, L=L, epochs=epochs)
    write_json(directory / "source.json", doc)
    taskset = read_json(root / "truth/train/taskset.json")
    taskset.update(L16=ids, P=[])
    write_json(root / "truth/train/taskset.json", taskset)
    if strip == "targeted":
        probe = directory / "targeted-probe/root"
        quick.prepare(source, probe, L=L, epochs=0)
        write_json(probe / "truth/train/taskset.json", taskset)
        epoch.run_tree(
            probe,
            "hammer-frozen",
            epochs=0,
            threads=threads,
            holdout=False,
            log=lambda message: quick._stop(probe),
        )
    removed = _stripped(doc, ids, strip, directory / "targeted-probe/root")
    ops = [o for o in read_jsonl(root / "ops.jsonl") if o["id"] not in set(removed)]
    write_jsonl(root / "ops.jsonl", ops)
    write_jsonl(directory / "initial_ops.jsonl", ops)
    errors = check_root(root)
    meta = {
        "schema": "think4-meter/1",
        "genome_sha": metadata["genome_sha"],
        "cfg": {
            "B_ref": B_REF,
            "L": L,
            "E": epochs,
            "strip": strip,
            "taskset_sha": sha12(ids),
            "threads": threads,
            "holdout": False,
        },
        "task_ids": ids,
        "stripped_ops": removed,
        "original_comb_count": sum(o["kind"] == "comb" for o in tree["ops.jsonl"]),
        "prepared_check_root_errors": len(errors),
        "dumb": doc.get("dumb"),
    }
    boundary.check_stop()
    write_json(directory / PREPARED, meta)
    if errors:
        raise ValueError(f"meter check_root failed: {errors}")
    return meta


def _gates(directory: Path, meta: dict) -> dict:
    root = directory / "root"
    doc = read_json(directory / "source.json")
    tree = expand(doc["tree"], doc["defs"])
    cal = tree["truth"]["cal"]["ids.json"]
    # Calibration deliberately reclassifies selected P tasks as L16. The
    # remaining quarantined P tasks and all holdouts still cannot feed ops.
    forbidden = (
        set(cal["H8"])
        | set(cal["H24"])
        | (set(tree["truth"]["train"]["taskset.json"]["P"]) - set(meta["task_ids"]))
    )
    ops = read_jsonl(root / "ops.jsonl")
    violations = []
    for op in ops:
        tasks = set(op["payload"].get("src_tasks", [])) | set(
            op["evidence"]["new_solves"]
        )
        if tasks & forbidden:
            violations.append({"op_id": op["id"], "tasks": sorted(tasks & forbidden)})
    base = {o["id"] for o in read_jsonl(directory / "initial_ops.jsonl")}
    new = [o["id"] for o in ops if o["id"] not in base]
    ledger = read_jsonl(root / "ledger.jsonl")
    taskset = read_json(root / "truth/train/taskset.json")
    gates = {
        "check_root_errors": len(check_root(root)),
        "leak": "FAIL" if taskset["P"] or violations else "PASS",
        "leak_violations": violations,
        "quarantined_ids": sorted(forbidden),
        "promotes": sum(len(r["op_ids"]) for r in ledger if r["kind"] == "promote"),
        "new_ops": len(new),
        "new_ops_ids": new,
    }
    if read_json(root / "_metainfo.json").get("meter_freeze_uses") is True:
        gates["freeze_uses"] = True
    return gates


def _report(directory: Path) -> dict:
    meta = read_json(directory / PREPARED)
    table = bits_table(directory / "root", meta["cfg"]["E"])
    wall = read_json(directory / "timing.json")["wall_s"]
    return {
        **meta,
        "per_task": table,
        "scores": score(table, wall_s=wall),
        "gates": _gates(directory, meta),
    }


def run(run_dir: str | Path) -> dict:
    """Run real epochs 0..E, without holdout searches, and publish meter.json."""
    directory = _destination(run_dir)
    root = directory / "root"
    meta = read_json(directory / PREPARED)
    if not meta or (directory / "meter.json").exists() or (root / "epochs").exists():
        raise ValueError("meter run must be freshly prepared and never run before")
    freeze_uses = read_json(root / "_metainfo.json").get("meter_freeze_uses") is True
    started = time.perf_counter()
    quick._stop(root)

    def after_epoch(message: str) -> None:
        quick._stop(root)
        if freeze_uses:
            # run_epoch writes state.json (epoch.py:455) before run_tree logs.
            path = root / "live/state.json"
            state = read_json(path)
            state["uses"] = {}
            write_json(path, state)
        print(message, flush=True)

    epoch.run_tree(
        root,
        "hammer",
        epochs=meta["cfg"]["E"],
        threads=meta["cfg"]["threads"],
        holdout=False,
        log=after_epoch,
    )
    quick._stop(root)
    write_json(directory / "timing.json", {"wall_s": time.perf_counter() - started})
    result = _report(directory)
    write_json(directory / "meter.json", result)
    return result


def verify(run_dir: str | Path) -> dict:
    """Recompute all measured fields and audit source hash/config; fail closed."""
    boundary.check_stop()
    directory = Path(run_dir)
    errors = []
    try:
        actual = read_json(directory / "meter.json")
        expected = _report(directory)
        if actual != expected:
            errors.append("meter.json differs from raw recomputation")
        doc = read_json(directory / "source.json")
        sha = genome_sha(doc["defs"], doc["tree"])
        if sha != doc["genome_sha"] or sha != expected["genome_sha"]:
            errors.append("genome_sha mismatch")
        ids, cfg = expected["task_ids"], expected["cfg"]
        root = directory / "root"
        taskset = read_json(root / "truth/train/taskset.json")
        if cfg["B_ref"] != B_REF or cfg["taskset_sha"] != sha12(ids):
            errors.append("fixed B_ref/taskset_sha mismatch")
        if not 1 <= cfg["threads"] <= 4 or cfg["holdout"] is not False:
            errors.append("threads/holdout mismatch")
        tree = expand(doc["tree"], doc["defs"])
        if read_json(root / "_metainfo.json") != tree["_metainfo.json"]:
            errors.append("root config differs from source")
        frozen = tree["frozen.json"]
        frozen["budgets"].update(L=cfg["L"], epochs=cfg["E"])
        if read_json(root / "frozen.json") != frozen:
            errors.append("frozen config differs from source plus meter budgets")
        for name, node in tree["nodes"].items():
            if (
                read_json(root / "nodes" / name / "_metainfo.json")
                != node["_metainfo.json"]
            ):
                errors.append(f"node config differs from source: {name}")
        if ids != taskset["L16"] or taskset["P"]:
            errors.append("taskset mismatch")
        removed = _stripped(doc, ids, cfg["strip"], directory / "targeted-probe/root")
        if removed != expected["stripped_ops"]:
            errors.append("stripped_ops mismatch")
        original = expand(doc["tree"], doc["defs"])["ops.jsonl"]
        initial = read_jsonl(directory / "initial_ops.jsonl")
        definitions = [
            {k: o[k] for k in boundary.OP_DEFINITION_FIELDS} for o in initial
        ]
        if definitions != [o for o in original if o["id"] not in set(removed)]:
            errors.append("initial ops differ from stripped source")
        count = sum(o["kind"] == "comb" for o in original)
        if expected["original_comb_count"] != count:
            errors.append("original_comb_count mismatch")
        if (
            expected["prepared_check_root_errors"]
            or expected["gates"]["check_root_errors"]
        ):
            errors.append("check_root failed")
        if expected["gates"]["leak"] != "PASS":
            errors.append("leak failed")
        if cfg["strip"] == "all" and len(removed) != count:
            errors.append("strip=all did not remove every original comb")
        if expected["dumb"] != doc.get("dumb"):
            errors.append("dumb provenance mismatch")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OverflowError,
    ) as exc:
        errors.append(f"invalid meter artifacts: {exc}")
    return {
        "status": "FAIL" if errors else "PASS",
        "pass": not errors,
        "errors": errors,
    }
