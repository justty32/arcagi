"""node-pool style accounts for blocks: one full eval report = one epoch.

CLI in ``__main__``; budget shares and ``allocate`` in ``budget``.

A solved task pays ``price``: the top keeps ``retain``, blocks share the rest by
static references in the selected program; a macro passes ``macro_passdown`` on
to its ``program.json`` steps, a generated block (``generator`` in metainfo, e.g.
a ``pred_*`` parameter) ``generator_cut`` to its generator. Spend = block_calls /
``calls_per_unit`` x cost, plus ``gen_seconds`` x ``generator_rate`` for
generator nodes; ``rent`` per epoch. ``retire_after`` zero-dividend epochs in a
row: suggested retirement unless ``essential``; really retired (status, ledger)
if generated and ``covered``. ``generator_budget`` (net shares, floor
``generator_floor``) feeds ``budget.allocate`` for the next enumeration.
Near misses become ``_gradients.jsonl`` letters. Files: ``config.json``,
``wallets.json``, ``ledger.jsonl`` (append-only), ``epochs/<n>.json``.
"""

import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from .. import read_json, write_json
from ..catalog import Catalog, load_catalog, load_macro_program
from .budget import shares

DEFAULT_CONFIG: dict[str, Any] = {
    "price_per_task": 1000,
    "retain": 0.2,
    "rent": 100,
    "calls_per_unit": 1000,
    "retire_after": 3,
    "gradient_cap": 50,
    "near_misses_per_task": 1,
    "generator_cut": 0.2,
    "essential": [],
    "macro_passdown": 0.5,
    "generator_rate": 1.0,
    "generator_floor": 0.2,
    "generator_total": 25000,
}
LETTER_KEYS = ("program", "train_correct", "train_total")


class EpochError(RuntimeError):
    """The requested epoch conflicts with the ledger."""


def selected_steps(trace: dict | None) -> list[str]:
    """Block references of the selected attempt: step names plus pred params."""
    if not trace or trace.get("selected") is None:
        return []
    for attempt in trace.get("attempts", []):
        if attempt.get("id") == trace["selected"] and "program" in attempt:
            try:
                return _refs(json.loads(attempt["program"]))
            except (ValueError, TypeError, IndexError):
                return []
    return []


def _refs(steps) -> list[str]:
    """Static block references of a program: step names plus pred_* params."""
    preds = [p for step in steps for p in step[1:] if _is_pred(p)]
    return [step[0] for step in steps] + preds


def _is_pred(param: object) -> bool:
    # Generated-block references: pred_*, formula_*, extract_* and llm_* names.
    return isinstance(param, str) and param.startswith(
        ("pred_", "formula_", "extract_", "llm_")
    )


def _move(dividends: dict[str, Fraction], cut: object, targets: dict) -> None:
    """Move ``cut`` of each dividend to ``targets[name]`` (a Counter) by weight."""
    for name in sorted(dividends):
        parts = targets.get(name) if dividends[name] > 0 else None
        if parts:
            moved = dividends[name] * Fraction(str(cut))
            dividends[name] -= moved
            for part, n in parts.items():
                share = moved * n / sum(parts.values())
                dividends[part] = dividends.get(part, Fraction(0)) + share


def _targets(catalog: Catalog) -> tuple[dict[str, Counter], dict[str, Counter]]:
    """Macro name -> its program's refs; generated block -> its generator."""
    blocks = catalog.blocks.items()
    macros = [(n, load_macro_program(b.path)) for n, b in blocks if b.kind == "macro"]
    gens = [(n, b.meta.get("generator")) for n, b in blocks]
    parts = {n: Counter(_refs(p or ())) for n, p in macros}
    return parts, {n: Counter([g]) for n, g in gens if isinstance(g, str) and g}


