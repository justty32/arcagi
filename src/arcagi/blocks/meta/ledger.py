"""Meta ledger ``aos/meta/ledger.jsonl``: one row per generator / meta run.

Record only (no dividends). ``$ARCAGI_META`` overrides the directory (tests).
"""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from .. import REPO_ROOT

FIELDS = (
    "run_id",
    "time",
    "layer",
    "target_gen",
    "setting",
    "seed",
    "blocks_root_hash",
    "base_commit",
    "cost_wall_s",
    "cost_cpu_s",
    "n_tasks",
    "n_candidates",
    "score_main",
    "score_div",
    "baseline_ref",
    "delta",
    "sigma",
    "accepted",
    "note",
)


def ledger_path() -> Path:
    env = os.environ.get("ARCAGI_META")
    return (Path(env) if env else REPO_ROOT / "aos" / "meta") / "ledger.jsonl"


def blocks_root_hash(root: Path) -> str:
    """sha1 over every ``<root>/*/_rule.json`` and block status (12 hex)."""
    h = hashlib.sha1()
    for folder in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        meta, rule = folder / "_metainfo.json", folder / "_rule.json"
        h.update(folder.name.encode())
        if rule.is_file():
            h.update(rule.read_bytes())
        if meta.is_file():
            h.update(str(json.loads(meta.read_text()).get("status")).encode())
    return h.hexdigest()[:12]


def base_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def append(row: dict) -> dict:
    """Write one row (missing fields null; ``time`` / ``base_commit`` filled)."""
    full = {k: row.get(k) for k in FIELDS}
    full["time"] = full["time"] or time.strftime("%Y-%m-%dT%H:%M:%S")
    full["base_commit"] = full["base_commit"] or base_commit()
    extra = {k: v for k, v in row.items() if k not in FIELDS}
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(full | extra, ensure_ascii=False) + "\n")
    return full | extra


class Timer:
    """Wall and CPU seconds of a ``with`` block."""

    def __enter__(self) -> "Timer":
        self.w, self.c = time.perf_counter(), time.process_time()
        return self

    def __exit__(self, *exc: object) -> None:
        self.wall = round(time.perf_counter() - self.w, 2)
        self.cpu = round(time.process_time() - self.c, 2)
