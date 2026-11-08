"""Foundry (lost wax, 02-規劃-fable.md §2; 03-設計.md §4 proposal 2).

* ``pick_task(root)``: a P48 task (never L16 / H8 / H24) whose three-projection
  fingerprint (``hammer.proj``) is nearest to an unsolved L16 task, and that
  has no request or wax yet. Unsolved L16 = the latest
  ``epochs/<n>/solutions.jsonl`` (all L16 if there is none).
* ``request(root, task_id, epoch)``: writes
  ``foundry/requests/pending/<epoch>-<task>.md`` (train pairs only, the wax
  format and the rules). The tree does not wait (``foundry_wait_sec`` = 0).
* ``ingest(root, wax_path, epoch=None)``: wax trajectory -> segments
  ``(S_i, S_{i+1})`` over all pairs -> ``arcbatch --mode seed-sub`` (budget
  200k, current live library) -> constant holes -> segment residual gate ->
  ``comb incubating by:foundry`` rows. Failed segments become fracture rows in
  ``nodes/foundry/_witness.jsonl``; ``frozen.json#/priors`` gains the bits; one
  ledger row ``kind: foundry`` (evals: seed-sub nodes + LLM tax). Then the
  cross-wax upgrade: >= 2 foundry combs from different wax that
  ``compress.anti_unify`` merges (holes <= 2) give a templated comb.

Wax format (``foundry/wax/<task>.jsonl``): first line
``{"task","pairs":n,"steps":["tag",...],"by":"claude-opus"|"test-replay",
"req","verified":true}``; then one line per ``{"pair","step","tag","grid"}``
with step 1..k (step 0 is the train input; the last step must equal the
train output). A ``by: test-replay`` wax is a pipeline test: its rows carry
``evidence.test_replay = true`` and it pays no LLM tax (it does not count for
M2(c)).

Constant holes: an integer literal of a fitted segment program (not a lambda
arity) becomes a hole when it is not in {-1, 0, 1, 2} or does not occur in
every train input of the task; at most ``MAX_HOLES`` distinct constants (first
seen). The signature comes from ``grow.sig.infer_sig``; if it does not type,
the unholed body is kept.

Segment residual gate (all must pass): ``info_bits(outputs) >= 8``,
``prog_bits <= 0.6 * diff_bits`` and leave-one-out (>= 3 pairs; fewer pairs
pass, as in ``grow.pool.loo_ok``). prog_bits = size x log2(vocab), vocab = 32
primitives + live blocks + 10 digits + ``$in``; diff_bits = cells of S_{i+1}
that differ from S_i (all cells if the shape changes) x log2(10).

Wiring for epoch.py: on ``stall == "stop"``: ``t = pick_task(root)`` then
``request(root, t, n)``; at each epoch boundary ``for w in new_wax(root):
ingest(root, w, epoch=n)``.
"""

import argparse
import json
import math
import sys
from pathlib import Path

from arcagi.grow import compress as gcomp
from arcagi.grow import prog as pg
from arcagi.grow import sig as gsig
from arcagi.hammer import formats as fm
from arcagi.hammer import proj
from arcagi.hammer import route as rt
from arcagi.seed import interp

TRAINING = rt.ROOT / "data" / "ARC-AGI" / "data" / "training"
SUB_BUDGET = 200_000
MAX_HOLES = 2
INFO_MIN = 8.0
PROG_FRAC = 0.6
N_PRIMS = 32
SAFE_INTS = (-1, 0, 1, 2)


def _load_task(tid: str) -> dict:
    return json.loads((TRAINING / f"{tid}.json").read_text())


def _train_ids(root: Path) -> dict:
    return fm.read_json(Path(root) / "truth" / "train" / "taskset.json", {})


# ---------------------------------------------------------------- pick / request

