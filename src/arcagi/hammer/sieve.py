"""Layer-2 sieve scans (02-規劃-fable.md §4, 03-設計.md §4 proposal 3).

``exclude``: leave-one-out over the 32 seed primitives with arcbatch
``configs.exclude`` (re-checks still use all primitives). Tasks: L16 + P48
only, read straight from the taskset's ``learn`` / ``P48`` keys (H8 / H24 are
never loaded). Judge on the two folds ``sha1(task_id + "r09AB")`` (even last
hex digit -> A, odd -> B): a primitive is *selected* on fold A when A loses 0
solved tasks and sum(nodes_to_first) over A's base-solved tasks drops >= 5%;
a selected primitive is *accepted* when fold B (out of fold) also loses 0 and
drops >= 5% or solves >= 1 more. Accepted ones become ``kind: sieve
status: incubating by: gate-scan`` rows (``--write``); every tried primitive
gets one ledger row (``layer: 2``, ``by: gate-scan``, ``accepted`` as is).

``equiv`` (mine only, nothing is applied): 5 random 4x4 probes (fixed seed),
all first-order programs of size <= 3 over ``$in`` and the constants
(no lambdas / HOFs), well-typed by ``grow.sig.infer_sig``, values by
``arcbatch --mode seed-run``; prints the
number of observational equivalence classes and the estimated prunable
fraction (programs that are not their class's first member).

    python -m arcagi.hammer.sieve exclude [--root ROOT] [--write]
    python -m arcagi.hammer.sieve equiv
"""

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

from arcagi.hammer import formats as fm
from arcagi.seed.prims import CONSTS, PRIMS

ROOT = Path(__file__).resolve().parents[3]
ARCBATCH = ROOT / "native" / "bin" / "arcbatch"
TASKSET = ROOT / "data" / "r09" / "taskset.json"
OUT = ROOT / "reports" / "curve-r09" / "sieve"
DROP_MIN = 0.05


def fold(task_id: str) -> str:
    h = hashlib.sha1((task_id + "r09AB").encode()).hexdigest()
    return "A" if int(h[-1], 16) % 2 == 0 else "B"


def train_ids(taskset: Path = TASKSET) -> list[str]:
    """L16 + P48 ids only (holdout keys are not read)."""
    d = json.loads(Path(taskset).read_text())
    ids = []
    for k in ("learn", "P48"):
        ids += [e["task_id"] if isinstance(e, dict) else e for e in d[k]]
    return list(dict.fromkeys(ids))


