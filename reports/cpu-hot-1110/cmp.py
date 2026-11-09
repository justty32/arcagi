#!/usr/bin/env python3
"""Compare seed batch rows, retaining eval_steps and near order."""
import argparse
import json
from pathlib import Path

REQUIRED = {"program", "train_ok", "test_ok", "nodes", "nodes_to_first", "near", "eval_steps"}


def exact(value):
    # Python equality conflates True/1 and 1/1.0; preserve JSON value types.
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def read_rows(path):
    rows = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("summary"):
            continue
        missing = REQUIRED - row.keys()
        if missing:
            raise ValueError(f"{path}: missing keys {sorted(missing)}")
        key = (row.get("config", ""), row["task_id"])
        if key in rows:
            raise ValueError(f"{path}: duplicate {key}")
        rows[key] = {k: v for k, v in row.items() if k != "seconds"}
    if not rows:
        raise ValueError(f"{path}: no task rows")
    return rows


def compare(reference, candidate):
    ref, got = read_rows(reference), read_rows(candidate)
    bad = []
    for key in sorted(ref.keys() | got.keys()):
        if key not in ref or key not in got:
            bad.append({"config": key[0], "task_id": key[1], "keys": ["missing_row"]})
        elif exact(ref[key]) != exact(got[key]):
            fields = sorted(k for k in ref[key].keys() | got[key].keys()
                            if k not in ref[key] or k not in got[key]
                            or exact(ref[key][k]) != exact(got[key][k]))
            bad.append({"config": key[0], "task_id": key[1], "keys": fields})
    return {"reference": str(reference), "candidate": str(candidate),
            "tasks": len(ref), "mismatches": len(bad), "details": bad}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    result = compare(args.reference, args.candidate)
    print(json.dumps(result, sort_keys=True))
    return bool(result["mismatches"])


if __name__ == "__main__":
    raise SystemExit(main())