def _unsolved_l(root: Path, l16: list[str]) -> list[str]:
    eps = sorted((Path(root) / "epochs").glob("*/solutions.jsonl"),
                 key=lambda p: int(p.parent.name) if p.parent.name.isdigit() else -1)
    if not eps:
        return list(l16)
    solved = {r["task_id"] for r in fm.read_jsonl(eps[-1])
              if r.get("train_ok") and r.get("test_ok")}
    return [t for t in l16 if t not in solved]


def _cast(root: Path) -> set[str]:
    d = Path(root) / "foundry"
    done = {p.stem for p in (d / "wax").glob("*.jsonl")}
    for p in (d / "requests").glob("*/*.md"):
        done.add(p.stem.split("-", 1)[-1])
    return done


def pick_task(root: Path) -> str | None:
    """Nearest-to-unsolved-L16 P48 task that was not cast yet."""
    ids = _train_ids(root)
    l16, pool = ids.get("L16", []), ids.get("P", [])
    # H8 / H24 are never loaded here; P48 already excludes them (r09_taskset).
    cand = [t for t in pool if t not in set(l16) and t not in _cast(root)]
    gaps = _unsolved_l(root, l16)
    if not cand or not gaps:
        return None
    fl = [proj.fingerprint(_load_task(t)) for t in gaps]
    best = None
    for t in sorted(cand):
        fp = proj.fingerprint(_load_task(t))
        d = min(proj.distance(fp, g) for g in fl)
        if best is None or d < best[0]:
            best = (d, t)
    return best[1]


RULES = "\n".join([
    "## 規矩", "",
    "- 寫一支帶檢查點的 Python：每一步呼叫 `step(tag, grid)`，3～8 步，"
    "每一步是**整格變換**（不准把逐格迴圈拆成步）。",
    "- 同一個 tag 在所有 pair 的語意相同；最後一步必須等於該 pair 的 output；"
    "驗過全部 train 對才交。",
    "- **只交軌跡**（下面的蠟模格式），程式本身銷毀，不交。", ""])


def request(root: Path, task_id: str, epoch: int) -> Path:
    """Write the wax request (train pairs only) and return its path."""
    t = _load_task(task_id)
    wax = f"foundry/wax/{task_id}.jsonl"
    lines = [f"# 鑄模請求 {task_id}（epoch {epoch}）", "",
             f"題目只給 train 對（{len(t['train'])} 對，不含 test）。"
             f"蠟模寫到 `{wax}`。", "",
             "## train 對", ""]
    for i, p in enumerate(t["train"]):
        lines += [f"pair {i}", "```json", json.dumps({"input": p["input"],
                  "output": p["output"]}), "```", ""]
    lines += ["## 蠟模格式", "", "首行：", "```json",
              json.dumps({"task": task_id, "pairs": len(t["train"]),
                          "steps": ["tag1", "tag2", "tag3"], "by": "claude-opus",
                          "req": f"{epoch}-{task_id}.md", "verified": True},
                         ensure_ascii=False),
              "```", "之後每 pair 每步一行：", "```json",
              json.dumps({"pair": 0, "step": 1, "tag": "tag1", "grid": [[0]]}),
              "```", "", RULES]
    path = Path(root) / "foundry" / "requests" / "pending" / f"{epoch}-{task_id}.md"
    fm.write_text(path, "\n".join(lines))
    fm.append_ledger(root, {"kind": "foundry", "epoch": epoch, "layer": 1,
                           "by": "foundry", "op_ids": [], "event": "request",
                           "task": task_id, "path": str(path.relative_to(root))})
    return path


def new_wax(root: Path) -> list[Path]:
    """Wax files not ingested yet (no ledger ``ingest`` row naming them)."""
    seen = {r.get("wax") for r in fm.load_ledger(root)
            if r.get("kind") == "foundry" and r.get("event") == "ingest"}
    return [p for p in sorted((Path(root) / "foundry" / "wax").glob("*.jsonl"))
            if str(p.relative_to(root)) not in seen]


# ---------------------------------------------------------------- wax parsing

