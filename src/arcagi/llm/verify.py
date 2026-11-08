"""Check an LLM rule on a task: train pass rate (feedback) and test exact (score).

A rule is a four-kind block dict. ``transform`` bodies are ``arcagi.dsl.program``
step lists; an ``extract`` body with a grid property runs as ``crop_extract``;
``pred`` / ``formula`` bodies cannot produce a grid alone and are only
syntax-checked (they count as components of a transform that uses them).
"""

import json
import signal
from collections.abc import Iterator
from contextlib import contextmanager

from . import tasks as tk

KINDS = ("pred", "extract", "formula", "transform")
SHELL = {
    "pred": ("object", "bool"),
    "extract": ("grid", "json"),
    "formula": ("features", "int"),
    "transform": ("grid", "grid"),
}
STEP_SECONDS = 5


@contextmanager
def _limit(seconds: int) -> Iterator[None]:
    def _raise(_sig, _frm):
        raise TimeoutError(f"rule ran over {seconds}s")

    old = signal.signal(signal.SIGALRM, _raise)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def normalize(rule: object) -> dict:
    """Fill the shell (``in`` / ``out``) and reject unknown kinds."""
    if not isinstance(rule, dict) or rule.get("kind") not in KINDS:
        raise ValueError("rule must be a dict with kind pred|extract|formula|transform")
    kind = rule["kind"]
    inp, out = SHELL[kind]
    if kind == "extract" and isinstance(rule.get("body"), list):
        out = "grid" if rule["body"][:1] in (["subgrid"], ["object"]) else out
    return {"kind": kind, "in": inp, "out": out, "body": rule.get("body")}


def program_of(rule: dict) -> list | None:
    """The grid -> grid program a rule stands for, or None (pred / formula)."""
    kind, body = rule["kind"], rule["body"]
    if kind == "transform":
        if not isinstance(body, list) or not all(
            isinstance(s, list) and s and isinstance(s[0], str) for s in body
        ):
            raise ValueError("transform body must be a list of [name, *params] steps")
        return body
    if kind == "extract":
        from arcagi.dsl import extract as ex

        if not ex.validate(body):
            raise ValueError("bad extract body")
        return [["crop_extract", body]] if rule["out"] == "grid" else None
    if kind == "pred":
        from arcagi.dsl import predicates as pr

        if not pr.validate(body):
            raise ValueError("bad predicate body")
    else:
        from arcagi.dsl import formula as fm

        if not fm.validate(body):
            raise ValueError("bad formula body")
    return None


def run(program: list, grid: tk.Grid) -> tk.Grid:
    from arcagi.dsl import program as pg

    steps = tuple(tuple(s) for s in program)  # params stay JSON lists
    tgrid = tuple(tuple(r) for r in grid)
    with _limit(STEP_SECONDS):
        result = pg.run(steps, tgrid)  # type: ignore[arg-type]
    return [list(r) for r in result]


def background(task: dict) -> int | None:
    """Task background as the search sees it (all train inputs and outputs)."""
    from arcagi.dsl import background as bgc

    grids = [tuple(tuple(r) for r in g) for pair in tk.pairs(task) for g in pair]
    return bgc.task_background(grids)


def _try(
    program: list, grid: tk.Grid, bg: int | None = None
) -> tuple[tk.Grid | None, str | None]:
    from arcagi.dsl import background as bgc

    try:
        with bgc.task_context(bg):
            return run(program, grid), None
    except Exception as err:  # noqa: BLE001 - any rule failure is data
        return None, f"{type(err).__name__}: {err}"[:300]


def check(task_id: str, split: str, rule: object) -> dict:
    """Train-only feedback: per pair ok / error / predicted shape. No test data."""
    try:
        rule = normalize(rule)
        program = program_of(rule)
    except (ValueError, TypeError, KeyError, IndexError) as err:
        return {
            "rule": rule,
            "valid": False,
            "error": str(err)[:300],
            "train_pass": 0.0,
        }
    task = tk.load(task_id, split)
    if program is None:
        return {"rule": rule, "valid": True, "program": None, "train_pass": None}
    rows, bg = [], background(task)
    for inp, want in tk.pairs(task):
        got, err = _try(program, inp, bg)
        row = {"ok": got == want, "error": err}
        if got is not None and got != want:
            row["got"] = got
            same = len(got) == len(want) and len(got[0]) == len(want[0])
            row["wrong_cells"] = (
                sum(a != b for ra, rb in zip(got, want) for a, b in zip(ra, rb))
                if same
                else None
            )
        rows.append(row)
    passed = sum(r["ok"] for r in rows)
    return {
        "rule": rule,
        "valid": True,
        "program": program,
        "train_pass": passed / len(rows),
        "train_all": passed == len(rows),
        "pairs": rows,
    }


def score(task_id: str, split: str, rule: object) -> dict:
    """``check`` plus test exact (reads test outputs; grader side only)."""
    res = check(task_id, split, rule)
    res.pop("pairs", None)
    if not res.get("program"):
        res["test_exact"] = None
        return res
    task = tk.load(task_id, split)
    bg = background(task)
    hits = [
        _try(res["program"], t["input"], bg)[0] == t.get("output") for t in task["test"]
    ]
    res["test_exact"] = all(hits)
    res["test_hits"] = sum(hits)
    return res


def dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))
