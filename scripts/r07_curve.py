"""Run one tree's 8-pass learning curve -> reports/curve-r07/<tree>/curve.csv.

Trees: ``empty`` (pure enumeration, no G1/G4), ``empty-g1g4`` (G1 + G4, one
curve per --seed), ``old`` (read-only arcagi.solvers.search control).

    nice -n 19 systemd-run --user --scope -q -p MemoryMax=8G \
        uv run python scripts/r07_curve.py --tree empty-g1g4 --seed 0
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from arcagi.grow import curve, meta, oldtree
from arcagi.grow import knobs as kn

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "curve-r07"
SCRATCH = Path("/tmp/claude-1000/-home-lorkhan-repo-arcagi/"
               "5648215c-e662-495d-a192-e1ff3a6e4b3b/scratchpad/r07-B")


def run_old(out: Path, passes: int, workers: int, scratch: Path) -> list[dict]:
    learn, hold = curve.load_taskset()
    ids = [t.task_id for t in learn + hold]
    learn_ids = {t.task_id for t in learn}
    pool = scratch / "old-pool"
    pool.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "aos/pool/config.json", pool / "config.json")
    rows = []
    sols_log = []
    for p in range(min(passes, 2)):
        if p == 0:
            root = oldtree.primitive_root(scratch / "old-blocks-prim")
            sols, wall = oldtree.run_pass(ids, root, pool, workers)
        else:
            root = oldtree.full_root(scratch / "old-blocks-full")
            sols, wall = oldtree.run_pass(ids, root, None, workers)
        n_blocks = len(list(root.glob("*/_metainfo.json")))
        rows.append({
            "pass": p,
            "solved_L": sum(s["test_ok"] for s in sols if s["task_id"] in learn_ids),
            "solved_H": sum(s["test_ok"] for s in sols
                            if s["task_id"] not in learn_ids),
            "wall_s": round(wall, 2), "nodes": None, "llm_calls": 0,
            "lib_size": n_blocks, "lib_bits": None, "mean_prog_nodes": None,
            "nodes_solved": None,
        })
        sols_log += [{"pass": p, **s} for s in sols]
        print(f"[old] pass {p}: L={rows[-1]['solved_L']} H={rows[-1]['solved_H']} "
              f"blocks={n_blocks} wall={wall:.1f}s", flush=True)
    for p in range(2, passes):  # the old tree does not learn: pass>=2 = pass 1
        rows.append({**rows[1], "pass": p})
    out.mkdir(parents=True, exist_ok=True)
    (out / "solutions.jsonl").write_text(
        "".join(json.dumps(s, sort_keys=True) + "\n" for s in sols_log))
    curve.write_csv(rows, out / "curve.csv")
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True,
                    choices=["empty", "empty-g1", "empty-noT", "empty-g1g4",
                             "dec", "dec-g1", "dec-g1g4", "old", "meta"])
    ap.add_argument("--decomp", action="store_true",
                    help="meta: start from decomp=True")
    ap.add_argument("--seeds", default="0,1,2", help="meta CRN seeds")
    ap.add_argument("--rounds", type=int, default=3, help="meta rounds")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--passes", type=int, default=curve.N_PASSES)
    ap.add_argument("--budget", type=int, default=curve.BUDGET)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--knobs", type=Path, default=kn.KNOBS_PATH)
    a = ap.parse_args(argv)
    if a.workers > 6:
        sys.exit("workers <= 6 (r07 resource rule)")
    name = f"{a.tree}/seed{a.seed}" if a.tree.endswith("g1g4") else a.tree
    out = a.out or REPORTS / name
    if a.tree == "meta":
        seeds = tuple(int(s) for s in a.seeds.split(","))
        hist = meta.run_meta(a.rounds, a.passes, out, ROOT / "aos/seedlib/meta",
                             seeds=seeds, workers=a.workers,
                             start=kn.load(a.knobs).with_(decomp=a.decomp))
        (out / "rounds.json").write_text(json.dumps(hist, indent=1) + "\n")
        return
    if a.tree == "old":
        rows = run_old(out, a.passes, a.workers, SCRATCH)
    else:
        knobs = kn.load(a.knobs)
        if a.tree.startswith("dec"):
            knobs = knobs.with_(decomp=True)
        cfg = curve.Config(tree=a.tree, knobs=knobs, seed=a.seed,
                           passes=a.passes, budget=a.budget, workers=a.workers,
                           learn=a.tree in ("empty-g1", "empty-g1g4", "dec-g1",
                                            "dec-g1g4"),
                           g4=a.tree.endswith("g1g4"),
                           exclude=("transpose",) if a.tree == "empty-noT" else ())
        lib_dir = ROOT / "aos" / "seedlib" / name.replace("/", "-")
        rows = curve.run_curve(cfg, out, lib_dir)
    print(json.dumps({"tree": name, "AUC_L": curve.auc_l(rows),
                      "delta": curve.delta(rows),
                      "curve_sha": curve.curve_sha(out / "curve.csv")}))


if __name__ == "__main__":
    main()
