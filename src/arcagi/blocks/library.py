"""Tiny library learning: frequent fixed-parameter fragments become macros.

Run: ``uv run python -m arcagi.blocks.library --traces T.jsonl [T2.jsonl ...]``.

From every train-passing program (``kind=program``) take each contiguous 2-3
step window without learner steps. A window seen in at least ``--min-tasks``
distinct tasks becomes ``aos/blocks/<macro>/`` (``kind=macro``,
``program.json``). A macro is ``covered`` when every task it appears in already
has a program without it that is cheaper than the best program using it (with
the macro counted as one step); otherwise ``live``. Covered macros stay on disk.
"""

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from arcagi.dsl.program import Program, cost

from . import LEARNER_NAMES, default_blocks_root, read_json, write_json
from .sync import write_block

type Fragment = tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class Macro:
    name: str
    fragment: Fragment
    tasks: tuple[str, ...]
    status: str


def task_programs(records: Iterable[dict]) -> dict[str, list[Program]]:
    """task_id -> distinct train-passing programs from trace records."""
    found: dict[str, list[Program]] = defaultdict(list)
    for record in records:
        trace = record.get("trace") or {}
        for attempt in trace.get("attempts", []):
            if attempt.get("kind") != "program" or "program" not in attempt:
                continue
            steps = json.loads(attempt["program"])
            program = tuple(tuple(_freeze(p) for p in step) for step in steps)
            if program not in found[record["task_id"]]:
                found[record["task_id"]].append(program)
    return dict(found)


def _freeze(value: object) -> object:
    return tuple(_freeze(v) for v in value) if isinstance(value, list) else value


def _thaw(value: object) -> object:
    return [_thaw(v) for v in value] if isinstance(value, tuple) else value


def fragments(program: Program, sizes: Iterable[int] = (2, 3)) -> set[Fragment]:
    out = set()
    for size in sizes:
        for start in range(len(program) - size + 1):
            window = program[start : start + size]
            if not any(step[0] in LEARNER_NAMES for step in window):
                out.add(window)
    return out


def _contains(program: Program, fragment: Fragment) -> int:
    """Start index of ``fragment`` in ``program`` or -1."""
    size = len(fragment)
    for start in range(len(program) - size + 1):
        if program[start : start + size] == fragment:
            return start
    return -1


def _macro_cost(program: Program, fragment: Fragment) -> float:
    start = _contains(program, fragment)
    rest = program[:start] + program[start + len(fragment) :]
    return cost(rest) + 1


def macro_name(fragment: Fragment) -> str:
    text = json.dumps(_thaw(fragment), separators=(",", ":"))
    digest = hashlib.sha1(text.encode()).hexdigest()[:6]
    return "m_" + "__".join(str(step[0]) for step in fragment) + "_" + digest


def is_covered(fragment: Fragment, programs: dict[str, list[Program]]) -> bool:
    for task_id, progs in programs.items():
        using = [p for p in progs if _contains(p, fragment) >= 0]
        if not using:
            continue
        best_with = min(_macro_cost(p, fragment) for p in using)
        without = [cost(p) for p in progs if _contains(p, fragment) < 0]
        if not without or min(without) >= best_with:
            return False
    return True


def find_macros(programs: dict[str, list[Program]], min_tasks: int = 3) -> list[Macro]:
    seen: dict[Fragment, set[str]] = defaultdict(set)
    for task_id, progs in programs.items():
        for program in progs:
            for fragment in fragments(program):
                seen[fragment].add(task_id)
    macros = []
    for fragment, tasks in sorted(
        seen.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))
    ):
        if len(tasks) < min_tasks:
            continue
        status = "covered" if is_covered(fragment, programs) else "live"
        macros.append(
            Macro(macro_name(fragment), fragment, tuple(sorted(tasks)), status)
        )
    return macros


def write_macros(macros: list[Macro], root: Path, sources: list[str]) -> None:
    for macro in macros:
        folder = root / macro.name
        old = read_json(folder / "_metainfo.json", {}) or {}
        status = "retired" if old.get("status") == "retired" else macro.status
        steps = [_thaw(step) for step in macro.fragment]
        doc = "Macro: " + " -> ".join(json.dumps(s) for s in steps)
        write_block(
            folder,
            {
                "name": macro.name,
                "kind": "macro",
                "doc": doc,
                "params": [],
                "source_tasks": list(macro.tasks),
                "source_traces": sources,
            },
        )
        meta = read_json(folder / "_metainfo.json", {})
        meta["status"] = status  # type: ignore[index]
        write_json(folder / "_metainfo.json", meta)
        write_json(folder / "program.json", steps)


def _read_jsonl(paths: list[Path]) -> Iterable[dict]:
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract macro blocks from traces.")
    parser.add_argument("--traces", type=Path, nargs="+", required=True)
    parser.add_argument("--min-tasks", type=int, default=3)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    programs = task_programs(_read_jsonl(args.traces))
    macros = find_macros(programs, args.min_tasks)
    if not args.dry_run:
        write_macros(
            macros, args.root or default_blocks_root(), [str(p) for p in args.traces]
        )
    print(f"{len(programs)} tasks with programs; {len(macros)} macros")
    for macro in macros:
        print(f"  {macro.name} [{macro.status}] tasks={len(macro.tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