def _generator_meta(catalog: Catalog) -> dict[str, dict]:
    """Generator nodes: ``<root>/_gen/*`` folders plus names cited as generator."""
    names = {b.meta.get("generator") for b in catalog.blocks.values()}
    found = {n: {} for n in names if isinstance(n, str) and n}
    if catalog.root is not None:
        found |= {
            f"_gen/{p.parent.name}": {}
            for p in catalog.root.glob("_gen/*/_*.json")
            if not p.parent.name.startswith("_")  # _gen/_meta tunes generators
        }
        for name in found:
            meta = read_json(catalog.root / name / "_metainfo.json", {})
            found[name] = meta if isinstance(meta, dict) else {}
    return found


def _near_misses(trace: dict, limit: int) -> list[dict]:
    near = [a for a in trace.get("attempts", []) if a.get("kind") == "near_miss"]
    return sorted(near, key=lambda a: -a.get("data", {}).get("pixel_acc", 0))[:limit]


def _ledger_epochs(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return {
        r["epoch"]: r.get("report_sha256", "") for r in rows if r["type"] == "epoch"
    }


def settle(
    report: dict, wallets: dict, config: dict, catalog: Catalog
) -> tuple[dict, dict, list[tuple[str, dict]]]:
    """Pure accounting: return (epoch summary, new wallets, gradient letters)."""
    price, retain = config["price_per_task"], config["retain"]
    dividends: dict[str, Fraction] = {}
    share = 1 - Fraction(str(retain))
    refs: Counter[str] = Counter()
    calls: Counter[str] = Counter()
    letters: list[tuple[str, dict]] = []
    solved = 0
    for task in report.get("tasks", []):
        trace = task.get("trace") or {}
        block_calls = (trace.get("metadata") or {}).get("block_calls") or {}
        calls.update({k: v for k, v in block_calls.items() if isinstance(v, int)})
        if task.get("correct"):
            solved += 1
            steps = Counter(selected_steps(trace))
            refs.update(steps)
            total = sum(steps.values())
            for name, count in steps.items():
                part = price * share * Fraction(count, total)
                dividends[name] = dividends.get(name, Fraction(0)) + part
            continue
        for attempt in _near_misses(trace, config["near_misses_per_task"]):
            try:
                names = {step[0] for step in json.loads(attempt["program"])}
            except (KeyError, ValueError, TypeError, IndexError):
                continue
            letter = {"from": "pool", "task": task.get("task_id")}
            letter |= {k: attempt.get(k) for k in LETTER_KEYS}
            letter["score"] = attempt.get("data", {}).get("pixel_acc")
            letter["says"] = "near miss on an unsolved task"
            letters.extend((name, letter) for name in sorted(names))
    macro_parts, gen_parts = _targets(catalog)
    _move(dividends, config["macro_passdown"], macro_parts)
    _move(dividends, config["generator_cut"], gen_parts)
    gens = _generator_meta(catalog)
    income = solved * price
    exact_retained = income - sum(dividends.values(), Fraction(0))
    paid = {name: round(float(value), 6) for name, value in dividends.items()}
    retained = round(float(exact_retained), 6)
    names = set(wallets.get("blocks", {})) | set(catalog.blocks) | set(paid)
    names |= set(calls) | set(gens)
    blocks_out: dict[str, dict] = {}
    for name in sorted(names):
        old = wallets.get("blocks", {}).get(name, {})
        sec = gens.get(name, {}).get("gen_seconds", 0)
        spend = calls.get(name, 0) / config["calls_per_unit"] * catalog.cost(name)
        spend = round(spend + float(sec or 0) * config["generator_rate"], 6)
        dividend = paid.get(name, 0.0)
        streak = 0 if dividend > 0 else old.get("zero_streak", 0) + 1
        balance = old.get("balance", 0.0) + dividend - spend - config["rent"]
        blocks_out[name] = {"balance": round(balance, 6), "dividend": dividend}
        blocks_out[name] |= {"spend": spend, "rent": config["rent"]}
        blocks_out[name] |= {"refs": refs.get(name, 0), "zero_streak": streak}
        total = old.get("income_total", 0) + dividend
        blocks_out[name]["income_total"] = round(total, 6)
    top = round(wallets.get("top", {}).get("balance", 0.0) + retained, 6)
    new_wallets = {"top": {"balance": top}, "blocks": blocks_out}
    ess, after = sorted(config["essential"]), config["retire_after"]
    idle = [n for n, b in blocks_out.items() if b["zero_streak"] >= after]
    idle = sorted(n for n in idle if n not in ess)
    gone = [b for n in idle if (b := catalog.blocks.get(n)) and b.meta.get("generator")]
    summary = {"income": income, "tasks_solved": solved, "retained": retained}
    summary["tasks_total"] = len(report.get("tasks", []))
    summary["dividends_total"] = round(float(income - exact_retained), 6)
    summary["conservation_ok"] = exact_retained + sum(dividends.values()) == income
    summary["conservation_ok"] &= abs(income - retained - sum(paid.values())) < 1e-3
    summary |= {"essential": ess, "suggest_retire": idle}
    summary["retire"] = [b.name for b in gone if b.status == "covered"]
    budget = shares(blocks_out, sorted(gens), config["generator_floor"])
    summary |= {"generator_budget": budget, "blocks": blocks_out}
    return summary, new_wallets, letters


def _append_letters(catalog: Catalog, letters: list, epoch: int, cap: int) -> int:
    written = 0
    for name, letter in letters:
        block = catalog.blocks.get(name)
        path = block.path / "_gradients.jsonl" if block else None
        if path and (path.read_text().count("\n") if path.exists() else 0) < cap:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"epoch": epoch, **letter}) + "\n")
            written += 1
    return written