def parse_wax(path: Path) -> tuple[dict, list[list]]:
    """(header, states) with states[p] = [S_0, S_1, ..., S_k] for pair p."""
    rows = fm.read_jsonl(path)
    head, body = rows[0], rows[1:]
    t = _load_task(head["task"])
    k = len(head["steps"])
    if not 3 <= k <= 8:
        raise ValueError(f"wax {path}: {k} steps (need 3..8)")
    states = [[p["input"]] + [None] * k for p in t["train"]]
    for r in body:
        if r["tag"] != head["steps"][r["step"] - 1]:
            raise ValueError(f"wax {path}: tag mismatch at {r['pair']}/{r['step']}")
        states[r["pair"]][r["step"]] = r["grid"]
    for p, st in enumerate(states):
        if any(s is None for s in st):
            raise ValueError(f"wax {path}: pair {p} has missing steps")
        if st[-1] != t["train"][p]["output"]:
            raise ValueError(f"wax {path}: pair {p} last step != output")
    return head, states


# ---------------------------------------------------------------- helpers

def _shape_t(v) -> str:
    return rt._type_of(interp.to_value(v), None) if isinstance(v, list) else "int"


def diff_bits(a, b) -> float:
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and \
            all(isinstance(x, list) and isinstance(y, list) and len(x) == len(y)
                for x, y in zip(a, b)):
        n = sum(x != y for ra, rb in zip(a, b) for x, y in zip(ra, rb))
    else:
        n = sum(1 for _ in rt._cells(interp.to_value(b)))
    return n * math.log2(10)


def _ints_in(v) -> set:
    return set(rt._cells(interp.to_value(v)))


def hole_out(prog, inputs) -> tuple:
    """Replace up to MAX_HOLES task constants by holes. -> (body, consts)."""
    common = set.intersection(*(_ints_in(x) for x in inputs)) if inputs else set()
    found: list[int] = []

    def go(p):
        if isinstance(p, bool):
            return p
        if isinstance(p, int):
            if (p not in SAFE_INTS or p not in common) and \
                    (p in found or len(found) < MAX_HOLES):
                if p not in found:
                    found.append(p)
                return (f"{pg.HOLE_PREFIX}{found.index(p)}",)
            return p
        if p[0] == "lam":
            return ("lam", p[1], go(p[2]))
        if p[0] == "blk":
            return ("blk", p[1], *(go(a) for a in p[2:]))
        return (p[0], *(go(a) for a in p[1:]))

    return go(prog), found


def _blocks(root: Path, ops: list[dict]) -> list[dict]:
    """Live comb rows as seed.library block dicts."""
    out = []
    for o in ops:
        if o["kind"] == "comb" and o["status"] == "live" and o.get("sig"):
            out.append({"name": o["payload"].get("name", o["id"]),
                        "body": o["payload"]["body"], "sig": o["sig"],
                        "src_tasks": [], "saving": 0.0, "uses": 0})
    return out


def _check(prog_json, pairs, lib) -> bool:
    try:
        p = interp.from_json(prog_json)
        return all(interp.run(p, x, lib) == interp.to_value(y) for x, y in pairs)
    except Exception:
        return False


def _prog_of(r: dict):
    return r.get("program") or (r.get("cond") or {}).get("program")


# ---------------------------------------------------------------- ingest