def run_seed(ids: list[str], configs: list[dict], work: Path,
             threads: int = 8) -> list[dict]:
    work.mkdir(parents=True, exist_ok=True)
    (work / "ids.txt").write_text("\n".join(ids) + "\n")
    (work / "configs.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in configs))
    out = work / "out.jsonl"
    subprocess.run([str(ARCBATCH), "--mode", "seed", "--tasks",
                    str(work / "ids.txt"), "--configs",
                    str(work / "configs.jsonl"), "--threads", str(min(threads, 8)),
                    "--out", str(out)], check=True, capture_output=True)
    return [json.loads(x) for x in out.read_text().splitlines() if x.strip()]


def _fold_stats(base: dict, cand: dict, ids: list[str]) -> dict:
    sb = {t for t in ids if base[t]["train_ok"] and base[t]["test_ok"]}
    sc = {t for t in ids if cand[t]["train_ok"] and cand[t]["test_ok"]}
    nb = sum(base[t]["nodes_to_first"] or 0 for t in sb)
    nc = sum(cand[t]["nodes_to_first"] or 0 for t in sb & sc)
    return {"solved_base": len(sb), "solved": len(sc), "lost": len(sb - sc),
            "gained": len(sc - sb), "ntf_base": nb, "ntf": nc,
            "drop": round(1 - nc / nb, 4) if nb else 0.0}


def exclude_scan(work: Path, budget: int = 100_000, lib: str | None = None,
                 threads: int = 8) -> list[dict]:
    ids = train_ids()
    base_cfg = {"name": "base", "budget": budget, "decomp": True, "lam_depth": 2}
    if lib:
        base_cfg["lib"] = lib
    cfgs = [base_cfg] + [{**base_cfg, "name": f"x_{p}", "exclude": [p]}
                         for p in PRIMS]
    rows = run_seed(ids, cfgs, work, threads)
    by = {}
    for r in rows:
        if "task_id" in r:
            by.setdefault(r["config"], {})[r["task_id"]] = r
    fa = [t for t in ids if fold(t) == "A"]
    fb = [t for t in ids if fold(t) == "B"]
    res = []
    for p in PRIMS:
        c = by[f"x_{p}"]
        a = _fold_stats(by["base"], c, fa)
        b = _fold_stats(by["base"], c, fb)
        sel = a["lost"] == 0 and a["drop"] >= DROP_MIN
        acc = sel and b["lost"] == 0 and (b["drop"] >= DROP_MIN or b["gained"] >= 1)
        res.append({"prim": p, "A": a, "B": b, "selected": sel, "accepted": acc})
    return res


def write_exclude(root: Path, res: list[dict], epoch: int) -> list[str]:
    """Ledger row per tried primitive; incubating sieve rows for accepted."""
    new = []
    for r in res:
        oid = f"sieve_x_{r['prim']}"
        if r["accepted"] and not any(o["id"] == oid for o in fm.load_ops(root)):
            new.append(fm.new_op(oid, "sieve", {"exclude": [r["prim"]]},
                                 "gate-scan", epoch))
        fm.append_ledger(root, {
            "kind": "layer2", "epoch": epoch, "layer": 2, "by": "gate-scan",
            "scan": "sieve/exclude", "op_ids": [oid] if r["accepted"] else [],
            "variant": {"exclude": [r["prim"]]},
            "judge": {"accepted": r["accepted"], "selected_A": r["selected"],
                      "A": r["A"], "B": r["B"]}})
    if new:
        fm.append_ops(root, new)
    return [o["id"] for o in new]


# ---------------------------------------------------------------- equiv

UNARY = [p for p, v in PRIMS.items() if v.arity == 1
         and p not in ("map", "filter")]
BINARY = [p for p, v in PRIMS.items() if v.arity == 2
          and p not in ("map", "filter", "zipwith", "fold")]


def programs_le3() -> list:
    leaves = [["$in"]] + list(CONSTS) + [2, 3]
    out = list(leaves)
    for u in UNARY:
        out += [[u, a] for a in leaves]
    for u in UNARY:
        for v in UNARY:
            out += [[u, [v, a]] for a in leaves]
    for b in BINARY:
        out += [[b, x, y] for x in leaves for y in leaves]
    return out


def probes(n: int = 5, seed: int = 9) -> list:
    rng = random.Random(seed)
    return [[[rng.randrange(10) for _ in range(4)] for _ in range(4)]
            for _ in range(n)]


def equiv_scan(work: Path, threads: int = 8) -> dict:
    from arcagi.grow.sig import infer_sig
    from arcagi.seed.interp import from_json

    allp = programs_le3()
    # seed-run evaluates dynamically; keep only well-typed programs
    progs = [p for p in allp if infer_sig(from_json(p)) is not None]
    xs = probes()
    work.mkdir(parents=True, exist_ok=True)
    inp, out = work / "progs.jsonl", work / "vals.jsonl"
    inp.write_text("".join(json.dumps({"id": str(i), "program": p, "inputs": xs})
                           + "\n" for i, p in enumerate(progs)))
    subprocess.run([str(ARCBATCH), "--mode", "seed-run", "--programs", str(inp),
                    "--threads", str(min(threads, 8)), "--out", str(out)],
                   check=True, capture_output=True)
    vals = {}
    for ln in out.read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            vals[int(r["id"])] = r["values"]
    valid = {i: v for i, v in vals.items() if not all(x == "ERR" for x in v)}
    classes: dict[str, list[int]] = {}
    for i in sorted(valid):
        classes.setdefault(json.dumps(valid[i]), []).append(i)
    big = sorted(classes.values(), key=len, reverse=True)[:8]
    return {"generated": len(allp), "typed": len(progs), "valid": len(valid),
            "classes": len(classes),
            "prunable": round(1 - len(classes) / len(valid), 4) if valid else 0.0,
            "biggest": [[json.dumps(progs[i]) for i in c[:4]] + [len(c)]
                        for c in big]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="hammer sieve scans")
    ap.add_argument("kind", choices=("exclude", "equiv"))
    ap.add_argument("--root", default=None)
    ap.add_argument("--work", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--epoch", type=int, default=0)
    a = ap.parse_args(argv)
    work = Path(a.work or OUT / f".work-{a.kind}")
    if a.kind == "exclude":
        res = exclude_scan(work)
        print(json.dumps(res))
        if a.write and a.root:
            print(write_exclude(Path(a.root), res, a.epoch))
    else:
        print(json.dumps(equiv_scan(work)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
