"""Run model-written ``solve(grid)`` code in a throwaway subprocess.

The code runs under ``python3 -I`` with CPU / memory / file-size limits and a
wall timeout, in a scratch directory, and gets the train inputs on stdin.
It returns the checkpoint trajectory: per pair the list of ``(tag, grid)``
recorded by ``step`` plus the returned grid. Nothing from the code is kept.
"""

from __future__ import annotations

import json
import re
import resource
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = r"""
import json, sys
from functools import reduce as _reduce

class _P:
    add = staticmethod(lambda a, b: a + b)
    sub = staticmethod(lambda a, b: a - b)
    mul = staticmethod(lambda a, b: a * b)
    neg = staticmethod(lambda a: -a)
    mod = staticmethod(lambda a, b: a % b)
    max = staticmethod(max)
    min = staticmethod(min)
    eq = staticmethod(lambda a, b: a == b)
    lt = staticmethod(lambda a, b: a < b)
    and_ = staticmethod(lambda a, b: a and b)
    or_ = staticmethod(lambda a, b: a or b)
    not_ = staticmethod(lambda a: not a)
    if_ = staticmethod(lambda c, a, b: a if c else b)
    len = staticmethod(len)
    nth = staticmethod(lambda xs, i: xs[i])
    head = staticmethod(lambda xs: xs[0])
    last = staticmethod(lambda xs: xs[-1])
    take = staticmethod(lambda n, xs: list(xs[:max(n, 0)]))
    drop = staticmethod(lambda n, xs: list(xs[max(n, 0):]))
    reverse = staticmethod(lambda xs: list(xs)[::-1])
    cons = staticmethod(lambda x, xs: [x] + list(xs))
    append = staticmethod(lambda xs, ys: list(xs) + list(ys))
    concat = staticmethod(lambda xss: [x for xs in xss for x in xs])
    range = staticmethod(lambda n: list(range(max(n, 0))))
    repeat = staticmethod(lambda n, x: [x] * max(n, 0))
    count = staticmethod(lambda x, xs: list(xs).count(x))
    sort = staticmethod(lambda xs: sorted(xs))
    map = staticmethod(lambda f, xs: [f(x) for x in xs])
    filter = staticmethod(lambda f, xs: [x for x in xs if f(x)])
    zipwith = staticmethod(lambda f, xs, ys: [f(a, b) for a, b in zip(xs, ys)])
    fold = staticmethod(lambda f, z, xs: _reduce(f, xs, z))
    transpose = staticmethod(lambda xss: [list(c) for c in zip(*xss)])
P = _P()

def _norm(g):
    return [[int(c) for c in row] for row in g]

_TRACE = []
def step(tag, grid):
    _TRACE.append([str(tag), _norm(grid)])
    return grid

_req = json.loads(sys.stdin.read())
_ns = {"step": step, "P": P, "__name__": "wax"}
_out = []
try:
    exec(compile(_req["code"], "wax", "exec"), _ns)
    for _x in _req["inputs"]:
        _TRACE.clear()
        try:
            _r = _norm(_ns["solve"]([list(r) for r in _x]))
            _out.append({"trace": list(_TRACE), "ret": _r})
        except Exception as e:
            _out.append({"trace": list(_TRACE), "error": type(e).__name__ + ": " + str(e)[:200]})
except Exception as e:
    _out = {"error": type(e).__name__ + ": " + str(e)[:200]}
sys.stdout.write(json.dumps(_out))
"""

FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def extract_code(text: str) -> str | None:
    """The last fenced block that defines ``solve`` (or the bare text)."""
    blocks = [b for b in FENCE.findall(text or "") if "def solve" in b]
    if blocks:
        return blocks[-1]
    if "def solve" in (text or ""):
        return text[text.index("def solve") :]
    return None


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))


def run_code(code: str, inputs: list, timeout: float = 15.0) -> dict | list:
    """Per-pair ``{"trace", "ret"}`` (or ``{"error"}``) list, or ``{"error"}``."""
    with tempfile.TemporaryDirectory(prefix="wax-") as d:
        h = Path(d) / "harness.py"
        h.write_text(HARNESS)
        try:
            p = subprocess.run(
                [sys.executable, "-I", str(h)],
                cwd=d,
                input=json.dumps({"code": code, "inputs": inputs}),
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=_limits,
            )
        except subprocess.TimeoutExpired:
            return {"error": "timeout"}
        try:
            return json.loads(p.stdout)
        except Exception:
            return {"error": f"bad output rc={p.returncode} {p.stderr[-200:]}"}


def _grid_ok(g) -> bool:
    return (
        isinstance(g, list)
        and 0 < len(g) <= 30
        and all(isinstance(r, list) and 0 < len(r) <= 30 for r in g)
        and len({len(r) for r in g}) == 1
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
    )


def trajectory(task: dict, run: dict | list) -> dict:
    """Aligned states ``states[p] = [S_0..S_k]`` and tags, or a failure.

    The returned grid is appended as step ``_return`` when it differs from the
    last checkpoint. Steps that change no pair are dropped (no-ops). All pairs
    must record the same tag sequence (1..8 steps after dropping no-ops).
    """
    if isinstance(run, dict):
        return {"status": "error", "error": run.get("error")}
    pairs = task["train"]
    if len(run) != len(pairs):
        return {"status": "error", "error": "pair count"}
    tags_all, states = [], []
    for p, r in zip(pairs, run):
        if "error" in r:
            return {"status": "error", "error": r["error"]}
        tr = [(t, g) for t, g in r["trace"]]
        if not tr or tr[-1][1] != r["ret"]:
            tr.append(("_return", r["ret"]))
        if not all(_grid_ok(g) for _, g in tr):
            return {"status": "badgrid"}
        tags_all.append([t for t, _ in tr])
        states.append([p["input"]] + [g for _, g in tr])
    if any(t != tags_all[0] for t in tags_all):
        return {"status": "unaligned", "n_steps": [len(t) for t in tags_all]}
    # Collapse no-op steps and loops: a step whose result equals an earlier
    # state on every pair cuts the trajectory back to that state.
    seq = [(None, [st[0] for st in states])]
    for i, tag in enumerate(tags_all[0]):
        cur = [st[i + 1] for st in states]
        back = next((j for j, (_, s) in enumerate(seq) if s == cur), None)
        if back is None:
            seq.append((tag, cur))
        else:
            del seq[back + 1 :]
    tags = [t for t, _ in seq[1:]]
    states = [[s[p] for _, s in seq] for p in range(len(pairs))]
    if not 1 <= len(tags) <= 8:
        return {"status": "steps", "n": len(tags)}
    verified = all(st[-1] == p["output"] for st, p in zip(states, pairs))
    return {"status": "ok", "tags": tags, "states": states, "verified": verified}
