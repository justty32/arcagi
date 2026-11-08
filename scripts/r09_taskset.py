"""Build the r09 task set -> data/r09/taskset.json.

Deterministic: same inputs give a byte-identical file. Rule (written BEFORE
generating; notes/rounds/r09/02-規劃-fable.md section 5):
  * learn (L16), holdout (H8), holdout24 (H24) copied unchanged from
    data/r08/taskset.json (task ids and sha1 only are touched; H8/H24 task
    contents are never read).
  * practice = P48 = pool_foot32 of data/r08/taskset.json (32 tasks) UNION 16
    more tasks "near" the L16 tasks still unsolved at the last pass of
    reports/curve-r08/pool/solutions.jsonl (rows of the max pass with set=="L"
    and test_ok false; 12 tasks).
  * the 16 extra: candidates = all training tasks minus L16, H8, H24 and
    foot32. For each candidate, d = min over the unsolved-L tasks of
    arcagi.hammer.proj.distance (three-projection residual fingerprint of the
    train pairs only; formula in that docstring). Take the 16 smallest d, ties
    broken by task_id ascending.
  * AB fold: sort P48 ids by sha1(task_id + "r09AB"); first half = fold A, the
    rest = fold B.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from arcagi.hammer import proj  # noqa: E402

N_EXTRA = 16
SOLS = ROOT / "reports/curve-r08/pool/solutions.jsonl"


def _task(tid: str) -> dict:
    return json.loads((ROOT / f"data/ARC-AGI/data/training/{tid}.json").read_text())


def build() -> dict:
    r08 = json.loads((ROOT / "data/r08/taskset.json").read_text())
    sols = [json.loads(x) for x in SOLS.read_text().splitlines()]
    last = max(s["pass"] for s in sols)
    unsolved = sorted(s["task_id"] for s in sols
                      if s["pass"] == last and s["set"] == "L" and not s["test_ok"])
    ids = lambda k: [e["task_id"] for e in r08[k]]  # noqa: E731
    excl = set(ids("learn")) | set(ids("holdout")) | set(ids("holdout24")) \
        | set(ids("pool_foot32"))
    cands = sorted(p.stem for p in (ROOT / "data/ARC-AGI/data/training").glob("*.json")
                   if p.stem not in excl)
    ref = [proj.fingerprint(_task(t)) for t in unsolved]
    scored = []
    for t in cands:
        fp = proj.fingerprint(_task(t))
        scored.append((round(min(proj.distance(fp, r) for r in ref), 9), t))
    scored.sort()
    extra = [{"task_id": t, "dist": d, "src": "near_unsolved_L16",
              "sha1": hashlib.sha1((ROOT / f"data/ARC-AGI/data/training/{t}.json")
                                   .read_bytes()).hexdigest()}
             for d, t in scored[:N_EXTRA]]
    foot = [{**e, "src": "foot32"} for e in r08["pool_foot32"]]
    practice = foot + extra
    order = sorted((e["task_id"] for e in practice),
                   key=lambda t: hashlib.sha1((t + "r09AB").encode()).hexdigest())
    half = len(order) // 2
    fold = {t: ("A" if i < half else "B") for i, t in enumerate(order)}
    for e in practice:
        e["fold"] = fold[e["task_id"]]
    return {
        "schema": "r09-taskset/1",
        "rule": "see scripts/r09_taskset.py docstring",
        "r08_taskset_sha1": hashlib.sha1(
            (ROOT / "data/r08/taskset.json").read_bytes()).hexdigest(),
        "unsolved_L16_r08": unsolved,
        "learn": r08["learn"], "holdout": r08["holdout"],
        "holdout24": r08["holdout24"],
        "practice": practice,
        "P48": practice,  # key name read by hammer.formats.taskset_ids
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/r09/taskset.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=1, sort_keys=True) + "\n")
    d = json.loads(out.read_text())
    print(out, hashlib.sha1(out.read_bytes()).hexdigest(), len(d["learn"]),
          len(d["holdout"]), len(d["holdout24"]), len(d["practice"]))


if __name__ == "__main__":
    main()
