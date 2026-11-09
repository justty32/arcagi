"""Re-verify gpusearch programs with the Python reference DSL.

Usage: python native/tools/gpu_verify.py RESULTS.jsonl [...] [--data DIR ...]

For every record with a ``best`` program, runs it with ``arcagi.dsl.program``
(under the task background context, as the hybrid entry does) on all train
pairs and the test pairs, and prints one JSON summary line.
"""

import json
import sys
from pathlib import Path

from arcagi.dsl import background as bgc
from arcagi.dsl import program
from arcagi.tasks import load_task

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = [
    ROOT / "data/ARC-AGI/data/training",
    ROOT / "data/ARC-AGI/data/evaluation",
]


def find(task_id: str, dirs: list[Path]) -> Path:
    for d in dirs:
        path = d / f"{task_id}.json"
        if path.exists():
            return path
    raise FileNotFoundError(task_id)


def runs(task: object, steps: object) -> tuple[bool, bool]:
    """(train all correct, test all correct) for one JSON program."""
    prog = program.from_json(json.dumps(steps))
    grids = [e.input for e in task.train] + [e.output for e in task.train]  # type: ignore[attr-defined]
    train_ok, test_ok = True, True
    with bgc.task_context(bgc.task_background(grids)):
        for example in task.train:  # type: ignore[attr-defined]
            try:
                train_ok &= program.run(prog, example.input) == example.output
            except ValueError:
                train_ok = False
        for example in task.test:  # type: ignore[attr-defined]
            try:
                test_ok &= program.run(prog, example.input) == example.output
            except ValueError:
                test_ok = False
    return train_ok, test_ok


def check(record: dict[str, object], dirs: list[Path]) -> dict[str, object]:
    task = load_task(find(str(record["task"]), dirs))
    best = record["best"]
    assert isinstance(best, dict)
    train_ok, test_ok = runs(task, best["program"])
    samples = record.get("samples") or []
    sample_ok = sum(runs(task, steps)[0] for steps in samples)  # type: ignore[union-attr]
    return {
        "task": record["task"],
        "train_ok": train_ok,
        "test_ok": test_ok,
        "cpp_test_ok": best.get("test_ok"),
        "program": best["program"],
        "samples": len(samples),
        "samples_train_ok": sample_ok,
    }  # type: ignore[arg-type]


def main(argv: list[str]) -> int:
    files, dirs = [], []
    it = iter(argv)
    for arg in it:
        if arg == "--data":
            dirs.append(Path(next(it)))
        else:
            files.append(Path(arg))
    dirs = dirs or DEFAULT_DATA
    rows = []
    for path in files:
        for line in path.read_text().splitlines():
            record = json.loads(line)
            if "best" in record:
                rows.append(check(record, dirs))
    for row in rows:
        print(json.dumps(row))
    summary = {
        "checked": len(rows),
        "train_ok": sum(bool(r["train_ok"]) for r in rows),
        "test_ok": sum(bool(r["test_ok"]) for r in rows),
        "test_agrees_with_cpp": sum(r["test_ok"] == r["cpp_test_ok"] for r in rows),
        "samples": sum(int(r["samples"]) for r in rows),  # type: ignore[call-overload]
        "samples_train_ok": sum(int(r["samples_train_ok"]) for r in rows),  # type: ignore[call-overload]
    }
    print(json.dumps({"summary": summary}))
    ok = (
        summary["train_ok"] == len(rows)
        and summary["samples_train_ok"] == summary["samples"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
