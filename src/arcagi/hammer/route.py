"""Route table (03-設計.md §4 proposal 4): no UCB, a stall-state lookup.

A ``kind: route`` op has payload ``{"when_stall": "ok|starve|saturate",
"arm": "rt_sleep|rt_vsplit|rt_pool|rt_gatescan", "priority": int}``. Each
epoch the live rows whose ``when_stall`` equals the stall state are ranked by
priority (ties: op id) and the top arm is taken. ``stop`` is not in the table
(it triggers the foundry); for routing it falls back to the ``saturate`` rows.
The starting table is ``formats.seed_ops()`` (six rows, all four arms).

Wiring for epoch.py (step ⑤):

    arm = pick_arm([o for o in ops if o["kind"] == "route"], state)
    if arm == "rt_vsplit":
        subs = vsplit_witness(root, unsolved_L16_tasks, epoch)   # writes witness
        fits = solve_subs(subs, lib_path, work_dir)              # arcbatch seed-sub

``rt_vsplit`` (this module): for each unsolved L16 task, the r07 witness
splits (``seed.witness.witness_splits``) of its train pairs become backward
subgoals; those with ``info_bits >= 8`` go into
``nodes/route/_witness.jsonl`` (``dir: bwd``, ``src: decomp:<split>``) and are
solved with ``arcbatch --mode seed-sub``; a fitted subgoal gets
``status: fitted`` + ``fit`` in a second, appended row (the file stays
append-only; the last row per id wins).

info_bits (one definition for route and foundry): over all scalar cells of
the subgoal outputs, the cells that differ from their own output's
background (most common value) each carry log2(10) bits; ``info_bits`` is
their sum. 8 bits = at least 3 informative cells.
"""

import json
import math
import subprocess
from collections import Counter
from pathlib import Path

from arcagi.hammer import formats as fm
from arcagi.seed import witness as wt
from arcagi.seed.interp import to_json, to_value
from arcagi.seed.prims import task_consts
from arcagi.seed.types import INPUT, show

ROOT = Path(__file__).resolve().parents[3]
ARCBATCH = ROOT / "native" / "bin" / "arcbatch"
INFO_MIN = 8.0
SUB_BUDGET = 200_000
MAX_THREADS = 8


def pick_arm(route_ops: list[dict], stall_state: str) -> str | None:
    """Arm of the highest-priority live route row for this stall state."""
    state = "saturate" if stall_state == "stop" else stall_state
    rows = [o for o in route_ops if o.get("kind") == "route"
            and o.get("status") == "live"
            and o["payload"].get("when_stall") == state]
    if not rows:
        return None
    rows.sort(key=lambda o: (-o["payload"].get("priority", 0), o["id"]))
    return rows[0]["payload"]["arm"]


def _cells(v):
    if isinstance(v, (tuple, list)):
        for x in v:
            yield from _cells(x)
    else:
        yield v


def info_bits(outs) -> float:
    """Non-background scalar cells of the outputs x log2(10)."""
    bits = 0.0
    for o in outs:
        cs = list(_cells(o))
        if not cs:
            continue
        bg = Counter(cs).most_common(1)[0][0]
        bits += sum(c != bg for c in cs) * math.log2(10)
    return round(bits, 3)


def _plain(v):
    return [_plain(x) for x in v] if isinstance(v, tuple) else v


def _type_of(v, fallback):
    """Ground type string of a seed value (int / list nesting)."""
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, tuple) and v:
        return f"list[{_type_of(v[0], fallback)}]"
    return show(fallback)


def sub_row(sid: str, xs, outs, in_t: str, out_t: str, consts=(),
            lib: str | None = None, budget: int = SUB_BUDGET,
            extra=()) -> dict:
    """One arcbatch seed-sub job line (format of native/tools/seed_record.py)."""
    return {"id": sid, "lib": lib, "budget": budget,
            "examples": [[_plain(x), _plain(y)] for x, y in zip(xs, outs)],
            "in_type": in_t, "out_type": out_t, "extra": list(extra),
            "sub": False, "consts": list(consts), "lam_depth": 2,
            "lam_body_max": 4, "order": {}, "cond_limit": None, "near": True}


