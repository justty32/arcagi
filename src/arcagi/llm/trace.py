"""Distillation traces: one JSONL line per LLM rule with its verification.

Line schema ``arcagi-llm-trace/1``: ``task``, ``split``, ``model``, ``rank``
(order in the response), ``rule``, ``valid``, ``train_pass``, ``train_all``,
``test_exact`` (None for pred / formula), ``error``, ``tokens``, ``seconds``,
``candidates`` (folders written), ``ts``.
"""

import json
import time
from pathlib import Path

from . import LLM_ROOT

SCHEMA = "arcagi-llm-trace/1"


def path_for(split: str, run: str) -> Path:
    return LLM_ROOT / "traces" / f"{run}-{split}.jsonl"


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {"schema": SCHEMA, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")} | row
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, separators=(",", ":")) + "\n")


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def summarize(rows: list[dict]) -> list[dict]:
    """Per task: best train pass, top-1 test exact, tokens, seconds."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["task"], []).append(r)
    out = []
    for task, rs in sorted(by.items()):
        rs.sort(key=lambda r: r["rank"])
        passing = [r for r in rs if r.get("train_all")]
        best = max((r.get("train_pass") or 0.0) for r in rs)
        out.append(
            {
                "task": task,
                "split": rs[0]["split"],
                "rules": len(rs),
                "best_train_pass": round(best, 3),
                "train_all": bool(passing),
                "test_exact": bool(passing and passing[0].get("test_exact")),
                "tokens": rs[0].get("tokens"),
                "seconds": rs[0].get("seconds"),
            }
        )
    return out
