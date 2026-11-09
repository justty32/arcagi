"""Prepare isolated hammer replicas and measure their short search curves."""

import hashlib
import importlib.util
import shutil
import time
from pathlib import Path

from arcagi.hammer import epoch
from arcagi.hammer.check import check_root
from arcagi.hammer.formats import read_json, read_jsonl, write_json, write_jsonl

from . import boundary, guards
from .import_ import import_tree
from .refs import deduplicate, genome_sha

EVO = Path("/home/lorkhan/code/playground-arc1/ws/evo")
SCRATCH = Path(
    "/tmp/claude-1000/-home-lorkhan-repo-arcagi/"
    "b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t2c"
)
METER_SCRATCH = SCRATCH.with_name("t4b")
PREPARED = "quick.prepare.json"


def _destination(dest: str | Path) -> Path:
    root = Path(dest).resolve()
    if not any(
        root != allowed.resolve() and root.is_relative_to(allowed.resolve())
        for allowed in (EVO, SCRATCH, METER_SCRATCH)
    ):
        raise ValueError(
            f"quick destination must be below {EVO}, {SCRATCH} or {METER_SCRATCH}"
        )
    for name in ("quick.json", "quarantine_P.json"):
        boundary.safe_path(root.parent, name)
    return root


def _copy_root(src: Path, dest: Path) -> str:
    """Copy admitted files verbatim and compute the exporter's genome hash."""
    paths, _ = boundary.inventory(src)
    tree = {}
    for relative in paths:
        boundary.check_stop()
        source, target = src / relative, boundary.safe_path(dest, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        shutil.copymode(source, target)
        kind = boundary.file_kind(relative)
        if kind == "file":
            data = target.read_bytes()
            value = {
                "$file": relative,
                "sha1": hashlib.sha1(data).hexdigest(),
                "mode": "755" if target.stat().st_mode & 0o111 else "644",
                "bytes": len(data),
            }
        elif kind == "ops":
            value = [
                {k: op[k] for k in boundary.OP_DEFINITION_FIELDS}
                for op in read_jsonl(target)
            ]
        else:
            value = read_json(target)
        parent = tree
        for part in Path(relative).parts[:-1]:
            parent = parent.setdefault(part, {})
        parent[Path(relative).name] = value
    defs, tree = deduplicate(tree)
    return genome_sha(defs, tree)


def prepare(
    src: str | Path,
    dest: str | Path,
    *,
    state: str | Path | None = None,
    L: int,  # noqa: N803 - Public budget name specified by the quick interface.
    epochs: int,
    clear_p: bool = True,
) -> dict:
    """Build a fresh replica, lock outer budgets and quarantine the P pool."""
    boundary.check_stop()
    if L <= 0 or epochs < 0:
        raise ValueError("L must be positive and epochs must be nonnegative")
    source, root = Path(src).resolve(), _destination(dest)
    if root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError("quick source and destination must not overlap")
    if source.is_dir() and state is not None:
        raise ValueError("--state requires a tree.json source")
    if source.is_dir():
        boundary.empty_directory(root)
        sha = _copy_root(source, root)
    else:
        sha = read_json(source)["genome_sha"]
        import_tree(source, root, state)
    write_jsonl(root / "ledger.jsonl", [])
    frozen = read_json(root / "frozen.json")
    original_budgets = dict(frozen["budgets"])
    frozen["budgets"].update(L=L, epochs=epochs)
    boundary.check_stop()
    write_json(root / "frozen.json", frozen)
    taskset_path = root / "truth/train/taskset.json"
    taskset = read_json(taskset_path)
    if clear_p:
        write_json(root.parent / "quarantine_P.json", taskset["P"])
        taskset["P"] = []
        write_json(taskset_path, taskset)
    errors = check_root(root)
    metadata = {
        "schema": "think2-quick/1",
        "genome_sha": sha,
        "src": str(source),
        "state": source.is_dir() or state is not None,
        "cfg": {
            "L": L,
            "epochs": epochs,
            "clear_p": clear_p,
            "genome_budgets": original_budgets,
        },
        "check_root_errors": len(errors),
        "check_root_details": errors,
        "base_ops": [op["id"] for op in read_jsonl(root / "ops.jsonl")],
        "dest": str(root),
    }
    boundary.check_stop()
    write_json(root / PREPARED, metadata)
    return metadata


def _stop(root: Path) -> None:
    try:
        boundary.check_stop()
    except RuntimeError:
        # Only the validated replica's RUN switch may be removed.
        (root / "RUN").unlink(missing_ok=True)
        raise


def _summarize(root: Path) -> dict:
    path = guards.REPO / "scripts/think1_meter.py"
    spec = importlib.util.spec_from_file_location("treegen_think1_meter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.summarize(root)


def _per_task(root: Path, epochs: int) -> dict:
    ids = read_json(root / "truth/train/taskset.json")["L16"]
    result = {tid: {"solved": [], "auc": 0, "nodes_to_first": []} for tid in ids}
    for n in range(1, epochs + 1):
        boundary.check_stop()
        path = root / "epochs" / str(n) / "solutions.jsonl"
        if not path.is_file():
            raise ValueError(f"missing epoch solutions: {path}")
        solutions = [row for row in read_jsonl(path) if row["set"] == "L16"]
        if len(solutions) != len(ids) or {s["task_id"] for s in solutions} != set(ids):
            raise ValueError(f"expected exactly one solution row per L16 task: {path}")
        for solution in solutions:
            item = result[solution["task_id"]]
            solved = int(bool(solution["test_ok"]))
            item["solved"].append(solved)
            item["auc"] += solved
            item["nodes_to_first"].append(solution["nodes_to_first"])
    return result


def run(dest: str | Path, *, epochs: int, threads: int = 4) -> dict:
    """Run epochs 0..E and publish the quick summary beside the replica."""
    root = _destination(dest)
    _stop(root)
    if not 1 <= threads <= 4:
        raise ValueError("quick threads must be between 1 and 4")
    metadata = read_json(root / PREPARED)
    if metadata is None or metadata.get("dest") != str(root):
        raise ValueError("run requires a replica created by quick.prepare")
    if epochs != metadata["cfg"]["epochs"]:
        raise ValueError("epochs must match the prepared quick budget")
    if metadata["check_root_errors"]:
        raise ValueError(f"replica check_root failed: {metadata['check_root_details']}")

    def after_epoch(message: str) -> None:
        _stop(root)
        print(message)

    started = time.perf_counter()
    epoch.run_tree(
        root,
        "hammer",
        epochs=epochs,
        backend="native",
        threads=threads,
        holdout=True,
        log=after_epoch,
    )
    wall_s = time.perf_counter() - started
    _stop(root)
    summary = _summarize(root)
    if len(summary["per_epoch"]) != epochs + 1:
        raise ValueError("quick did not complete all requested epochs")
    per_task = _per_task(root, epochs)
    assert sum(item["auc"] for item in per_task.values()) == summary["auc_L"]
    base = set(metadata["base_ops"])
    leak = guards.leak(root, base_ops=base)
    result = {
        **{k: v for k, v in metadata.items() if k not in ("base_ops", "dest")},
        "cfg": {**metadata["cfg"], "threads": threads},
        "wall_s": wall_s,
        **{
            key: summary[key]
            for key in (
                "auc_L",
                "auc_speed_L",
                "cost",
                "eff",
                "logcost_L_final",
                "per_epoch",
            )
        },
        "solved_L_final": summary["per_epoch"][-1]["solved_L"],
        "per_task": per_task,
        "new_ops": [
            op["id"] for op in read_jsonl(root / "ops.jsonl") if op["id"] not in base
        ],
        "guards": {"leak_new": leak["leak_new"], "leak_config": leak["config"]},
    }
    _stop(root)
    write_json(root.parent / "quick.json", result)
    return result
