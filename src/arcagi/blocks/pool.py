"""node-pool style accounts for blocks: one full eval report = one epoch.

Run: ``uv run python -m arcagi.blocks.pool --report R.json --epoch N --split S``.

Per solved task the top level earns ``price``; it keeps ``retain`` and pays the
rest to blocks in proportion to their static references in the selected
program. Spend = ``trace.metadata.block_calls[name] / calls_per_unit * cost``
(0 when absent). Every wallet pays ``rent`` per epoch. A block with zero
dividend for ``retire_after`` epochs in a row is only *suggested* for retirement.
A generated block (``generator`` in its metainfo, e.g. a ``pred_*``
referenced as a selector parameter) passes ``generator_cut`` of its dividend to
its generator node. Near misses of unsolved tasks become ``_gradients.jsonl``
letters to the blocks they reference. Files: ``config.json``, ``wallets.json``,
``ledger.jsonl`` (append-only), ``epochs/<n>.json``.
"""

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from . import REPO_ROOT, read_json, write_json
from .catalog import Catalog, load_catalog

DEFAULT_CONFIG: dict[str, Any] = {
    "price_per_task": 1000,
    "retain": 0.2,
    "rent": 100,
    "calls_per_unit": 1000,
    "retire_after": 3,
    "gradient_cap": 50,
    "near_misses_per_task": 1,
    "generator_cut": 0.2,
}


class EpochError(RuntimeError):
    """The requested epoch conflicts with the ledger."""


def selected_steps(trace: dict | None) -> list[str]:
    """Block references of the selected attempt: step names plus pred params."""
    if not trace or trace.get("selected") is None:
        return []
    for attempt in trace.get("attempts", []):
        if attempt.get("id") == trace["selected"] and "program" in attempt:
            try:
                steps = json.loads(attempt["program"])
                return [step[0] for step in steps] + [
                    p for step in steps for p in step[1:] if _is_pred(p)
                ]
            except (ValueError, TypeError, IndexError):
                return []
    return []


def _is_pred(param: object) -> bool:
    return isinstance(param, str) and param.startswith("pred_")


def _generator_share(
    dividends: dict[str, Fraction], catalog: Catalog, cut: Fraction
) -> None:
    """Move ``cut`` of each generated block's dividend to its generator node."""
    for name in sorted(dividends):
        block = catalog.blocks.get(name)
        gen = block.meta.get("generator") if block else None
        if isinstance(gen, str) and gen and dividends[name] > 0:
            moved = dividends[name] * cut
            dividends[name] -= moved
            dividends[gen] = dividends.get(gen, Fraction(0)) + moved


def _near_misses(trace: dict | None, limit: int) -> list[dict]:
    if not trace:
        return []
    near = [a for a in trace.get("attempts", []) if a.get("kind") == "near_miss"]
    near.sort(key=lambda a: -a.get("data", {}).get("pixel_acc", 0))
    return near[:limit]


def _ledger_epochs(path: Path) -> dict[int, str]:
    found: dict[int, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("type") == "epoch":
                    found[row["epoch"]] = row.get("report_sha256", "")
    return found


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
            letter = {
                "from": "pool",
                "task": task.get("task_id"),
                "program": attempt["program"],
                "score": attempt.get("data", {}).get("pixel_acc"),
                "train_correct": attempt.get("train_correct"),
                "train_total": attempt.get("train_total"),
                "says": "near miss on an unsolved task",
            }
            letters.extend((name, letter) for name in sorted(names))
    _generator_share(
        dividends, catalog, Fraction(str(config.get("generator_cut", 0.2)))
    )
    income = solved * price
    exact_retained = income - sum(dividends.values(), Fraction(0))
    paid = {name: round(float(value), 6) for name, value in dividends.items()}
    retained = round(float(exact_retained), 6)
    names = set(wallets.get("blocks", {})) | set(catalog.blocks) | set(paid)
    names |= set(calls)
    blocks_out: dict[str, dict] = {}
    for name in sorted(names):
        old = wallets.get("blocks", {}).get(name, {})
        spend = round(
            calls.get(name, 0) / config["calls_per_unit"] * catalog.cost(name), 6
        )
        dividend = paid.get(name, 0.0)
        streak = 0 if dividend > 0 else old.get("zero_streak", 0) + 1
        blocks_out[name] = {
            "balance": round(
                old.get("balance", 0.0) + dividend - spend - config["rent"], 6
            ),
            "dividend": dividend,
            "spend": spend,
            "rent": config["rent"],
            "refs": refs.get(name, 0),
            "zero_streak": streak,
            "income_total": round(old.get("income_total", 0.0) + dividend, 6),
        }
    top = wallets.get("top", {})
    new_wallets = {
        "top": {"balance": round(top.get("balance", 0.0) + retained, 6)},
        "blocks": blocks_out,
    }
    summary = {
        "income": income,
        "tasks_solved": solved,
        "tasks_total": len(report.get("tasks", [])),
        "retained": retained,
        "dividends_total": round(float(income - exact_retained), 6),
        "conservation_ok": exact_retained + sum(dividends.values()) == income
        and abs(income - retained - sum(paid.values())) < 1e-3,
        "suggest_retire": sorted(
            n
            for n, b in blocks_out.items()
            if b["zero_streak"] >= config["retire_after"]
        ),
        "blocks": blocks_out,
    }
    return summary, new_wallets, letters


def _append_letters(catalog: Catalog, letters: list, epoch: int, cap: int) -> int:
    written = 0
    for name, letter in letters:
        block = catalog.blocks.get(name)
        if block is None:
            continue
        path = block.path / "_gradients.jsonl"
        lines = path.read_text(encoding="utf-8").count("\n") if path.exists() else 0
        if lines >= cap:
            continue
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"epoch": epoch, **letter}) + "\n")
        written += 1
    return written


def _bump_uses(catalog: Catalog, blocks: dict) -> None:
    for name, row in blocks.items():
        block = catalog.blocks.get(name)
        if block is None or not row["refs"]:
            continue
        meta = dict(block.meta)
        meta["counter_uses"] = meta.get("counter_uses", 0) + row["refs"]
        write_json(block.path / "_metainfo.json", meta)


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
    summary = {
        "epoch": epoch,
        "split": split,
        "report": str(report_path),
        "report_sha256": sha,
        **summary,
    }
    summary["gradients_written"] = _append_letters(
        catalog, letters, epoch, config["gradient_cap"]
    )
    write_json(pool / "epochs" / f"{epoch}.json", summary)
    write_json(pool / "wallets.json", {"epoch": epoch, **new_wallets})
    rows = [
        {
            "type": "epoch",
            "epoch": epoch,
            "split": split,
            "report_sha256": sha,
            "income": summary["income"],
            "retained": summary["retained"],
            "conservation_ok": summary["conservation_ok"],
        }
    ]
    rows += [
        {"type": "block", "epoch": epoch, "block": name, **row}
        for name, row in summary["blocks"].items()
    ]
    pool.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _bump_uses(catalog, summary["blocks"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Settle one node-pool epoch.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--pool", type=Path, default=REPO_ROOT / "aos" / "pool")
    parser.add_argument("--blocks", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        summary = run_epoch(args.report, args.epoch, args.split, args.pool, args.blocks)
    except EpochError as exc:
        print(f"arcagi.blocks.pool: {exc}")
        return 2
    keys = (
        "epoch",
        "income",
        "retained",
        "dividends_total",
        "conservation_ok",
        "suggest_retire",
        "gradients_written",
    )
    print(json.dumps({k: summary.get(k) for k in keys}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
