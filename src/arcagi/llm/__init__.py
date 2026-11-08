"""LLM-proposed rules (distillation step one, branch S2).

An LLM reads the train pairs of an unsolved task and writes four-kind block
JSON (``{"kind": pred|extract|formula|transform, "in", "out", "body"}``); the
program checks it on train, records every proposal as a trace line, and turns
train-passing rules into candidate blocks under ``aos/llm/candidates/`` for the
main line to rescore and adopt. Nothing here writes ``aos/blocks/``.

Modules: ``tasks`` (task views without test outputs), ``verify`` (rule ->
train / test check), ``candidates`` (candidate folders, component split),
``rescore`` (training support of candidates), ``trace`` (JSONL log),
``__main__`` (CLI).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LLM_ROOT = REPO_ROOT / "aos" / "llm"
DATA_ROOT = REPO_ROOT / "data" / "ARC-AGI" / "data"
