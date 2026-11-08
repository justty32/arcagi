"""Build the r08 task set -> data/r08/taskset.json.

Deterministic: same inputs give a byte-identical file. Rule (notes/rounds/r08/
03-設計.md D-r8-1): L16 and H8 copied unchanged from data/r07/taskset.json;
H24 (D-r8-9) = the first 24 of the other training tasks ordered by
sha1(task_id + "r08H24"), measured only (never learned, never inspected);
the practice pool P (D-r8-14) = 32 themed tasks: themes are S4 subcategories
(docs/taxonomy/labels.csv), first those seen >= 2 times in L16, then the other
L16 subcategories by training count descending (ties by name); <= 16 tasks per
theme, ordered by sha1(task_id + "r08P"), excluding L16/H8/H24, until 32.
R32 (D-r8-15 control) = the first 32 of the same remaining tasks ordered by
sha1(task_id + "r08R32"), no themes. P is searched and compressed, never scored.
pool_foot32 (D-r8-18) = foothold themes: subcategories ordered by how many of
their tasks were train_ok in data/r08/foot_pass0.json (empty library, DEFAULT
splits, 100k; train only) descending, ties by name; every remaining task of a
theme (<= 16, ordered by sha1(task_id + "r08F")) until 32.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE = (
    "learn/holdout = data/r07/taskset.json unchanged; holdout24 = first 24 of "
    "the other training tasks by sha1(task_id+'r08H24') (D-r8-9); practice = "
    "32 tasks by S4 subcategory theme: subcategories seen >=2 times in L16 "
    "first, then the other L16 subcategories by training count desc (ties by "
    "name); <=16 per theme ordered by sha1(task_id+'r08P'); excluding "
    "L16/H8/H24 (D-r8-14); rand32 = first 32 of the same remaining tasks by "
    "sha1(task_id+'r08R32') (D-r8-15)"
)
N_H24 = 24
N_P = 32
PER_THEME = 16


def _rank(ids: list[str], salt: str) -> list[str]:
    return sorted(ids, key=lambda t: hashlib.sha1((t + salt).encode()).hexdigest())


FOOT = ROOT / "data/r08/foot_pass0.json"
FOOT_RULE = (
    "subcategories by train_ok count in data/r08/foot_pass0.json (empty lib, "
    "DEFAULT splits, 100k, train only) desc, ties by name; all remaining tasks "
    "of a theme (<=16, by sha1(task_id+'r08F')) until 32 (D-r8-18)"
)


def _foot(pool_rest: list[str], sub: dict[str, str], entry) -> dict:
    if not FOOT.exists():
        return {}
    probe = json.loads(FOOT.read_text())["tasks"]
    hits: dict[str, int] = {}
    for r in probe:
        if r["train_ok"] and r["task_id"] in sub:
            hits[sub[r["task_id"]]] = hits.get(sub[r["task_id"]], 0) + 1
    out: list[dict] = []
    for sc in sorted(hits, key=lambda c: (-hits[c], c)):
        if len(out) >= N_P:
            break
        members = _rank([t for t in pool_rest if sub.get(t) == sc], "r08F")
        for t in members[:min(PER_THEME, N_P - len(out))]:
            out.append({**entry(t), "theme": sc, "theme_hits": hits[sc]})
    return {"pool_foot32": out, "pool_foot32_rule": FOOT_RULE,
            "foot_pass0_sha1": hashlib.sha1(FOOT.read_bytes()).hexdigest()}


def build() -> dict:
    tdir = ROOT / "data/ARC-AGI/data/training"
    r07_raw = (ROOT / "data/r07/taskset.json").read_bytes()
    r07 = json.loads(r07_raw)
    used = {e["task_id"] for e in r07["learn"] + r07["holdout"]}
    rest = [p.stem for p in sorted(tdir.glob("*.json")) if p.stem not in used]
    h24 = set(_rank(rest, "r08H24")[:N_H24])

    def entry(tid: str) -> dict:
        raw = (tdir / f"{tid}.json").read_bytes()
        return {"task_id": tid, "sha1": hashlib.sha1(raw).hexdigest()}

    sub: dict[str, str] = {}
    for line in (ROOT / "docs/taxonomy/labels.csv").read_text().splitlines()[1:]:
        tid, _, sc = line.split(",", 2)
        sub[tid] = sc
    l16 = [e["task_id"] for e in r07["learn"]]
    seen: dict[str, int] = {}
    for t in l16:
        seen[sub[t]] = seen.get(sub[t], 0) + 1
    count: dict[str, int] = {}
    for t, sc in sub.items():
        count[sc] = count.get(sc, 0) + 1
    themes = sorted((sc for sc in seen if seen[sc] >= 2),
                    key=lambda sc: (-count[sc], sc))
    themes += sorted((sc for sc in seen if seen[sc] < 2),
                     key=lambda sc: (-count[sc], sc))
    pool_rest = [t for t in rest if t not in h24]
    practice: list[dict] = []
    for sc in themes:
        if len(practice) >= N_P:
            break
        members = _rank([t for t in pool_rest if sub.get(t) == sc], "r08P")
        for t in members[:min(PER_THEME, N_P - len(practice))]:
            practice.append({**entry(t), "theme": sc})
    return {
        "schema": "r08-taskset/1",
        "rule": RULE,
        "r07_taskset_sha1": hashlib.sha1(r07_raw).hexdigest(),
        "learn": r07["learn"],
        "holdout": r07["holdout"],
        "holdout24": [entry(t) for t in sorted(h24)],
        "practice": practice,
        "rand32": [entry(t) for t in sorted(_rank(pool_rest, "r08R32")[:N_P])],
        **_foot(pool_rest, sub, entry),
    }


def main() -> None:
    out = ROOT / "data/r08/taskset.json"
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    out.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(out, hashlib.sha1(out.read_bytes()).hexdigest(),
          len(data["learn"]), len(data["holdout"]), len(data["holdout24"]),
          len(data["practice"]))


if __name__ == "__main__":
    main()
