"""N4g: run ../replay.py with an explicit GPU source list (env N4G_SOURCES).

N4G_SOURCES is an os.pathsep-separated list of gpusearch-compatible JSONL files
(records with `task` and `best.program` and/or `samples`; GP records with
`best` are read the same way, `partial` is ignored by gated.load_gpu_programs).
Usage: N4G_SOURCES=a.jsonl:b.jsonl uv run --no-sync python \
    reports/gpu-fallback-1110/n4g/replay_sources.py --split training --workers 4 --out OUT
Nothing in gated.py or replay.py is changed; only replay.SOURCES is overridden
in the parent and in every spawned worker.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import replay  # noqa: E402

replay.SOURCES = tuple(p for p in os.environ["N4G_SOURCES"].split(os.pathsep) if p)


def _init_worker() -> None:
    replay._check_stop()
    replay.GPU_PROGRAMS = replay.gated.load_gpu_programs(replay.SOURCES)


replay._init_worker = _init_worker

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import replay_sources  # noqa: F401,E402  (registers module for workers)

    replay._init_worker = replay_sources._init_worker
    print(f"sources={len(replay.SOURCES)} {[Path(p).name for p in replay.SOURCES]}")
    raise SystemExit(replay.main())
