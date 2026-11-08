"""Build the r07 task set (L16 learn + H8 holdout) -> data/r07/taskset.json.

Deterministic: same inputs give a byte-identical file. Rule (notes/rounds/r07/
02-規劃-fable.md §2):
  * candidates: ARC-AGI-1 training tasks with an S4 label, an S5 synthetic file
    (data_synth/training/<id>.json) and every grid <= 15x15;
  * split by whether the r06 mixed entry solved it on training
    (artifacts/dsl-search-r06/training.json, tasks[].correct);
  * within each split, buckets = S4 category, each bucket ordered by
    sha1(task_id + "r07"); round-robin over sorted categories picks 12 per split;
    the first 8 go to L16, the next 4 to H8.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = "r07"
MAX_SIDE = 15
N_LEARN = 8  # per split
N_HOLD = 4  # per split
RULE = (
    "training tasks with S4 label, S5 synth file, all grids <=15x15; split by r06 "
    "training correct; per split round-robin over sorted S4 categories, each "
    "bucket ordered by sha1(task_id+'r07'); first 8 -> L16, next 4 -> H8 "
    "(the <=15x15 cap is a compute bias)"
)


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def _small(task: dict) -> bool:
    grids = [p[k] for part in ("train", "test") for p in task[part] for k in p]
    return all(
        len(gr) <= MAX_SIDE and all(len(r) <= MAX_SIDE for r in gr) for gr in grids
    )


def _pick(ids: list[str], labels: dict[str, str], n: int) -> list[str]:
    buckets: dict[str, list[str]] = {}
    for tid in ids:
        buckets.setdefault(labels[tid], []).append(tid)
    for b in buckets.values():
        b.sort(key=lambda t: _sha(t + SEED))
    out: list[str] = []
    depth = 0
    while len(out) < n and any(len(b) > depth for b in buckets.values()):
        for cat in sorted(buckets):
            if len(buckets[cat]) > depth and len(out) < n:
                out.append(buckets[cat][depth])
        depth += 1
    if len(out) < n:
        raise SystemExit(f"not enough candidates: {len(out)} < {n}")
    return out


def build() -> dict:
    tdir = ROOT / "data/ARC-AGI/data/training"
    labels: dict[str, str] = {}
    for line in (ROOT / "docs/taxonomy/labels.csv").read_text().splitlines()[1:]:
        tid, cat, _ = line.split(",", 2)
        labels[tid] = cat
    r06 = json.loads((ROOT / "artifacts/dsl-search-r06/training.json").read_text())
    solved = {t["task_id"]: bool(t["correct"]) for t in r06["tasks"]}
    cands = []
    for path in sorted(tdir.glob("*.json")):
        tid = path.stem
        if tid not in labels or tid not in solved:
            continue
        if not (ROOT / "data_synth/training" / f"{tid}.json").exists():
            continue
        if _small(json.loads(path.read_text())):
            cands.append(tid)
    learn: list[str] = []
    hold: list[str] = []
    for flag in (True, False):
        ids = [t for t in cands if solved[t] is flag]
        picked = _pick(ids, labels, N_LEARN + N_HOLD)
        learn += picked[:N_LEARN]
        hold += picked[N_LEARN:]

    def entry(tid: str) -> dict:
        raw = (tdir / f"{tid}.json").read_bytes()
        return {
            "task_id": tid,
            "category": labels[tid],
            "r06_solved": solved[tid],
            "sha1": hashlib.sha1(raw).hexdigest(),
        }

    return {
        "schema": "r07-taskset/1",
        "seed": SEED,
        "rule": RULE,
        "n_candidates": len(cands),
        "learn": [entry(t) for t in learn],
        "holdout": [entry(t) for t in hold],
    }


def main() -> None:
    out = ROOT / "data/r07/taskset.json"
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=1, sort_keys=True) + "\n")
    print(out, hashlib.sha1(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
