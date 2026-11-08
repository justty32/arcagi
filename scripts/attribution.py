"""Per-task attribution: who solved each task and which generated blocks it used.

Usage: uv run python scripts/attribution.py <eval report.json> [traces.jsonl]
           [--cpp intercept.csv]

Reads an ``arcagi eval`` report (``tasks[*].correct``/``trace``) and, when
given, the ``--traces`` JSONL (its trace wins over the report's). Writes one
CSV row per task to stdout and summary counts to stderr.

``solver`` is decided from the trace:

- ``search``  : Python BFS program selected (plain ``search:solve``, or the
  native hybrid with ``metadata.source == "python"``);
- ``rewrite`` : Python program whose attempt description starts ``rewrite ``;
- ``native``  : hybrid trace with ``metadata.source == "native"`` and a
  selected program (``origin`` = the attempt's ``data.origin``: ``cpp``,
  ``seed`` or ``prefix_py``);
- ``none``    : no selected program (inputs echoed) or no trace.

``blocks`` lists every string in the selected program starting with one of
``BLOCK_PREFIXES`` (step names and nested parameters alike).

The summary splits the score into Python's own (``search`` + ``rewrite``) and
what native adds. The hybrid never runs C++ on Python-solved tasks, so the
overlap (tasks both sides solve) needs ``--cpp``: the CSV that
``scripts/intercept.py`` writes for those tasks.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

BLOCK_PREFIXES = ("extract_", "formula_", "pred_", "llm_", "m_")
FIELDS = ["task_id", "correct", "solver", "origin", "families", "blocks", "program"]


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _strings(item)


def blocks_in(program: object) -> list[str]:
    """Generated / macro block names inside a program (JSON text or parsed)."""
    if isinstance(program, str):
        try:
            program = json.loads(program)
        except ValueError:
            return []
    found = {s for s in _strings(program) if s.startswith(BLOCK_PREFIXES)}
    return sorted(found)


def family(name: str) -> str:
    return next(p.rstrip("_") for p in BLOCK_PREFIXES if name.startswith(p))


def attribute(task_id: str, correct: bool, trace: dict | None) -> dict[str, str]:
    """One CSV row (see the module docstring)."""
    row = dict.fromkeys(FIELDS, "")
    row.update(task_id=task_id, correct=str(int(bool(correct))), solver="none")
    if not trace or trace.get("selected") is None:
        return row
    chosen = [a for a in trace.get("attempts", []) if a.get("id") == trace["selected"]]
    if not chosen:
        return row
    attempt = chosen[0]
    meta = trace.get("metadata") or {}
    if meta.get("source") == "native":
        row["solver"] = "native"
        row["origin"] = str((attempt.get("data") or {}).get("origin", "cpp"))
    elif str(attempt.get("description", "")).startswith("rewrite "):
        row["solver"] = row["origin"] = "rewrite"
    else:
        row["solver"], row["origin"] = "search", "python"
    names = blocks_in(attempt.get("program"))
    row["blocks"] = "|".join(names)
    row["families"] = "|".join(sorted({family(n) for n in names}))
    row["program"] = str(attempt.get("program") or "")
    return row


def load(report_path: str, traces_path: str | None) -> list[dict[str, str]]:
    report = json.loads(Path(report_path).read_text())
    traces: dict[str, dict | None] = {}
    if traces_path:
        for line in Path(traces_path).read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                traces[record["task_id"]] = record.get("trace")
    rows = []
    for task in report["tasks"]:
        trace = traces.get(task["task_id"], task.get("trace"))
        rows.append(attribute(task["task_id"], task["correct"], trace))
    return rows


def summary(rows: list[dict[str, str]], cpp: dict[str, str] | None = None) -> list[str]:
    solvers = Counter((r["solver"], r["correct"]) for r in rows)
    lines = [f"tasks {len(rows)}, correct {sum(r['correct'] == '1' for r in rows)}"]
    for name in ("search", "rewrite", "native", "none"):
        right, wrong = solvers[(name, "1")], solvers[(name, "0")]
        lines.append(f"{name}: correct {right}, wrong {wrong}")
    python = solvers[("search", "1")] + solvers[("rewrite", "1")]
    lines.append(f"python own score {python}, native adds {solvers[('native', '1')]}")
    if cpp is not None:
        mine = [r for r in rows if r["solver"] in ("search", "rewrite")]
        mine = [r for r in mine if r["task_id"] in cpp]
        both = sum(cpp[r["task_id"]] == "1" for r in mine if r["correct"] == "1")
        caught = sum(cpp[r["task_id"]] == "1" for r in mine if r["correct"] == "0")
        lines.append(
            f"overlap (python right and C++ alone right) {both}; "
            f"interceptions (python wrong, C++ alone right) {caught}; "
            f"python-solved tasks with C++ result {len(mine)}"
        )
    origins = Counter(r["origin"] for r in rows if r["solver"] == "native")
    if origins:
        lines.append("native origins: " + json.dumps(dict(origins)))
    correct = [r for r in rows if r["correct"] == "1"]
    fams = Counter(f for r in correct for f in r["families"].split("|") if f)
    lines.append(
        "correct tasks using family: " + json.dumps(dict(sorted(fams.items())))
    )
    blocks = Counter(b for r in correct for b in r["blocks"].split("|") if b)
    lines.append("top blocks (correct): " + json.dumps(dict(blocks.most_common(10))))
    return lines


def load_cpp(path: str) -> dict[str, str]:
    """task_id -> cpp_correct ("1"/"0") from an intercept.py CSV."""
    with open(path, newline="") as handle:
        return {r["task_id"]: r["cpp_correct"] for r in csv.DictReader(handle)}


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    cpp = None
    if "--cpp" in args:
        at = args.index("--cpp")
        if at + 1 >= len(args):
            return _usage()
        cpp = load_cpp(args[at + 1])
        del args[at : at + 2]
    if len(args) not in (1, 2):
        return _usage()
    rows = load(args[0], args[1] if len(args) == 2 else None)
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    print("\n".join(summary(rows, cpp)), file=sys.stderr)
    return 0


def _usage() -> int:
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