def ingest(root: Path, wax_path: Path, epoch: int | None = None,
           work: Path | None = None, threads: int = 6) -> list[dict]:
    """Wax -> comb incubating rows (returned, already appended to ops)."""
    from arcagi.seed.library import Library

    root, wax_path = Path(root), Path(wax_path)
    work = Path(work or root / "foundry" / "work" / wax_path.stem)
    work.mkdir(parents=True, exist_ok=True)
    head, states = parse_wax(wax_path)
    tid = head["task"]
    test = head.get("by") == "test-replay"
    if epoch is None:
        epoch = max([r.get("epoch", 0) for r in fm.load_ledger(root)
                     if isinstance(r.get("epoch"), int)] + [0])
    ops = fm.load_ops(root)
    blocks = _blocks(root, ops)
    lib_path, lib = None, None
    if blocks:
        lib_path = work / "lib.json"
        fm.write_text(lib_path, json.dumps(blocks, indent=1))
        lib = Library.load(lib_path)
    inputs = [st[0] for st in states]
    vocab = N_PRIMS + len(blocks) + 10 + 1
    k = len(head["steps"])

    # one seed-sub job per segment, plus leave-one-out jobs
    jobs, segs = [], []
    for i in range(k):
        pairs = [(st[i], st[i + 1]) for st in states]
        sid = f"{tid}#{i}"
        xs = [interp.to_value(x) for x, _ in pairs]
        ys = [interp.to_value(y) for _, y in pairs]
        from arcagi.seed.prims import task_consts
        consts = list(task_consts((*xs, *ys)))
        it, ot = _shape_t(pairs[0][0]), _shape_t(pairs[0][1])
        jobs.append(rt.sub_row(sid, xs, ys, it, ot, consts,
                              str(lib_path) if lib_path else None, SUB_BUDGET))
        if len(pairs) >= 3:
            for j in range(len(pairs)):
                rest = pairs[:j] + pairs[j + 1:]
                jobs.append(rt.sub_row(
                    f"{sid}/loo{j}", [interp.to_value(x) for x, _ in rest],
                    [interp.to_value(y) for _, y in rest], it, ot, consts,
                    str(lib_path) if lib_path else None, SUB_BUDGET))
        segs.append((i, sid, pairs))
    res = rt.run_subs(jobs, work, threads)
    nodes = sum(r.get("nodes", 0) for r in res.values())

    rows, fails, segs_out = [], [], []
    node_dir = root / "nodes" / "foundry"
    for i, sid, pairs in segs:
        prog = _prog_of(res.get(sid, {}))
        info = rt.info_bits(interp.to_value(y) for _, y in pairs)
        dbits = sum(diff_bits(x, y) for x, y in pairs)
        rec = {"seg": i, "tag": head["steps"][i], "program": prog,
               "info_bits": info, "diff_bits": round(dbits, 3)}
        ok = prog is not None and _check(prog, pairs, lib)
        loo = True
        if ok and len(pairs) >= 3:
            for j in range(len(pairs)):
                pj = _prog_of(res.get(f"{sid}/loo{j}", {}))
                if pj is None or not _check(pj, [pairs[j]], lib):
                    loo = False
                    break
        if ok:
            body, consts = hole_out(interp.from_json(prog), inputs)
            sig = gsig.infer_sig(body) if consts else gsig.infer_sig(body)
            if sig is None and consts:
                body, consts = interp.from_json(prog), []
                sig = gsig.infer_sig(body)
            pbits = pg.size(body) * math.log2(vocab)
            nontrivial = all(x != y for x, y in pairs) and \
                len({json.dumps(y) for _, y in pairs}) > 1
            rec.update({"body": interp.to_json(body), "holes": len(consts),
                        "consts": consts, "sig": sig,
                        "prog_bits": round(pbits, 3), "loo_ok": loo,
                        "nontrivial": nontrivial})
            gate = info >= INFO_MIN and pbits <= PROG_FRAC * dbits and loo
            rec["gate"] = gate
            if gate and sig is not None:
                oid = f"comb_fd_{tid}_{i}"
                if any(o["id"] == oid for o in ops):
                    oid += f"_e{epoch}"
                op = fm.new_op(oid, "comb", {"body": interp.to_json(body),
                                            "name": oid,
                                            "src": f"wax:{tid}#{i}",
                                            "tag": head["steps"][i],
                                            "holes": len(consts),
                                            "consts": consts},
                              "foundry", epoch, sig=sig, mdl_bits=round(pbits, 3))
                op["evidence"]["test_replay"] = test
                op["evidence"]["nontrivial"] = nontrivial
                op["env_hash"] = fm.env_hash(ops)
                rows.append(op)
        else:
            rec["gate"] = False
        if not rec["gate"]:
            fails.append(i)
            fm.append_witness(node_dir, {
                "id": f"wf-{tid}-{i}", "task": tid, "pair": None, "dir": "fwd",
                "src": f"wax:{tid}#{i}",
                "examples": [[x, y] for x, y in pairs],
                "props": {"tag": head["steps"][i], "fit_program": prog},
                "info_bits": info, "status": "open", "fit": None,
                "epoch": epoch})
        segs_out.append(rec)

    if rows:
        fm.append_ops(root, rows)
    up = upgrade(root, epoch)
    frozen = fm.load_frozen(root)
    if frozen is not None:
        for o in rows + up:
            frozen.setdefault("priors", []).append(
                {"id": o["id"], "bits": o["mdl_bits"], "src": o["payload"]["src"],
                 "epoch": epoch, "test_replay": test})
        fm.write_json(root / "frozen.json", frozen)
    tax = 0 if test else (frozen or {}).get("llm_tax_evals", fm.LLM_TAX_EVALS)
    fm.append_ledger(root, {
        "kind": "foundry", "epoch": epoch, "layer": 1, "by": "foundry",
        "event": "ingest", "task": tid, "wax": str(wax_path.relative_to(root))
        if wax_path.is_relative_to(root) else str(wax_path),
        "wax_by": head.get("by"), "test_replay": test,
        "op_ids": [o["id"] for o in rows + up], "segments": segs_out,
        "fractures": fails,
        "evals": {"body": 0, "shadow": 0, "meta": 0, "foundry": nodes,
                  "llm_tax": tax}})
    return rows + up


