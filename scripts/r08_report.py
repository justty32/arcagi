"""Summarise r08 curves -> JSON tables for reports/curve-r08/README.md.

    uv run python scripts/r08_report.py reports/curve-r08/pool [...]

Per curve: solved_L/H/H24 and clean_P per pass, AUC_L, delta, logcost_L sum
(passes 1..N), budget_P, false_pos, curve sha; every block ever born with its
origin (P / L / P+L, P themes), how many L16 test-right solutions used it and
how many distinct tasks' test-right solutions (L16 or P) share it; per-theme
P counts (train-solved / gate-passed, last pass and best pass).
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from arcagi.grow import curve  # noqa: E402
from arcagi.grow import prog as pg  # noqa: E402

TASKSET = ROOT / "data" / "r08" / "taskset.json"


def summarise(d: Path) -> dict:
    ts = json.loads(TASKSET.read_text())
    sols = [json.loads(x) for x in (d / "solutions.jsonl").read_text().splitlines()]
    p_ids = {s["task_id"] for s in sols if s["set"] == "P"}
    theme = {e["task_id"]: "rand32" for e in ts["rand32"]}
    for key in ("pool_foot32", "practice"):  # themed pools win over rand32
        theme.update({e["task_id"]: e["theme"] for e in ts.get(key, [])})
    theme = {t: v for t, v in theme.items() if t in p_ids}
    learn = {e["task_id"] for e in ts["learn"]}
    rows = list(csv.DictReader((d / "curve.csv").read_text().splitlines()))
    col = lambda c: [r[c] for r in rows]  # noqa: E731
    born_path = d / "blocks_born.json"
    born = json.loads(born_path.read_text()) if born_path.exists() else []
    blocks = []
    for b in born:
        srcs = b["src_tasks"]
        in_p = [t for t in srcs if t in p_ids]
        in_l = [t for t in srcs if t in learn]
        near = [t for t in srcs if t.endswith("~near")]  # cold-start near misses
        origin = ("P+L" if in_p and in_l else "P" if in_p else "L" if in_l
                  else "L-near" if near else "other")
        l_uses, share = 0, set()
        for s in sols:
            if not s["test_ok"] or s["program"] is None:
                continue
            names = pg.ops(pg.from_json(s["program"]))
            if b["name"] in names:
                share.add(s["task_id"])
                if s["set"] == "L":
                    l_uses += 1
        blocks.append({"name": b["name"], "body": b["body"], "sig": b["sig"],
                       "saving": b["saving"], "born": b["born"], "origin": origin,
                       "themes": sorted({theme[t] for t in in_p if t in theme}),
                       "src_tasks": srcs, "L16_uses": l_uses,
                       "shared_tasks": sorted(share)})
    themes: dict[str, dict] = {}
    passes = sorted({s["pass"] for s in sols})
    for th in sorted(set(theme.values())):
        per = []
        for p in passes:
            ps = [s for s in sols if s["pass"] == p and s["set"] == "P"
                  and theme.get(s["task_id"]) == th]
            per.append((sum(s["train_ok"] for s in ps),
                        sum(bool(s.get("gate_ok")) for s in ps),
                        sum(s["test_ok"] for s in ps)))
        if any(any(x) for x in per) or per:
            themes[th] = {"n": sum(v == th for v in theme.values()),
                          "last": per[-1] if per else None,
                          "best_gate": max((x[1] for x in per), default=0)}
    late = [r for r in rows if int(r["pass"]) >= 1]
    return {
        "dir": str(d.relative_to(ROOT)),
        "solved_L": col("solved_L"), "solved_H": col("solved_H"),
        "solved_H24": col("solved_H24"), "clean_P": col("clean_P"),
        "solved_P": col("solved_P"), "budget_P": col("budget_P"),
        "false_pos": col("false_pos"), "lib_from_P": col("lib_from_P"),
        "nodes_total": col("nodes_total"), "wall_s": col("wall_s"),
        "AUC_L": sum(int(r["solved_L"]) for r in late),
        "delta": int(rows[-1]["solved_L"]) - int(rows[0]["solved_L"]),
        "logcost_L": round(sum(float(r["logcost_L"]) for r in late), 3),
        "curve_sha": curve.curve_sha(d / "curve.csv"),
        "blocks": blocks, "themes": themes,
        "P_block_L16_uses": sum(b["L16_uses"] for b in blocks
                                if b["origin"] in ("P", "P+L")),
        "max_shared": max((len(b["shared_tasks"]) for b in blocks), default=0),
    }


def main() -> None:
    out = [summarise(Path(a).resolve()) for a in sys.argv[1:]]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
