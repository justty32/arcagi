"""Open, nonoverlapping cost dimensions and explicit exchange rates."""

import csv
import math
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from . import boundary

KEY = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)*")
FIELDS = {
    "evals_body": "evals.body",
    "evals_shadow": "evals.shadow",
    "evals_meta": "evals.meta",
    "evals_foundry": "evals.foundry",
    "llm_calls": "llm.calls",
    "wall_s": "wall_s",
}
LEGACY_RATES = {key: int(key.startswith("evals.")) for key in FIELDS.values()}


def validate(cost: object, *, rates: bool = False) -> list[str]:
    """Return dimension/value errors; rates allow ancestor/descendant keys."""
    if not isinstance(cost, dict):
        return ["expected a cost/rates object"]
    errors = []
    for key, value in cost.items():
        if not isinstance(key, str) or KEY.fullmatch(key) is None:
            errors.append(f"invalid key: {key!r}")
            continue
        if type(value) not in (int, float):
            errors.append(f"{key}: expected a finite nonnegative int or float")
        else:
            try:
                valid = math.isfinite(value) and value >= 0
            except OverflowError:
                valid = False
            if not valid:
                errors.append(f"{key}: expected a finite nonnegative int or float")
        if not rates:
            parts = key.split(".")
            for depth in range(1, len(parts)):
                ancestor = ".".join(parts[:depth])
                if ancestor in cost:
                    errors.append(f"overlapping dimensions: {ancestor} and {key}")
    return errors


def _require(cost: object, *, rates: bool = False) -> None:
    errors = validate(cost, rates=rates)
    if errors:
        raise ValueError("; ".join(errors))


def price(
    cost: dict[str, int | float],
    rates: dict[str, int | float],
    keys: Iterable[str] | None = None,
) -> float:
    """Price exact rate keys, optionally selecting dimensions by segment prefix."""
    _require(cost)
    _require(rates, rates=True)
    prefixes = None if keys is None else tuple(keys)
    return float(
        sum(
            rates.get(key, 0) * value
            for key, value in cost.items()
            if prefixes is None
            or any(key == prefix or key.startswith(prefix + ".") for prefix in prefixes)
        )
    )


def rollup(cost: dict[str, int | float], depth: int) -> dict[str, int | float]:
    """Return a new cost object truncated to at most depth path segments."""
    _require(cost)
    if type(depth) is not int or depth < 1:
        raise ValueError("depth must be a positive integer")
    result = {}
    for key, value in cost.items():
        parent = ".".join(key.split(".")[:depth])
        result[parent] = result.get(parent, 0) + value
    return result


def curves(root: Path, epochs: Iterable[int]) -> dict[int, dict[str, str]]:
    """Read exactly one curve row per completed epoch, checking its identity."""
    result = {}
    for epoch in epochs:
        boundary.check_stop()
        path = root / "epochs" / str(epoch) / "curve.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 1 or int(rows[0]["epoch"]) != epoch:
            raise ValueError(f"{path}: expected one row matching epoch {epoch}")
        result[epoch] = rows[0]
    return result


def records(rows: Mapping[int, dict[str, str]]) -> list[dict]:
    """Map curve spending fields without including state or inventing tokens."""
    result = []
    for epoch, row in rows.items():
        values = {
            key: float(row[field]) if field == "wall_s" else int(row[field])
            for field, key in FIELDS.items()
        }
        _require(values)
        result.append(
            {
                "schema": "t2-cost/1",
                "epoch": epoch,
                "who": "hammer",
                "cost": values,
                "src": f"epochs/{epoch}/curve.csv",
            }
        )
    return result


def check_open(rows: list[dict], rates: dict) -> dict:
    """Check every stored cost and exercise open keys and prefix selection."""
    errors = validate(rates, rates=True)
    for index, row in enumerate(rows):
        errors.extend(f"row {index}: {error}" for error in validate(row["cost"]))
    sample = {"evals.body": 2, "evals.shadow": 3, "gpu.sec": 4, "agent.ideas.tokens": 7}
    extended = {**LEGACY_RATES, "gpu.sec": 2}
    probes = {
        "open_key_price": price(sample, extended),
        "unknown_rate_price": price({"agent.ideas.tokens": 7}, extended),
        "prefix_price": price(sample, extended, keys=["evals"]),
    }
    if list(probes.values()) != [13, 0, 5]:
        errors.append("open-key / unknown-rate / prefix price probe failed")
    priced_total = None if errors else sum(price(row["cost"], rates) for row in rows)
    return {
        "pass": not errors,
        "rows": len(rows),
        "priced_total": priced_total,
        **probes,
        "errors": errors,
    }


def check_legacy(
    rows: list[dict], expected: list[dict], meter: dict, credit_rows: list[dict]
) -> dict:
    """Compare all legacy fields and totals with the read-only reference meter."""
    errors = []
    if len(rows) != len(expected) or {r["epoch"] for r in rows} != {
        r["epoch"] for r in expected
    }:
        errors.append("cost epochs must appear exactly once, including baseline 0")
    reference = {row["epoch"]: row for row in expected}
    for row in rows:
        target = reference.get(row["epoch"])
        if target is None or any(
            row[key] != target[key] for key in ("schema", "who", "src")
        ):
            errors.append(f"epoch={row['epoch']}: invalid cost provenance")
        elif any(
            row["cost"].get(key) != value for key, value in target["cost"].items()
        ):
            errors.append(f"epoch={row['epoch']}: legacy cost fields differ from curve")
    legacy = sum(price(row["cost"], LEGACY_RATES) for row in rows)
    # Only the first layer contributes to the root amount; never sum both layers.
    total_amount = sum(row["amount"] for row in credit_rows if row["layer"] == 1)
    delta_cost, delta_eff = legacy - meter["cost"], total_amount - meter["eff"]
    if delta_cost != 0:
        errors.append(
            f"legacy price minus meter cost = {delta_cost}, expected exactly 0"
        )
    if not math.isfinite(delta_eff) or abs(delta_eff) > 1e-4:
        errors.append(f"root amount minus meter eff = {delta_eff}")
    return {
        "pass": not errors,
        "legacy_price": legacy,
        "meter_cost": meter["cost"],
        "delta_cost": delta_cost,
        "amount_sum": total_amount,
        "meter_eff": meter["eff"],
        "delta_eff": delta_eff,
        "errors": errors,
    }