def upgrade(root: Path, epoch: int) -> list[dict]:
    """Cross-wax anti-unification of foundry combs (>= 2 from different wax)."""
    ops = fm.load_ops(root)
    fd = [o for o in ops if o["kind"] == "comb" and o["by"] == "foundry"
          and not o["payload"].get("generalized_from")]
    have = {tuple(sorted(o["payload"].get("generalized_from", [])))
            for o in ops}
    out = []
    for a in range(len(fd)):
        for b in range(a + 1, len(fd)):
            oa, ob = fd[a], fd[b]
            if oa["payload"]["src"].split("#")[0] == ob["payload"]["src"].split("#")[0]:
                continue
            key = tuple(sorted((oa["id"], ob["id"])))
            if key in have:
                continue
            t = gcomp.anti_unify(interp.from_json(oa["payload"]["body"]),
                                 interp.from_json(ob["payload"]["body"]), MAX_HOLES)
            if t is None or pg.size(t) < 2 or gcomp.n_holes(t) == 0:
                continue
            sig = gsig.infer_sig(t)
            if sig is None:
                continue
            oid = f"comb_fdu_{oa['id'][8:]}__{ob['id'][8:]}"
            op = fm.new_op(oid, "comb", {"body": interp.to_json(t), "name": oid,
                                        "src": oa["payload"]["src"] + "+"
                                        + ob["payload"]["src"],
                                        "generalized_from": list(key),
                                        "holes": gcomp.n_holes(t)},
                          "foundry", epoch, sig=sig,
                          mdl_bits=round(pg.size(t) * math.log2(N_PRIMS + 11), 3))
            out.append(op)
            have.add(key)
    if out:
        fm.append_ops(root, out)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="hammer foundry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("pick")
    s.add_argument("root")
    s = sub.add_parser("request")
    s.add_argument("root")
    s.add_argument("task")
    s.add_argument("--epoch", type=int, default=0)
    s = sub.add_parser("ingest")
    s.add_argument("root")
    s.add_argument("wax")
    s.add_argument("--epoch", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "pick":
        print(pick_task(Path(a.root)))
    elif a.cmd == "request":
        print(request(Path(a.root), a.task, a.epoch))
    else:
        for o in ingest(Path(a.root), Path(a.wax), a.epoch):
            keep = ("id", "status", "by", "sig", "mdl_bits")
            print(json.dumps({k: o[k] for k in keep}
                             | {"body": o["payload"]["body"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