def _bump_uses(catalog: Catalog, blocks: dict) -> None:
    for name, row in blocks.items():
        if (block := catalog.blocks.get(name)) and row["refs"]:
            uses = block.meta.get("counter_uses", 0) + row["refs"]
            write_json(
                block.path / "_metainfo.json", {**block.meta, "counter_uses": uses}
            )


def run_epoch(
    report_path: Path, epoch: int, split: str, pool: Path, blocks_root: Path | None
) -> dict:
    """Settle one epoch and write all pool files; idempotent for the same report."""
    raw = report_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    ledger = pool / "ledger.jsonl"
    seen = _ledger_epochs(ledger)
    if epoch in seen:
        if seen[epoch] == sha:
            return read_json(pool / "epochs" / f"{epoch}.json", {})  # type: ignore[return-value]
        raise EpochError(f"epoch {epoch} already recorded from a different report")
    expected = max(seen) + 1 if seen else 0
    if epoch != expected:
        raise EpochError(f"next epoch must be {expected}, got {epoch}")
    config = read_json(pool / "config.json", None)
    if not isinstance(config, dict):
        config = dict(DEFAULT_CONFIG)
        write_json(pool / "config.json", config)
    config = {**DEFAULT_CONFIG, **config}
    catalog = load_catalog(blocks_root)
    wallets = read_json(pool / "wallets.json", {}) or {}
    summary, new_wallets, letters = settle(json.loads(raw), wallets, config, catalog)  # type: ignore[arg-type]
    head = {"epoch": epoch, "split": split, "report": str(report_path)}
    summary = {**head, "report_sha256": sha, **summary}
    summary["gradients_written"] = _append_letters(
        catalog, letters, epoch, config["gradient_cap"]
    )
    write_json(pool / "epochs" / f"{epoch}.json", summary)
    write_json(pool / "wallets.json", {"epoch": epoch, **new_wallets})
    keys = ("epoch", "split", "report_sha256", "income", "retained", "conservation_ok")
    rows = [{"type": "epoch", **{k: summary[k] for k in keys}}]
    rows += [
        {"type": "block", "epoch": epoch, "block": name, **row}
        for name, row in summary["blocks"].items()
    ]
    rows += [{"type": "retire", "epoch": epoch, "block": n} for n in summary["retire"]]
    pool.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _bump_uses(catalog, summary["blocks"])
    for name in summary["retire"]:  # after _bump_uses, which rewrites metainfo
        path = catalog.blocks[name].path / "_metainfo.json"
        write_json(path, {**(read_json(path, {}) or {}), "status": "retired"})
    return summary
