#!/usr/bin/env python3
"""Build the think-1 L0 scorecard from completed hammer epochs."""

import argparse
import json
import os
from pathlib import Path

RULES = {
    "keep_hit_rate": 0.3,
    "retire_idle": 5,
    "stale_age": 6,
    "param_kinds": ("gate", "route", "sieve"),
    "window_epochs": 10,
    "first_scored_epoch": 1,
    "hit_rate_digits": 4,
    "rules_version": "a1",
}
OUTPUT_DIR = Path("/home/lorkhan/code/playground-arc1/ws/hammer/think1/audit")


def check_stop() -> None:
    if (Path.home() / "arcagi-STOP").exists():
        raise SystemExit("STOP: ~/arcagi-STOP exists")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def completed_epochs(root: Path) -> list[int]:
    return sorted(
        int(path.name)
        for path in (root / "epochs").iterdir()
        if path.is_dir() and path.name.isascii() and path.name.isdecimal()
        and (path / "status.json").exists()
    )


def block_refs(program: object) -> set[str]:
    """Collect explicit blk references, counting each name once per task."""
    refs = set()
    if isinstance(program, list):
        if len(program) >= 2 and program[0] == "blk" and isinstance(program[1], str):
            refs.add(program[1])
        for child in program:
            refs.update(block_refs(child))
    elif isinstance(program, dict):
        for child in program.values():
            refs.update(block_refs(child))
    return refs


def contributions(epoch_dir: Path) -> dict[str, dict[str, int]]:
    counts = {"L16": {}, "P": {}}
    with (epoch_dir / "solutions.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["set"] not in counts or not row["train_ok"]:
                continue
            per_set = counts[row["set"]]
            for name in block_refs(row["program"]):
                per_set[name] = per_set.get(name, 0) + 1
    return counts


def verdict(row: dict) -> str:
    uses = None if row["uses_L"] is None else row["uses_L"] + row["uses_P"]
    ev_zero = (row["shadow_epochs"] == 0 and row["new_solves_n"] == 0
               and row["witness_hits"] == 0)
    if row["status"] == "incubating":
        return "incubating"
    elif row["kind"] in RULES["param_kinds"] and ev_zero:
        return "unmeasured"
    elif row["status"] == "dormant":
        stale = row["age"] >= RULES["stale_age"] and row["new_solves_n"] == 0
        return "dormant-stale" if stale else "dormant-active"
    elif row["status"] == "live":
        good = (row["new_solves_n"] >= 1 if uses is None else
                uses >= 1 or (row["hit_rate_10"] or 0) >= RULES["keep_hit_rate"])
        idle = row["idle_epochs"] if row["idle_epochs"] is not None else row["age"]
        return "keep" if good else (
            "retire-candidate" if idle >= RULES["retire_idle"] else "watch"
        )
    else:
        return "unknown-status"


def scorecard(root: Path, epoch: int, epochs: list[int]) -> list[dict]:
    scored = [e for e in epochs if RULES["first_scored_epoch"] <= e <= epoch]
    window = scored[-RULES["window_epochs"]:]
    contrib = {}
    observed = {}
    for e in sorted(set(scored) | {epoch}):
        check_stop()
        epoch_dir = root / "epochs" / str(e)
        contrib[e] = contributions(epoch_dir)
        if e in window:
            observed[e] = {
                block["name"]
                for filename in ("blocks.json", "shadow_blocks.json")
                for block in read_json(epoch_dir / filename)
            }

    rows = []
    with (root / "ops.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            op = json.loads(line)
            born = op.get("born", {}).get("epoch", 0)
            evidence = op["evidence"]
            uses_l = uses_p = hit_rate = idle = None
            if op["kind"] == "comb":
                name = op["payload"]["name"]
                uses_l = contrib[epoch]["L16"].get(name, 0)
                uses_p = contrib[epoch]["P"].get(name, 0)
                hits = {
                    e for e in scored
                    if contrib[e]["L16"].get(name, 0) + contrib[e]["P"].get(name, 0) >= 1
                }
                obs = {e for e in window if name in observed[e]}
                if obs:
                    hit_rate = round(len(hits & obs) / len(obs), RULES["hit_rate_digits"])
                idle = epoch - (max(hits) if hits else born)
                note = "shadow-only epochs cannot contribute: solutions.jsonl is main-run only"
            else:
                note = f"no per-block trace for kind={op['kind']}; uses/hit/idle null"
            row = {
                "id": op["id"], "kind": op["kind"], "status": op["status"],
                "by": op["by"], "mdl_bits": op["mdl_bits"],
                "born_epoch": born, "age": epoch - born,
                "shadow_epochs": evidence["shadow_epochs"],
                "witness_hits": evidence["witness_hits"],
                "new_solves_n": len(evidence["new_solves"]),
                "uses_L": uses_l, "uses_P": uses_p,
                "hit_rate_10": hit_rate, "idle_epochs": idle,
            }
            row["verdict"] = verdict(row)
            row["rules_version"] = RULES["rules_version"]
            row["note"] = note
            rows.append(row)
    return rows


def write_scorecard(out: Path, rows: list[dict]) -> None:
    """Only publish within the authorized directory, using atomic replacement."""
    check_stop()
    tmp = out.with_name(out.name + ".tmp")
    if out.parent.resolve() != OUTPUT_DIR or tmp.is_symlink() or out.is_symlink():
        raise ValueError(f"output must stay in {OUTPUT_DIR} without file symlinks")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    check_stop()
    os.replace(tmp, out)


def main() -> None:
    check_stop()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree_root", type=Path)
    parser.add_argument("--epoch", type=int)
    args = parser.parse_args()
    try:
        root = args.tree_root.resolve()
        epochs = completed_epochs(root)
        if not epochs:
            parser.error("tree has no completed epochs")
        epoch = epochs[-1] if args.epoch is None else args.epoch
        if epoch not in epochs:
            parser.error(f"epoch {epoch} is not completed")
        rows = scorecard(root, epoch, epochs)
        out = root / "think1" / "audit" / f"epoch-{epoch}.jsonl"
        write_scorecard(out, rows)
        verdicts = {}
        for row in rows:
            label = row["verdict"]
            verdicts[label] = verdicts.get(label, 0) + 1
        print(json.dumps({"epoch": epoch, "rows": len(rows),
                          "verdicts": verdicts, "out": str(out)}))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
