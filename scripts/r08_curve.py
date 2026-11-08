"""Run one r08 learning curve / meta experiment -> reports/curve-r08/<tree>/.

Trees (notes/rounds/r08/03-設計.md §2, §8):
  dec-g1     r07 control (decomposition + G1, r07 gate/library rules)
  pool       decomposition (DEFAULT) + G1 + themed practice pool P32, LOO gate
  pool-noG1  same P budget schedule, no learning (compute dividend)
  pool-rand32  P = 32 blind tasks without themes (D-r8-15)
  pool-foot32  P = 32 tasks from foothold themes (D-r8-18)
  pool-halves  pool with DEFAULT + halves splits (after the meta action)
  pool-g4    pool + G4, one curve per CRN --seed (80% P subset)
  meta       --rounds of layer 1+2 on 4-pass pool curves (80% P), P cap 100k
  action     --action decomp:<split>: one agent meta action, same CRN judge

    nice -n 19 systemd-run --user --scope -q -p MemoryMax=16G \
        uv run python scripts/r08_curve.py --tree pool
"""

import argparse
import json
import sys
import time
from pathlib import Path

from arcagi.grow import backend, curve, meta
from arcagi.grow import knobs as kn

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "curve-r08"
KNOBS = ROOT / "data" / "r08" / "knobs.json"
TREES = ["dec-g1", "pool", "pool-noG1", "pool-rand32", "pool-foot32",
         "pool-halves", "pool-g4", "meta", "action"]
META_PASSES = 4
META_CAP = 100_000


def make_cfg(tree: str, knobs: kn.Knobs, seed: int, passes: int,
             workers: int) -> curve.Config:
    common = {"tree": tree, "knobs": knobs, "seed": seed, "passes": passes,
              "workers": workers, "taskset": curve.TASKSET_R08, "h24": True}
    if tree == "dec-g1":  # r07 rules: test-right L16 feeds G1, cap 40, retire 3
        return curve.Config(**common, learn=True, g4=False, gate="r07")
    r08 = {**common, "gate": "loo", "pool": "all", "retire_after": 2}
    if tree == "pool":
        return curve.Config(**r08, learn=True, g4=False)
    if tree == "pool-noG1":
        return curve.Config(**r08, learn=False, g4=False)
    if tree == "pool-foot32":
        return curve.Config(**{**r08, "pool": "foot32"}, learn=True, g4=False)
    if tree == "pool-halves":
        return curve.Config(**{**r08, "knobs": knobs.with_(
            decomp_set="default+halves")}, learn=True, g4=False)
    if tree == "pool-rand32":
        return curve.Config(**{**r08, "pool": "rand32"}, learn=True, g4=False)
    if tree == "pool-g4":
        return curve.Config(**r08, learn=True, g4=True, pool_frac=0.8)
    if tree in ("meta", "action"):  # no G4 (time); CRN = P 80% subset
        return curve.Config(**r08, learn=True, g4=False, pool_frac=0.8,
                            pool_cap=META_CAP)
    raise ValueError(tree)


def meta_cfg_for(workers: int):
    def cfg_for(knobs: kn.Knobs, seed: int) -> curve.Config:
        return make_cfg("meta", knobs, seed, META_PASSES, workers)
    return cfg_for


def allowed_knobs() -> list[str]:
    out = [k for k in kn.CHOICES if k != "decomp"]  # the r08 trees keep it on
    if not backend.HAS_SPLIT_SETS:
        out = [k for k in out if k not in kn.SPLIT_KNOBS]
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, choices=TREES)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", default="1,2,3,4,5", help="meta CRN seeds")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--passes", type=int, default=curve.N_PASSES)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--action", default=None, help="decomp:<split>")
    ap.add_argument("--commit", default="", help="seed commit for the ledger")
    ap.add_argument("--agent-min", type=float, default=0.0)
    ap.add_argument("--fresh", action="store_true",
                    help="action: re-score the base on this snapshot")
    a = ap.parse_args(argv)
    if a.workers > 8:
        sys.exit("workers <= 8 (r08 line B resource rule)")
    knobs = kn.load(KNOBS)
    if a.tree == "dec-g1":
        knobs = kn.load(curve.TASKSET.parent / "knobs.json").with_(
            decomp=True, lib_cap=40)
    seeds = tuple(int(s) for s in a.seeds.split(","))
    if a.tree in ("meta", "action"):
        out = a.out or REPORTS / a.tree
        out.mkdir(parents=True, exist_ok=True)
        libs = ROOT / "aos" / "seedlib" / f"r08-{a.tree}"
        cfg_for = meta_cfg_for(a.workers)
        state = out.parent / "meta" / "final.json"
        if a.tree == "meta":
            hist, final, score = meta.run_meta_r08(
                a.rounds, cfg_for, knobs, out, libs, seeds=seeds,
                allowed=allowed_knobs())
            (out / "rounds.json").write_text(json.dumps(hist, indent=1) + "\n")
            state.write_text(json.dumps({"knobs": final.to_dict(),
                                         "score": score}, indent=1) + "\n")
            return
        name = a.action.split(":", 1)[1]
        start = knobs
        before = None
        if state.exists():  # start from the knobs meta ended with
            st = json.loads(state.read_text())
            start = kn.Knobs(**st["knobs"])
            before = None if a.fresh else st["score"]
        if not a.fresh and (out / "base.json").exists():  # same-snapshot base
            before = json.loads((out / "base.json").read_text())
        if before is None:
            before = meta.score_r08(cfg_for, start, "base", seeds, out, libs)
            (out / "base.json").write_text(json.dumps(before, indent=1) + "\n")
        cur = start.decomp_set
        trial = start.with_(decomp_set=f"{cur}+{name}" if cur != "none"
                            else f"default+{name}",
                            sub_lam_depth=3 if name == "nest" else start.sub_lam_depth)
        t0 = time.perf_counter()
        after = meta.score_r08(cfg_for, trial, f"decomp-{name}", seeds, out, libs)
        row = meta.r08_row("r08-agent", before, after, action=f"decomp:{name}",
                           commit=a.commit, knobs_before=start.to_dict(),
                           knobs_after=trial.to_dict(), seeds=list(seeds),
                           agent_min=a.agent_min,
                           note="r08 line B: line A split as a meta action, "
                                "same CRN judge (D-r8-5)")
        meta.append_ledger(row)
        print(json.dumps({k: row[k] for k in ("action", "logcost_before_seeds",
                          "logcost_after_seeds", "auc_before_seeds",
                          "auc_after_seeds", "mean_drop", "se", "accepted")}))
        print(f"wall {time.perf_counter() - t0:.0f}s")
        return
    name = f"{a.tree}/seed{a.seed}" if a.tree == "pool-g4" else a.tree
    out = a.out or REPORTS / name
    cfg = make_cfg(a.tree, knobs, a.seed, a.passes, a.workers)
    lib_dir = ROOT / "aos" / "seedlib" / ("r08-" + name.replace("/", "-"))
    if a.out is not None:
        lib_dir = lib_dir.with_name(lib_dir.name + "-" + a.out.name)
    rows = curve.run_curve(cfg, out, lib_dir)
    print(json.dumps({"tree": name, "AUC_L": curve.auc_l(rows),
                      "delta": curve.delta(rows),
                      "logcost_L": round(sum(float(r["logcost_L"]) for r in rows
                                             if int(r["pass"]) >= 1), 3),
                      "curve_sha": curve.curve_sha(out / "curve.csv")}))


if __name__ == "__main__":
    main()
