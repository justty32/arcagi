"""Apply the shadow gate to blocks; returns one verdict dict per block."""

import json
from collections.abc import Sequence
from pathlib import Path

from arcagi.tasks import Task

from . import CHUNK_MAJORITY, MIN_SUPPORT, MIN_SYNTH_FRAC, PRED_SYNTH_FRAC
from .blocks import live_index, loadable
from .support import chunk_rates, support


def _key(body: object) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def duplicate_of(block: dict, sup: set[str], live: Sequence[dict]) -> str | None:
    """A live block of the same kind with the same body or the same support."""
    for other in live:
        if other["kind"] != block["kind"] or other["name"] == block["name"]:
            continue
        if _key(other["body"]) == _key(block["body"]):
            return other["name"]
        if block["kind"] != "macro" and sup and other["support"] == frozenset(sup):
            return other["name"]
    return None


def verdict(
    block: dict, sup: set[str], rates: dict[str, float], dup: str | None
) -> dict:
    need = PRED_SYNTH_FRAC if block["kind"] == "pred" else MIN_SYNTH_FRAC
    ok = [t for t, r in rates.items() if r >= CHUNK_MAJORITY]
    frac = len(ok) / len(sup) if sup else 0.0
    reasons = []
    if (why := loadable(block)) is not None:
        reasons.append(why)
    if len(sup) < MIN_SUPPORT:
        reasons.append("no training support")
    elif frac + 1e-9 < need:
        reasons.append(f"synth majority {len(ok)}/{len(sup)} < {need:.2f}")
    if dup:
        reasons.append(f"duplicate of live {dup}")
    return {
        "name": block["name"],
        "kind": block["kind"],
        "status": block["status"],
        "pass": not reasons,
        "reasons": reasons,
        "support": sorted(sup),
        "synth_ok": len(ok),
        "synth_frac": round(frac, 3),
        "chunk_rates": rates,
        "duplicate_of": dup,
        "body": block["body"],
    }


def run(
    blocks: Sequence[dict],
    orig: Sequence[Task],
    chunks: dict,
    blocks_root: Path | None = None,
) -> list[dict]:
    """Verdicts for ``blocks``; duplicates checked against live ``blocks_root``."""
    from arcagi.blocks import default_blocks_root
    from arcagi.blocks.catalog import load_catalog
    from arcagi.dsl import predicates as pr

    root = Path(blocks_root) if blocks_root else default_blocks_root()
    pr.install(load_catalog(root).predicates())  # named preds used by selectors
    live = live_index(root) if root.is_dir() else []
    claims = support(blocks, orig)
    rates = chunk_rates(blocks, claims, chunks)
    return [
        verdict(
            b,
            claims[b["name"]],
            rates[b["name"]],
            duplicate_of(b, claims[b["name"]], live),
        )
        for b in blocks
    ]


def summary(results: Sequence[dict]) -> dict:
    """Counts of pass / fail per kind and of each first reason."""
    out: dict = {"total": len(results), "pass": 0, "by_kind": {}, "reasons": {}}
    for r in results:
        row = out["by_kind"].setdefault(r["kind"], {"total": 0, "pass": 0})
        row["total"] += 1
        row["pass"] += r["pass"]
        out["pass"] += r["pass"]
        for why in r["reasons"]:
            head = " ".join(why.split(" ")[:2])
            out["reasons"][head] = out["reasons"].get(head, 0) + 1
    return out


def table(results: Sequence[dict]) -> str:
    """Markdown table: name, kind, support, synth majority, verdict, reasons."""
    lines = [
        "| block | kind | support | synth ok | pass | reasons |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['kind']} | {len(r['support'])} | "
            f"{r['synth_ok']}/{len(r['support'])} | {'yes' if r['pass'] else 'no'} | "
            f"{'; '.join(r['reasons']) or '-'} |"
        )
    return "\n".join(lines)


__all__ = ["duplicate_of", "run", "summary", "table", "verdict"]
