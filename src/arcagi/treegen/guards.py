"""Audit forbidden task provenance and registered approximate metrics."""

import hashlib
import os
import re
from pathlib import Path

from arcagi.hammer.formats import read_json, read_jsonl, write_json

from . import boundary
from .refs import expand

REPO = Path(__file__).resolve().parents[3]
LIVE_ROOT = Path("/home/lorkhan/code/playground-arc1/ws/hammer")
REGISTRY = REPO / "reports/think2-1109/guards/thresholds.json"
METRICS = re.compile(
    r"pixel_acc|cell_acc|match_ratio|match_after|near_score|near_best|near_miss|"
    r"_gradients"
)
PURPOSES = frozenset(("rank", "diag", "route", "accept", "promote", "retire"))
FORBIDDEN = frozenset(("accept", "promote", "retire"))


def _contents(target: Path, state: Path | None) -> tuple[list[dict], dict, dict]:
    if target.is_dir():
        if state is not None:
            raise ValueError("--state requires a tree.json target")
        if not (target / "ops.jsonl").is_file():
            raise ValueError(f"missing ops.jsonl: {target}")
        return (
            read_jsonl(target / "ops.jsonl"),
            read_json(target / "truth/train/taskset.json"),
            read_json(target / "truth/cal/ids.json"),
        )
    document = read_json(target)
    if document["schema"] != "aos-tree/1":
        raise ValueError("unsupported tree schema")
    tree = expand(document["tree"], document["defs"])
    ops = tree["ops.jsonl"]
    sidecar = state if state is not None else target.with_name("state.json")
    if state is not None or sidecar.exists():
        saved = read_json(sidecar)
        if saved["schema"] != "aos-tree-state/1":
            raise ValueError("unsupported state schema")
        ops = [
            {
                **op,
                **{
                    k: v
                    for k, v in saved["ops"].get(op["id"], {}).items()
                    if k in boundary.OP_STATE_FIELDS
                },
            }
            for op in ops
        ]
    return ops, tree["truth"]["train"]["taskset.json"], tree["truth"]["cal"]["ids.json"]


def leak(
    target: str | Path,
    *,
    forbid_root: str | Path = LIVE_ROOT,
    base_ops: set[str] | str | Path | None = None,
    state: str | Path | None = None,
) -> dict:
    """Report P/H8/H24 task provenance, separating inherited and new ops."""
    boundary.check_stop()
    ops, train, cal = _contents(Path(target), Path(state) if state else None)
    forbidden_root = Path(forbid_root)
    other_train = read_json(forbidden_root / "truth/train/taskset.json")
    other_cal = read_json(forbidden_root / "truth/cal/ids.json")
    pools = {
        "P": set(train["P"]) | set(other_train["P"]),
        **{name: set(cal[name]) | set(other_cal[name]) for name in ("H8", "H24")},
    }
    base = (
        {op["id"] for op in read_jsonl(Path(base_ops))}
        if isinstance(base_ops, (str, Path))
        else set(base_ops or ())
    )
    violations = []
    for op in ops:
        boundary.check_stop()
        for field, tasks in (
            ("payload.src_tasks", op.get("payload", {}).get("src_tasks", [])),
            ("evidence.new_solves", op.get("evidence", {}).get("new_solves", [])),
        ):
            for pool, forbidden in pools.items():
                overlap = sorted(set(tasks) & forbidden)
                if overlap:
                    violations.append(
                        {
                            "op_id": op["id"],
                            "field": field,
                            "tasks": overlap,
                            "pool": pool,
                        }
                    )
    inherited = [row for row in violations if row["op_id"] in base]
    new = [row for row in violations if row["op_id"] not in base]
    config = "FAIL" if train["P"] else "PASS"
    return {
        "rule": "no_build_from_P",
        "config": config,
        "config_reason": (
            "epoch.py:252 gate_ids=L16∪P、:335 shadow lp 含 P" if train["P"] else "P=[]"
        ),
        "violations": violations,
        "tainted_ops": sorted({row["op_id"] for row in violations}),
        "inherited": inherited,
        "new": new,
        "leak_new": "FAIL" if new else "PASS",
        "status": "PASS" if config == "PASS" and not violations else "FAIL",
    }


def scan_thresholds(scan: list[Path] | None = None) -> list[dict]:
    """Find each matching source line once; line numbers do not affect keys."""
    hits = {}
    for directory in scan if scan is not None else [REPO / "src", REPO / "scripts"]:
        directory = Path(directory).resolve()
        if not directory.is_dir():
            raise ValueError(f"scan directory does not exist: {directory}")
        for path in sorted(directory.rglob("*.py")):
            boundary.check_stop()
            resolved = path.resolve()
            # External scans retain their path so adding another scan root cannot
            # change the identity of any existing registered line.
            relative = Path(os.path.relpath(resolved, REPO)).as_posix()
            for number, line in enumerate(path.read_text().splitlines(), 1):
                text = line.strip()
                metrics = sorted(set(METRICS.findall(text)))
                if not metrics:
                    continue
                key = hashlib.sha1(f"{relative}\n{text}".encode()).hexdigest()[:12]
                hits.setdefault(
                    key,
                    {
                        "key": key,
                        "file": relative,
                        "text": text,
                        "metric": "|".join(metrics),
                        "line": number,
                    },
                )
    return sorted(hits.values(), key=lambda row: (row["file"], row["line"]))


def thresholds(
    scan: list[Path] | None = None,
    registry: str | Path = REGISTRY,
    *,
    init: bool = False,
) -> dict:
    """Fail for unregistered or forbidden uses; initialization writes a draft."""
    boundary.check_stop()
    registry = Path(registry)
    hits = scan_thresholds(scan)
    if init:
        if registry.exists():
            raise ValueError(f"refusing to overwrite registry: {registry}")
        write_json(
            registry,
            {
                "schema": "think2-thresholds/1",
                "entries": [
                    {k: v for k, v in hit.items() if k != "line"}
                    | {"purpose": "", "why": ""}
                    for hit in hits
                ],
            },
        )
    document = read_json(registry, {"schema": "think2-thresholds/1", "entries": []})
    if document["schema"] != "think2-thresholds/1":
        raise ValueError("unsupported thresholds schema")
    entries = document["entries"]
    registered = {row["key"]: row for row in entries}
    if len(registered) != len(entries):
        raise ValueError("duplicate threshold registry key")
    hit_keys = {row["key"] for row in hits}
    missing = [row for row in hits if row["key"] not in registered]
    active = [row for row in entries if row["key"] in hit_keys]
    invalid = [row for row in active if row.get("purpose") not in PURPOSES]
    forbidden = [row for row in active if row.get("purpose") in FORBIDDEN]
    stale = [row for row in entries if row["key"] not in hit_keys]
    return {
        "rule": "no_approximate_thresholds",
        "registry": str(registry),
        "hits": hits,
        "unregistered": missing,
        "invalid": invalid,
        "forbidden": forbidden,
        "stale": stale,
        "status": "FAIL" if missing or invalid or forbidden else "PASS",
    }
