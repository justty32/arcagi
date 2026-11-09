#!/usr/bin/env python3
"""Run one seed batch inside the caller's systemd scope and record wall/load."""

import argparse
import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = Path(
    "/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8"
)


def main():
    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("budget", type=int, choices=(1000000, 10000000))
    parser.add_argument(
        "binary",
        choices=(
            "arcbatch",
            "arcbatch-hot-a",
            "arcbatch-hot",
            "arcbatch-hot-prof",
            "arcbatch-hot-c",
            "arcbatch-hot-d",
        ),
    )
    parser.add_argument("rep", type=int)
    parser.add_argument("outdir", type=Path)
    args = parser.parse_args()
    stop = Path.home() / "arcagi-STOP"
    if stop.exists():
        raise SystemExit("Stopped: ~/arcagi-STOP exists")
    outdir = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.budget}-{args.binary}-r{args.rep}"
    output = outdir / f"{stem}.jsonl"
    if output.exists():
        raise SystemExit(f"Refusing to overwrite {output}")
    data = Path(os.environ.get("ARC_HOT_DATA", str(DEFAULT_DATA)))
    command = [
        str(ROOT / "native/bin" / args.binary),
        "--mode",
        "seed",
        "--tasks",
        str(data / "train100.txt"),
        "--configs",
        str(data / f"cfg-{args.budget}.jsonl"),
        "--threads",
        "4",
        "--out",
        str(output),
    ]
    load = os.getloadavg()[0]
    start = time.perf_counter()
    with (outdir / f"{stem}.stderr").open("w") as err:
        proc = subprocess.Popen(
            command, cwd=ROOT, stderr=err, stdout=err, start_new_session=True
        )
        try:
            while proc.poll() is None:
                if stop.exists():
                    raise RuntimeError("Stopped: ~/arcagi-STOP exists")
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
            if proc.returncode:
                raise RuntimeError(
                    f"{args.binary} exited {proc.returncode}; see {err.name}"
                )
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
    seconds = time.perf_counter() - start
    row = f"{args.budget} {args.binary} {args.rep} {seconds:.6f} {load:.2f}"
    with (outdir / "wall.txt").open("a") as out:
        print(row, file=out)
    print(row, flush=True)


if __name__ == "__main__":
    main()
