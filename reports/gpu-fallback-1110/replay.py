"""Replay stored gated traces with and without cached GPU fallback, on CPU.

Usage: uv run --no-sync python reports/gpu-fallback-1110/replay.py \
    --split training --workers 4 --out /tmp/gpu-fallback-training.jsonl
Add --limit 5 for a smoke run. Full runs should use an arcagi-n4f-* systemd
scope with MemoryMax=16G and nice -n 19, as required by the task brief.
"""

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from itertools import islice, repeat
from multiprocessing import get_context
from pathlib import Path

from arcagi.solvers import gated
from arcagi.tasks import load_task

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/ARC-AGI/data"
NATIVE_CUDA = ROOT / "reports/native-cuda-1109"
SOURCES = tuple(
    NATIVE_CUDA / name
    for name in (
        "overnight/phase-A.jsonl",
        "filler/train-open-d6.jsonl",
        "filler/eval-open-d6.jsonl",
        "overnight/phase-B.jsonl",
    )
)
TRACES = {
    "training": ROOT / "artifacts/gated-r07/training-traces.jsonl",
    "evaluation": ROOT / "artifacts/gated-r08/evaluation-traces.jsonl",
}
EXPECTED = {"training": 147, "evaluation": 56}
GPU_PROGRAMS: dict[str, list[str]] = {}


def _check_stop() -> None:
    if (Path.home() / "arcagi-STOP").exists():
        raise SystemExit("~/arcagi-STOP exists; stopping replay")


def _init_worker() -> None:
    global GPU_PROGRAMS
    _check_stop()
    GPU_PROGRAMS = gated.load_gpu_programs(SOURCES)


def _replay(rec: dict, split: str) -> dict:
    _check_stop()
    tid = rec["task_id"]
    full = load_task(DATA / split / f"{tid}.json")
    if any(e.output is None for e in full.test):
        raise ValueError(f"{tid}: replay requires test outputs")
    task = full.to_solver_task()
    off, _ = gated.gate(task, rec["trace"])
    on = gated.gpu_fallback(task, off, GPU_PROGRAMS.get(tid, []))

    def correct(predictions) -> list[bool]:
        return [
            tuple(tuple(row) for row in predicted) == example.output
            for predicted, example in zip(predictions, full.test, strict=True)
        ]

    return {
        "task": tid,
        "tests_correct": rec["tests_correct"],
        "off_predictions": off.predictions,
        "off_tests_correct": correct(off.predictions),
        "off_abstained": off.abstained,
        "on_predictions": on.predictions,
        "on_tests_correct": correct(on.predictions),
        "fallback_used": on is not off,
    }


def _summarize(rows: list[dict], split: str, limited: bool) -> None:
    off_correct = sum(all(r["off_tests_correct"]) for r in rows)
    on_correct = sum(all(r["on_tests_correct"]) for r in rows)
    stored_correct = sum(all(r["tests_correct"]) for r in rows)
    differences = [
        {"task": r["task"], "stored": r["tests_correct"], "off": r["off_tests_correct"]}
        for r in rows
        if r["tests_correct"] != r["off_tests_correct"]
    ]
    new_correct = [
        r["task"]
        for r in rows
        if not all(r["off_tests_correct"]) and all(r["on_tests_correct"])
    ]
    new_false = [
        r["task"]
        for r in rows
        if not all(r["off_tests_correct"])
        and r["fallback_used"]
        and not all(r["on_tests_correct"])
    ]
    conflicts = [
        r["task"]
        for r in rows
        if all(r["off_tests_correct"]) and not all(r["on_tests_correct"])
    ]
    print(f"split={split} tasks={len(rows)} limited={limited}")
    print(
        f"off tasks_correct={off_correct} (stored={stored_correct}; "
        f"full-split expected={EXPECTED[split]})"
    )
    if not limited and off_correct != EXPECTED[split]:
        print(f"BASELINE MISMATCH: expected {EXPECTED[split]}, got {off_correct}")
    print(f"off/stored differences={len(differences)} {json.dumps(differences)}")
    print(f"on tasks_correct={on_correct}")
    print(f"new correct={len(new_correct)} {json.dumps(new_correct)}")
    print(f"new false={len(new_false)} {json.dumps(new_false)}")
    print(f"conflicts={len(conflicts)} {json.dumps(conflicts)}")


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _workers(value: str) -> int:
    number = _positive_int(value)
    if number > 4:
        raise argparse.ArgumentTypeError("workers must be <= 4")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=tuple(TRACES), default="training")
    parser.add_argument("--workers", type=_workers, default=4)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=_positive_int)
    args = parser.parse_args(argv)
    _check_stop()
    with TRACES[args.split].open() as source:
        records = [json.loads(line) for line in islice(source, args.limit)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with (
        args.out.open("w") as output,
        ProcessPoolExecutor(
            max_workers=args.workers,
            mp_context=get_context("spawn"),
            initializer=_init_worker,
        ) as pool,
    ):
        for row in pool.map(_replay, records, repeat(args.split)):
            _check_stop()
            output.write(json.dumps(row) + "\n")
            output.flush()
            rows.append(row)
    _summarize(rows, args.split, limited=args.limit is not None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
