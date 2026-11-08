"""Task access for the LLM loop: raw JSON, unsolved lists, prompt views.

The prompt view carries train pairs and test *inputs* only; test outputs are
read solely by ``verify`` for scoring and never reach a prompt or a check.
"""

import json
from pathlib import Path

from . import DATA_ROOT, LLM_ROOT, REPO_ROOT

type Grid = list[list[int]]
SPLITS = ("training", "evaluation")
DEFAULT_REPORT = REPO_ROOT / "artifacts" / "r04" / "dsl-{split}.json"


def load(task_id: str, split: str) -> dict:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    return json.loads((DATA_ROOT / split / f"{task_id}.json").read_text())


def unsolved(split: str, report: Path | None = None) -> list[str]:
    """Task ids the main-line report did not solve, sorted."""
    path = report or Path(str(DEFAULT_REPORT).format(split=split))
    data = json.loads(path.read_text())
    return sorted(t["task_id"] for t in data["tasks"] if not t["correct"])


def pairs(task: dict) -> list[tuple[Grid, Grid]]:
    return [(p["input"], p["output"]) for p in task["train"]]


def _grid_text(grid: Grid) -> str:
    return "\n".join(" ".join(str(v) for v in row) for row in grid)


def prompt_view(task_id: str, split: str) -> str:
    """Markdown with train pairs and test inputs (no test outputs)."""
    task = load(task_id, split)
    out = [f"# Task {task_id}", ""]
    for i, (inp, outp) in enumerate(pairs(task)):
        h, w = len(inp), len(inp[0])
        oh, ow = len(outp), len(outp[0])
        out += [f"## train {i}: input {h}x{w}", "```", _grid_text(inp), "```"]
        out += [f"## train {i}: output {oh}x{ow}", "```", _grid_text(outp), "```"]
    for i, p in enumerate(task["test"]):
        h, w = len(p["input"]), len(p["input"][0])
        out += [f"## test {i}: input {h}x{w}", "```", _grid_text(p["input"]), "```"]
    return "\n".join(out) + "\n"


def write_prompt(task_id: str, split: str) -> Path:
    path = LLM_ROOT / "prompts" / "tasks" / f"{task_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prompt_view(task_id, split))
    return path