def vsplit_witness(root: Path, tasks: list, epoch: int) -> list[dict]:
    """Backward subgoals of unsolved tasks -> nodes/route/_witness.jsonl.

    ``tasks``: objects or dicts with ``task_id`` / ``id`` and ``train``
    (list of (input, output) grids or {"input","output"} dicts).
    Returns the seed-sub job rows (with the witness id as job id).
    """
    node = Path(root) / "nodes" / "route"
    jobs = []
    for t in tasks:
        tid, train = _task(t)
        xs = tuple(to_value(i) for i, _ in train)
        outs = tuple(to_value(o) for _, o in train)
        consts = list(task_consts((*xs, *outs)))
        for name, sx, sy, (ti, to), extra, _build in wt.witness_splits(
                xs, outs, (INPUT, INPUT)):
            if extra:  # positional extra leaves: not expressible here yet
                continue
            bits = info_bits(sy)
            if bits < INFO_MIN:
                continue
            wid = f"wv-{epoch}-{tid}-{name}"
            fm.append_witness(node, {
                "id": wid, "task": tid, "pair": None, "dir": "bwd",
                "src": f"decomp:{name}",
                "examples": [[_plain(x), _plain(y)] for x, y in zip(sx, sy)],
                "props": {"n": len(sx)}, "info_bits": bits, "status": "open",
                "fit": None, "epoch": epoch})
            jobs.append(sub_row(wid, sx, sy, _type_of(sx[0], ti),
                                _type_of(sy[0], to), consts))
    return jobs


def _task(t):
    if isinstance(t, dict):
        tid = t.get("task_id") or t.get("id")
        train = t["train"]
    else:
        tid = getattr(t, "task_id", None) or getattr(t, "id")
        train = t.train
    train = [(p["input"], p["output"]) if isinstance(p, dict) else tuple(p)
             for p in train]
    return tid, train


def run_subs(jobs: list[dict], work: Path, threads: int = 6) -> dict[str, dict]:
    """Run arcbatch --mode seed-sub on ``jobs``; {id: result line}."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    if not jobs:
        return {}
    inp, out = work / "subs.jsonl", work / "subs.out.jsonl"
    inp.write_text("".join(json.dumps(j) + "\n" for j in jobs))
    subprocess.run([str(ARCBATCH), "--mode", "seed-sub", "--subproblems",
                    str(inp), "--threads", str(min(threads, MAX_THREADS)),
                    "--out", str(out)], check=True, capture_output=True)
    res = {}
    for ln in out.read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            res[r["id"]] = r
    return res


def solve_subs(root: Path, jobs: list[dict], work: Path, epoch: int) -> dict:
    """Solve vsplit subgoals; append ``fitted`` rows; summary dict."""
    res = run_subs(jobs, work)
    node = Path(root) / "nodes" / "route"
    fitted = 0
    for j in jobs:
        r = res.get(j["id"], {})
        prog = r.get("program") or (r.get("cond") or {}).get("program")
        if prog is None:
            continue
        fitted += 1
        fm.append_witness(node, {
            "id": j["id"], "task": j["id"].split("-")[2], "pair": None,
            "dir": "bwd", "src": "decomp:fit", "examples": j["examples"],
            "props": {}, "info_bits": info_bits(e[1] for e in j["examples"]),
            "status": "fitted", "fit": {"program": prog, "nodes": r.get("nodes")},
            "epoch": epoch})
    return {"subgoals": len(jobs), "fitted": fitted,
            "nodes": sum(r.get("nodes", 0) for r in res.values())}


__all__ = ["pick_arm", "info_bits", "sub_row", "vsplit_witness", "run_subs",
           "solve_subs", "to_json"]
