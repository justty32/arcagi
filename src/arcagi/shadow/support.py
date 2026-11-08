"""Training support of blocks with the generators' own judgement, and data views.

Adapted from ``scripts/synth_overfit.py`` (S5): formula via
``gen_formula.problems`` + ``formula.holds``, pred via
``gen_predicates.segments`` + ``Segment.mask``, grid extract via
``gen_extract.score_candidates``, object extract via ``objrule.gen.score``;
macro = reproduces every train pair under the task background.
"""

import json
import signal
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from arcagi.tasks import Task, load_tasks

from . import CHUNK

STEP_SECONDS = 5


def views(synth_root: Path, chunk: int = CHUNK) -> tuple[list[Task], dict]:
    """(original training tasks, task id -> list of chunk tasks) from data_synth.

    ``train[:n_original]`` are the original pairs; the synthetic rest is cut
    into chunks of ``chunk`` pairs, each a task the size of a real one.
    """
    manifest_path = synth_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"{manifest_path} missing; regenerate with "
            "`nice -n 19 .venv/bin/python scripts/synth_generate.py --workers 6`"
        )
    manifest = json.loads(manifest_path.read_text())
    full = {t.task_id: t for t in load_tasks(synth_root / "training")}
    orig, chunks = [], defaultdict(list)
    for task_id, entry in sorted(manifest["tasks"].items()):
        task, n = full[task_id], entry["n_original"]
        orig.append(Task(task_id, task.train[:n], task.test))
        pairs = task.train[n:]
        for k in range(len(pairs) // chunk):
            part = pairs[k * chunk : (k + 1) * chunk]
            chunks[task_id].append(Task(task_id, part, task.test))
    return orig, dict(chunks)


@contextmanager
def _limit(seconds: int) -> Iterator[None]:
    def _raise(_sig, _frm):
        raise TimeoutError(f"program ran over {seconds}s")

    old = signal.signal(signal.SIGALRM, _raise)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def reproduces(steps: Sequence, task: Task) -> bool:
    """Does the program map every train input to its output?"""
    from arcagi.dsl import background as bgc
    from arcagi.dsl import program as pg

    pairs = [(e.input, e.output) for e in task.train]
    if not pairs or any(o is None for _, o in pairs):
        return False
    program = tuple(tuple(s) for s in steps)
    bg = bgc.task_background([grid for pair in pairs for grid in pair])
    try:
        with bgc.task_context(bg), _limit(STEP_SECONDS):
            return all(pg.run(program, i) == o for i, o in pairs)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 - any program failure is a miss
        return False


def support(blocks: Sequence[dict], tasks: Sequence[Task]) -> dict[str, set[str]]:
    """Block name -> ids of ``tasks`` it supports (generator judgement)."""
    from arcagi.blocks import gen_extract as gx
    from arcagi.blocks import gen_formula as gf
    from arcagi.blocks import gen_predicates as gp
    from arcagi.dsl import formula as fm
    from arcagi.objrule import gen as objgen

    out: dict[str, set[str]] = {b["name"]: set() for b in blocks}
    by_kind = defaultdict(list)
    for b in blocks:
        by_kind[b["kind"]].append(b)
    if by_kind["formula"]:
        extracts: dict = {}
        for b in by_kind["formula"]:
            extracts |= b["rule"].get("extracts", {})
        probs = gf.problems(tasks, extracts)
        for b in by_kind["formula"]:
            body = b["rule"]["body"]
            out[b["name"]] = {p.task for p in probs if fm.holds(body, p.xs, p.ys)}
    if by_kind["pred"]:
        segs = gp.segments(tasks)
        for b in by_kind["pred"]:
            body = b["rule"]["body"]
            out[b["name"]] = {s.task for s in segs if s.mask(body) == s.label}
    extract = by_kind["extract"]
    grid = [b for b in extract if isinstance(b["rule"]["body"], list)]
    obj = [b for b in extract if isinstance(b["rule"]["body"], dict)]
    if grid:
        sels: list = []
        for b in grid:
            if b["rule"]["body"][1] not in sels:
                sels.append(b["rule"]["body"][1])
        found = {json.dumps(c.body): c.tasks for c in gx.score_candidates(tasks, sels)}
        for b in grid:
            out[b["name"]] = set(found.get(json.dumps(b["rule"]["body"]), ()))
    if obj:
        bodies = [_object_body(b["rule"]["body"]) for b in obj]
        for b, (_, ids) in zip(obj, objgen.score(tasks, bodies), strict=True):
            out[b["name"]] = set(ids)
    for b in by_kind["macro"]:
        out[b["name"]] = {t.task_id for t in tasks if reproduces(b["program"], t)}
    return out


def _object_body(body: dict) -> dict:
    """Generated object bodies are bare ``{sel, prop}``; LLM ones carry a scope."""
    from arcagi.dsl import extract as ex

    return ex.unwrap_object(body) if ex.is_object(body) else body


def chunk_rates(
    blocks: Sequence[dict], claims: dict[str, set[str]], chunks: dict
) -> dict[str, dict[str, float]]:
    """Per block, per supported task: share of synthetic chunks still supported."""
    wanted = sorted({t for ids in claims.values() for t in ids})
    n_chunks = max((len(chunks.get(t, [])) for t in wanted), default=0)
    hits: dict[str, dict[str, int]] = {b["name"]: {} for b in blocks}
    for k in range(n_chunks):
        tasks = [chunks[t][k] for t in wanted if len(chunks.get(t, [])) > k]
        found = support(blocks, tasks)
        for name, ids in found.items():
            for t in ids & claims[name]:
                hits[name][t] = hits[name].get(t, 0) + 1
    return {
        b["name"]: {
            t: round(hits[b["name"]].get(t, 0) / max(len(chunks.get(t, [])), 1), 3)
            for t in sorted(claims[b["name"]])
        }
        for b in blocks
    }


__all__ = ["chunk_rates", "reproduces", "support", "views"]
