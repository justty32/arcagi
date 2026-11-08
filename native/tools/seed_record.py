"""Record every subsearch (``seed.decomp._Solver._direct``: one Enumerator +
search, optionally cond_witness) of Python solves as seed-sub JSONL, then
compare arcbatch --mode seed-sub on them. The seed sources are only wrapped
at runtime (read-only).

    python native/tools/seed_record.py record --tasks IDS.txt --budget 100000 \
        --splits map,zip_pos,if,take,append,conj_transpose,conj_reverse,halves,nest \
        --out-dir DIR
    native/bin/arcbatch --mode seed-sub --subproblems DIR/subs.jsonl --out DIR/got.jsonl
    python native/tools/seed_record.py compare DIR
"""

import argparse
import json
import multiprocessing
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from arcagi.seed import decomp, interp  # noqa: E402
from arcagi.seed import enum as S_enum  # noqa: E402
from arcagi.seed.library import Library  # noqa: E402
from arcagi.seed.types import show  # noqa: E402

DATA = ROOT / "data" / "ARC-AGI" / "data" / "training"
if not DATA.is_dir():
    DATA = Path.home() / "repo" / "arcagi" / "data" / "ARC-AGI" / "data" / "training"


def _val(v):
    return [_val(x) for x in v] if isinstance(v, tuple) else v


def _prog(p):
    return interp.to_json(p) if p is not None else None


def _record(job):
    tid, budget, names, sub_lam_depth, lib_dir = job
    rows = []
    orig_search, orig_cond = decomp.search, decomp.cond_witness
    lib_paths: dict = {}

    def lib_path(lib):
        key = tuple(b.name for b in lib.blocks)
        if not key:
            return None
        if key not in lib_paths:
            p = Path(lib_dir) / f"{tid}-lib{len(lib_paths)}.json"
            lib.save(p)
            lib_paths[key] = str(p)
        return lib_paths[key]

    def search(en):
        out = orig_search(en)
        rows.append({
            "id": f"{tid}/{len(rows)}", "lib": lib_path(en.lib), "budget": en.budget,
            "examples": [[_val(x), _val(y)] for x, y in zip(en.xs, en.outs)],
            "in_type": show(en.in_type), "out_type": show(en.out_type),
            "extra": [{"prog": interp.to_json(p), "type": show(t), "vals": [_val(v) for v in vs]}
                      for p, t, vs in en.extra],
            "sub": en.sub, "consts": list(en.consts),
            "lam_depth": en.lam_depth if en.lam_depth is not None else decomp.lam.LAM_DEPTH,
            "lam_body_max": en.lam_body_max if en.lam_body_max is not None else decomp.lam.LAM_BODY_MAX,
            "order": {}, "cond_limit": None, "near": not en.sub,
            "_expect": {"program": _prog(en.found), "nodes": en.nodes,
                        "nodes_to_first": en.nodes_to_first,
                        "near": [[_prog(p), sc] for sc, _, p in sorted(en.near, reverse=True)]},
        })
        return out

    def cond(en, limit):
        prog, used = orig_cond(en, limit)
        rows[-1]["cond_limit"] = limit
        rows[-1]["_expect"]["cond"] = {"program": _prog(prog), "used": used}
        return prog, used

    en_order: dict = {}
    decomp.search, decomp.cond_witness = search, cond
    try:
        t = json.loads((DATA / f"{tid}.json").read_text())
        train = [(e["input"], e["output"]) for e in t["train"]]
        S_enum.solve(train, Library(), budget, None, decompose=names,
                     sub_lam_depth=sub_lam_depth)
    finally:
        decomp.search, decomp.cond_witness = orig_search, orig_cond
    return rows


def cmd_record(a):
    ids = [w.split()[0] for w in Path(a.tasks).read_text().splitlines() if w.strip()]
    names = frozenset(a.splits.split(","))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(t, a.budget, names, a.sub_lam_depth, str(out)) for t in ids]
    with multiprocessing.get_context("fork").Pool(a.workers) as pool:
        per = pool.map(_record, jobs, chunksize=1)
    rows = [r for rs in per for r in rs]
    with open(out / "subs.jsonl", "w") as f, open(out / "expect.jsonl", "w") as g:
        for r in rows:
            exp = r.pop("_expect")
            f.write(json.dumps(r) + "\n")
            g.write(json.dumps({"id": r["id"], **exp}) + "\n")
    print(f"{len(rows)} subsearches from {len(ids)} tasks")


def cmd_compare(a):
    d = Path(a.out_dir)
    exp = [json.loads(x) for x in (d / "expect.jsonl").read_text().splitlines()]
    got = {json.loads(x)["id"]: json.loads(x) for x in (d / "got.jsonl").read_text().splitlines()}
    bad = 0
    for e in exp:
        g = got.get(e["id"], {})
        keys = ["program", "nodes", "nodes_to_first", "near"] + (["cond"] if "cond" in e else [])
        diff = [k for k in keys if e.get(k) != g.get(k)]
        if diff:
            bad += 1
            if bad <= 8:
                print(e["id"], diff, json.dumps({k: e.get(k) for k in diff})[:200],
                      json.dumps({k: g.get(k) for k in diff})[:200])
    print(f"{len(exp)} subsearches: {len(exp) - bad} identical, {bad} differ")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--tasks", required=True)
    r.add_argument("--budget", type=int, default=100000)
    r.add_argument("--splits", default=",".join(sorted(decomp.DEFAULT_SPLITS)))
    r.add_argument("--sub-lam-depth", type=int, default=None)
    r.add_argument("--workers", type=int, default=6)
    r.add_argument("--out-dir", required=True)
    c = sub.add_parser("compare")
    c.add_argument("out_dir")
    a = ap.parse_args(argv)
    if getattr(a, "workers", 1) > 6:
        sys.exit("workers <= 6")
    return cmd_record(a) if a.cmd == "record" else cmd_compare(a)


if __name__ == "__main__":
    sys.exit(main())
