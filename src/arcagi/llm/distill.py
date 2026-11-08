"""Distill train-passing LLM solutions into reusable blocks and test the reuse.

Pipeline (training only; evaluation solutions never become blocks):

1. ``solutions()`` gathers every train-passing training program from the
   traces; ``pieces()`` cuts each into contiguous fragments (a fragment of two
   or more steps, or one step with parameters) - the sub-rules a search can
   reuse as a single step - plus the non-transform candidates already split
   out by ``candidates.components``.
2. ``stage(out)`` copies ``aos/blocks`` to ``<out>/base`` (baseline) and to
   ``<out>/llm`` with every piece added as a live block named ``*_llm_<hash>``
   (``m_llm_`` for macros). The real search then runs on training twice, once
   per blocks root (``ARCAGI_BLOCKS``), outside this module.
3. ``reuse(out, base_report, llm_report)`` reads both reports: a piece is
   *reused* on a task when the llm run solves the task's train pairs with a
   selected program naming the piece. For each use it measures the selected
   program on the task's synthetic pairs (``data_synth``, re-arc, after the
   original pairs) - a block that only memorized its origin fails there.
   Results go to ``<out>/reuse.json`` and to each candidate's metainfo.

Verdict ``reused`` = used in a solution of at least one training task outside
the piece's origin and synthetic majority on at least 2/3 of its use tasks
(the r06 shadow gate (b)); ``origin_only`` / ``memorized`` / ``unused`` else.
"""

import hashlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

from . import LLM_ROOT, REPO_ROOT
from . import candidates as cd
from . import trace as tr
from . import verify as vf

BLOCKS = REPO_ROOT / "aos" / "blocks"
SYNTH = REPO_ROOT / "data_synth" / "training"
PREFIX = {"transform": "m_llm_", "pred": "pred_llm_", "extract": "extract_llm_"}
PREFIX["formula"] = "formula_llm_"
# Fitted tables are search terminals, never macro steps.
LEARNED = frozenset({"colormap", "object_colormap", "local_rule", "x_vrule"})


def solutions() -> dict[str, list[list]]:
    """Training task -> distinct train-passing programs from all LLM runs."""
    found: dict[str, list[list]] = {}
    for path in sorted((LLM_ROOT / "traces").glob("*-training.jsonl")):
        for row in tr.read(path):
            if not row.get("train_all") or not row.get("rule"):
                continue
            program = vf.program_of(vf.normalize(row["rule"]))
            progs = found.setdefault(row["task"], [])
            if program and program not in progs:
                progs.append(program)
    return found


def fragments(program: list) -> Iterator[list]:
    """Contiguous step runs worth a block: >= 2 steps, or 1 step with params."""
    n = len(program)
    for size in range(1, n + 1):
        for start in range(n - size + 1):
            frag = program[start : start + size]
            if size == 1 and len(frag[0]) == 1:
                continue  # a bare primitive is already in the registry
            if any(s[0] in LEARNED for s in frag):
                continue  # fitted tables are search terminals, not macro steps
            yield frag


def pieces() -> dict[str, dict]:
    """Block name -> {kind, body, origin}; origin = tasks whose solution has it."""
    out: dict[str, dict] = {}

    def add(kind: str, body: object, task: str) -> None:
        name = PREFIX[kind] + cd.digest(kind, body)
        entry = out.setdefault(name, {"kind": kind, "body": body, "origin": []})
        if task not in entry["origin"]:
            entry["origin"].append(task)

    for task, progs in sorted(solutions().items()):
        for program in progs:
            for frag in fragments(program):
                add("transform", frag, task)
            for kind, body in cd.components(program):
                add(kind, body, task)
    return out


