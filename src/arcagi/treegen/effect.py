"""Probe genome edits at hammer's configuration and epoch boundaries."""

import copy
import json
import tempfile
import time
from pathlib import Path

from arcagi.hammer import epoch, grow
from arcagi.hammer import formats as fm
from arcagi.hammer.route import pick_arm

from . import boundary, genome, refs
from .import_ import import_tree

# epoch.run_epoch only branches on rt_pool and rt_vsplit. The remaining
# arms all reset pool_mult to 1 and perform no route work.
NOOP_ARMS = frozenset(("rt_sleep", "rt_gatescan", None))
SCRATCH = Path(
    "/tmp/claude-1000/-home-lorkhan-repo-arcagi/"
    "b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4f"
)
FIXTURE_TASKS = ("67a3c6ac", "25ff71a9")
FIXTURE_BUDGET = 64


def _arm(arm: str | None) -> str:
    return "NOOP" if arm in NOOP_ARMS else arm


def effective_arms(ops: list[dict]) -> dict[str, str]:
    """Use pick_arm's priority, id tie-break and stop-to-saturate fallback."""
    return {state: _arm(pick_arm(ops, state)) for state in fm.STALL_STATES}


def _json(value: object) -> object:
    return json.loads(refs.canonical(value))


def _static(tree: dict, root: Path, threads: int, backend: str) -> dict:
    ops = tree["ops.jsonl"]
    cfg, gate = epoch._cfg(ops, threads, backend, root)
    return {
        "cfg": _json({"body": cfg.to_dict(), "gate": gate}),
        "arms": effective_arms(ops),
        # comb does not enter _cfg: _main_run loads it via lib_from_ops,
        # and the shadow run also includes incubating combs.
        "library": _json(
            {
                "live": grow.lib_from_ops(ops),
                "shadow": grow.lib_from_ops(ops, ("live", "incubating")),
            }
        ),
    }


def _fixture(
    doc: dict, directory: Path, files_dir: Path, threads: int, backend: str
) -> dict:
    boundary.check_stop()
    fm.write_json(directory / "tree.json", doc)
    root = import_tree(directory / "tree.json", directory / "root", files_dir=files_dir)
    frozen = fm.load_frozen(root)
    frozen["budgets"].update(
        L=FIXTURE_BUDGET,
        P0=FIXTURE_BUDGET,
        P_cap=FIXTURE_BUDGET,
        shadow_slow=FIXTURE_BUDGET,
        epochs=1,
    )
    fm.write_json(root / "frozen.json", frozen)
    fm.write_json(root / "truth/train/taskset.json", {"L16": FIXTURE_TASKS, "P": []})
    epoch.run_epoch(
        root,
        0,
        holdout=False,
        threads=threads,
        backend=backend,
        # The probe must never dispatch a foundry request.
        foundry_fn=lambda *args: None,
    )
    boundary.check_stop()
    state = fm.read_json(root / "live/state.json")
    status = fm.read_json(root / "epochs/0/status.json")
    solutions = fm.read_jsonl(root / "epochs/0/solutions.jsonl")
    return {
        "pool_mult": state["pool_mult"],
        "feed": {
            **{
                key: value
                for key, value in status.items()
                if "feed" in key or key in ("gate_in", "false_pos")
            },
            "uses": state["uses"],
        },
        "epoch_arm": _arm(status["arm"]),
        "solutions": [
            {key: value for key, value in row.items() if key != "seconds"}
            for row in solutions
        ],
    }


def probe(
    parent_doc: dict | str | Path,
    child_doc: dict | str | Path,
    *,
    files_dir: Path | None = None,
    scratch: Path | None = None,
    threads: int = 1,
    backend: str = "native",
) -> dict:
    """Compare actual settings, then two tiny epochs if cfg/arms are equal.

    This is a bounded behavioral witness, not proof of equivalence on all
    ARC tasks. Runtime history, env hashes, row counts and timings are not
    effects: those would make masked route edits look useful.
    """
    boundary.check_stop()
    if not 1 <= threads <= 4:
        raise ValueError("effect probe threads must be between 1 and 4")
    started = time.perf_counter()
    scratch = Path(scratch) if scratch is not None else SCRATCH
    parent, child = genome.load(parent_doc), genome.load(child_doc)
    # _cfg embeds tmp_dir. Compare both configurations against the SAME root.
    root = scratch / "cfg-root"
    before = _static(genome.expanded(parent), root, threads, backend)
    after = _static(genome.expanded(child), root, threads, backend)
    changed = [key for key in before if before[key] != after[key]]
    detail = {key: {"parent": before[key], "child": after[key]} for key in changed}
    ran_epoch = not any(key in changed for key in ("cfg", "arms"))
    if ran_epoch:
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="effect-", dir=scratch) as tmp:
            observations = []
            for label, source, doc in (
                ("parent", parent_doc, parent),
                ("child", child_doc, child),
            ):
                blobs = files_dir
                if blobs is None:
                    path = (
                        Path(source)
                        if isinstance(source, (str, Path))
                        else genome.PARENT
                    )
                    blobs = path.parent / "files"
                observations.append(
                    _fixture(doc, Path(tmp) / label, blobs, threads, backend)
                )
            before_epoch, after_epoch = observations
            for key in before_epoch:
                if before_epoch[key] != after_epoch[key]:
                    changed.append(key)
                    detail[key] = {
                        "parent": before_epoch[key],
                        "child": after_epoch[key],
                    }
    return {
        "changed": changed,
        "detail": detail,
        "fixture": {
            "ran_epoch": ran_epoch,
            "tasks": list(FIXTURE_TASKS),
            "budget": FIXTURE_BUDGET,
            "threads": threads,
            "backend": backend,
            "holdout": False,
        },
        "wall_s": time.perf_counter() - started,
    }


def meter_track(parent_doc: dict, child_doc: dict) -> str:
    """Use targeted stripping only for comb status flips or deletions vs g0."""
    parent, child = genome.expanded(parent_doc), genome.expanded(child_doc)
    before = parent.pop("ops.jsonl")
    after = child.pop("ops.jsonl")
    if refs.canonical(parent) != refs.canonical(child):
        return "all"
    originals = {op["id"]: op for op in before}
    children = {op["id"]: op for op in after}
    if [op["id"] for op in after] != [
        op["id"] for op in before if op["id"] in children
    ]:
        return "all"
    changed = False
    for oid, op in originals.items():
        other = children.get(oid)
        if op == other:
            continue
        changed = True
        if op["kind"] != "comb":
            return "all"
        if other is not None:
            flipped = copy.deepcopy(op)
            flipped["status"] = "dormant" if op["status"] == "live" else "live"
            if op["status"] not in ("live", "dormant") or flipped != other:
                return "all"
    return "targeted" if changed else "all"
