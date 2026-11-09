"""Can the empty tree fit a wax step? (``arcbatch --mode seed-sub``.)

Same job shape as ``hammer.foundry.ingest``: one seed-sub job per segment
``(S_i, S_{i+1})`` over all pairs, budget 200k nodes, the task constants of
the segment, optionally the hammer's live library. A step is fittable when a
program comes back and re-checks on every pair with the Python interpreter.
Results are cached by segment content (many samples repeat steps).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arcagi.hammer import route as rt
from arcagi.seed import interp
from arcagi.seed.library import Library
from arcagi.seed.prims import task_consts

BUDGET = 200_000


def _type(g) -> str:
    return rt._type_of(interp.to_value(g), None)


def seg_key(pairs: list) -> str:
    return hashlib.sha1(json.dumps(pairs, separators=(",", ":")).encode()).hexdigest()[
        :16
    ]


class Fitter:
    def __init__(
        self,
        work: Path,
        lib_path: Path | None = None,
        threads: int = 6,
        cache_path: Path | None = None,
    ):
        self.work = Path(work)
        self.lib_path = Path(lib_path) if lib_path else None
        self.lib = Library.load(self.lib_path) if self.lib_path else None
        self.threads = threads
        self.cache: dict[str, dict] = {}
        self.cache_path = Path(cache_path) if cache_path else None
        if self.cache_path and self.cache_path.exists():
            for ln in self.cache_path.read_text().splitlines():
                if ln.strip():
                    r = json.loads(ln)
                    self.cache[r["key"]] = r
        self.nodes = 0

    def _check(self, prog, pairs) -> bool:
        try:
            p = interp.from_json(prog)
            return all(
                interp.run(p, interp.to_value(x), self.lib) == interp.to_value(y)
                for x, y in pairs
            )
        except Exception:
            return False

    def fit(self, segments: list[list]) -> list[dict]:
        """``segments[i]`` = [(x, y) per pair] -> [{"key","program","nodes"}]."""
        keys = [seg_key(s) for s in segments]
        jobs, todo = [], {}
        for k, s in zip(keys, segments):
            if k in self.cache or k in todo:
                continue
            xs = [interp.to_value(x) for x, _ in s]
            ys = [interp.to_value(y) for _, y in s]
            jobs.append(
                rt.sub_row(
                    k,
                    xs,
                    ys,
                    _type(s[0][0]),
                    _type(s[0][1]),
                    list(task_consts((*xs, *ys))),
                    str(self.lib_path) if self.lib_path else None,
                    BUDGET,
                )
            )
            todo[k] = s
        if jobs:
            res = rt.run_subs(jobs, self.work, self.threads)
            new = []
            for k, s in todo.items():
                r = res.get(k, {})
                prog = r.get("program") or (r.get("cond") or {}).get("program")
                if prog is not None and not self._check(prog, s):
                    prog = None
                self.nodes += r.get("nodes", 0)
                rec = {
                    "key": k,
                    "program": prog,
                    "nodes": r.get("nodes"),
                    "size": interp.size(interp.from_json(prog)) if prog else None,
                }
                self.cache[k] = rec
                new.append(rec)
            if self.cache_path:
                with self.cache_path.open("a") as f:
                    for rec in new:
                        f.write(json.dumps(rec) + "\n")
        return [self.cache[k] for k in keys]