def _write_block(folder: Path, name: str, piece: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    kind, body = piece["kind"], piece["body"]
    meta = {
        "name": name,
        "kind": "macro" if kind == "transform" else kind,
        "doc": "LLM-distilled " + kind + " " + json.dumps(body)[:200],
        "params": [],
        "cost": 1,
        "status": "live",
        "source": "llm",
        "origin": piece["origin"],
    }
    (folder / "_metainfo.json").write_text(json.dumps(meta, indent=2) + "\n")
    if kind == "transform":
        (folder / "program.json").write_text(json.dumps(body) + "\n")
    else:
        (folder / "_rule.json").write_text(
            json.dumps(cd.shell(kind, body), indent=2) + "\n"
        )


def _existing_bodies() -> set[str]:
    """Bodies of blocks already in ``aos/blocks`` (skip re-adding them)."""
    seen = set()
    for folder in BLOCKS.iterdir():
        for fname in ("program.json", "_rule.json"):
            path = folder / fname
            if path.exists():
                data = json.loads(path.read_text())
                body = data.get("body") if isinstance(data, dict) else data
                seen.add(json.dumps(body, sort_keys=True))
    return seen


def stage(out: Path, kinds: tuple[str, ...] = tuple(PREFIX)) -> dict[str, dict]:
    """Write ``<out>/base`` and ``<out>/llm`` blocks roots; returns staged pieces."""
    have = _existing_bodies()
    staged = {
        name: p
        for name, p in pieces().items()
        if p["kind"] in kinds and json.dumps(p["body"], sort_keys=True) not in have
    }
    for sub in ("base", "llm"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
        shutil.copytree(BLOCKS, out / sub)
    for name, piece in staged.items():
        _write_block(out / "llm" / name, name, piece)
    (out / "staged.json").write_text(json.dumps(staged, indent=1) + "\n")
    return staged


def synth_rate(task_id: str, program: list) -> float | None:
    """Share of the task's synthetic pairs the program reproduces (None: no set)."""
    path = SYNTH / f"{task_id}.json"
    manifest = SYNTH.parent / "manifest.json"
    if not path.exists() or not manifest.exists():
        return None
    task = json.loads(path.read_text())
    info = json.loads(manifest.read_text())
    info = info.get("tasks", info).get(task_id, {})
    n0 = int(info.get("n_original", 0))
    synth = task["train"][n0:]
    if not synth:
        return None
    bg = vf.background({"train": synth})
    ok = sum(vf._try(program, p["input"], bg)[0] == p["output"] for p in synth)
    return ok / len(synth)


def _selected(trace: dict | None) -> list | None:
    for att in (trace or {}).get("attempts", []):
        if att.get("selected") and att.get("program"):
            return json.loads(att["program"])
    return None


def _solved(report: Path) -> dict[str, dict]:
    data = json.loads(report.read_text())
    out = {}
    for t in data["tasks"]:
        prog = _selected(t.get("trace"))
        out[t["task_id"]] = {"correct": t["correct"], "program": prog}
    return out


def _names(node: object) -> Iterator[str]:
    if isinstance(node, str):
        if "_llm_" in node:
            yield node
    elif isinstance(node, (list, dict)):
        for kid in node.values() if isinstance(node, dict) else node:
            yield from _names(kid)


def reuse(out: Path, base_report: Path, llm_report: Path) -> dict:
    """Per staged piece: tasks whose search solution uses it, with synth rates.

    Run with ``ARCAGI_BLOCKS=<out>/llm`` so programs naming the pieces resolve.
    """
    staged = json.loads((out / "staged.json").read_text())
    base, llm = _solved(base_report), _solved(llm_report)
    used: dict[str, list[dict]] = {name: [] for name in staged}
    for task, row in sorted(llm.items()):
        prog = row["program"]
        if not prog:
            continue
        names = sorted(set(_names(prog)))
        if not names:
            continue
        rate = synth_rate(task, prog)
        for name in names:
            if name in used:
                used[name].append(
                    {
                        "task": task,
                        "correct": row["correct"],
                        "base_correct": base.get(task, {}).get("correct", False),
                        "synth": rate,
                        "program": prog,
                    }
                )
    rows = {}
    for name, piece in staged.items():
        uses = used[name]
        outside = [u for u in uses if u["task"] not in piece["origin"]]
        passed = [u for u in uses if (u["synth"] or 0) > 0.5]
        if not uses:
            verdict = "unused"
        elif not outside:
            verdict = "origin_only"
        elif 3 * len(passed) < 2 * len(uses):
            verdict = "memorized"
        else:
            verdict = "reused"
        rows[name] = piece | {"uses": uses, "verdict": verdict}
    regress = sorted(
        t for t in base if base[t]["correct"] and not llm.get(t, {}).get("correct")
    )
    gained = sorted(
        t for t in llm if llm[t]["correct"] and not base.get(t, {}).get("correct")
    )
    ptw = {
        k: sum(1 for r in rep.values() if r["program"] and not r["correct"])
        for k, rep in (("base", base), ("llm", llm))
    }
    result = {
        "solved": {
            k: sum(r["correct"] for r in v.values())
            for k, v in (("base", base), ("llm", llm))
        },
        "gained": gained,
        "regressed": regress,
        "pass_train_wrong": ptw,
        "pieces": rows,
    }
    (out / "reuse.json").write_text(json.dumps(result, indent=1) + "\n")
    return result


def record(result: dict, model: str = "claude-opus-5-5") -> list[str]:
    """Write pieces that were used (any verdict but ``unused``) as candidates."""
    made = []
    for name, row in result["pieces"].items():
        if row["verdict"] == "unused":
            continue
        folder = None
        for task in row["origin"]:
            folder = cd.write(
                row["kind"],
                row["body"],
                task_id=task,
                split="training",
                model=model,
                role="fragment",
            )
        assert folder is not None
        meta_path = folder / "_metainfo.json"
        meta = json.loads(meta_path.read_text())
        meta["distill"] = {
            "staged_as": name,
            "verdict": row["verdict"],
            "uses": [
                {k: u[k] for k in ("task", "correct", "base_correct", "synth")}
                for u in row["uses"]
            ],
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        made.append(folder.name)
    return made


def fingerprint(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:10]
