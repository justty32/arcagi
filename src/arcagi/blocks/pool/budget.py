"""Generator budgets: shares at settlement, candidate counts at enumeration.

``shares`` (called by ``ledger.settle``) turns net generator income into next
round shares, each at least ``generator_floor``. ``allocate`` reads those shares
from the newest ``epochs/<n>.json`` and turns them into candidate counts:
``generator_total`` (``config.json``) x share, at least ``generator_floor`` of
the total and at least ``MIN_CANDIDATES``. Generators call ``allocate`` before
enumerating and print what they got.
"""

import json
from pathlib import Path

from .. import REPO_ROOT, read_json

POOL = REPO_ROOT / "aos" / "pool"
GENERATORS = ("_gen/extract", "_gen/formula", "_gen/pred_combiner")
DEFAULT_TOTAL = 25000  # ~ r03 enumeration: 1500 extract + 1620 formula + 21321 pred
DEFAULT_FLOOR = 0.2
MIN_CANDIDATES = 40
TOP_EXTRACTS = 20


def shares(rows: dict[str, dict], gens: list[str], floor: float) -> dict:
    """Next-round budget shares by positive net income, each at least ``floor``."""
    floor = min(floor, 1 / len(gens)) if gens else 0
    net = {n: rows[n]["dividend"] - rows[n]["spend"] for n in gens}
    pos = sum(max(v, 0.0) for v in net.values())
    part = {n: max(v, 0.0) / pos if pos else 1 / len(gens) for n, v in net.items()}
    rest = 1 - floor * len(gens)
    return {
        n: {"net": round(net[n], 6), "share": round(floor + rest * part[n], 6)}
        for n in gens
    }


def latest_epoch(pool: Path = POOL) -> Path | None:
    """Newest ``epochs/<n>.json`` by epoch number, or None."""
    files = [p for p in (pool / "epochs").glob("*.json") if p.stem.isdigit()]
    return max(files, key=lambda p: int(p.stem)) if files else None


def allocate(epoch_file: Path | str | None = None) -> dict[str, int]:
    """Candidate count per generator (``"_gen/<name>"``) for this enumeration.

    ``epoch_file`` defaults to the newest epoch; its ``config.json`` is the one
    next to ``epochs/``. Without an epoch or a recorded budget every known
    generator gets an equal share.
    """
    path = Path(epoch_file) if epoch_file is not None else latest_epoch()
    pool = path.parent.parent if path is not None else POOL
    config = read_json(pool / "config.json", {}) or {}
    total = int(config.get("generator_total", DEFAULT_TOTAL))  # type: ignore[union-attr]
    floor = float(config.get("generator_floor", DEFAULT_FLOOR))  # type: ignore[union-attr]
    epoch = read_json(path, {}) if path is not None else {}
    budget = (epoch or {}).get("generator_budget") or {}  # type: ignore[union-attr]
    names = sorted(set(GENERATORS) | set(budget))
    out = {}
    for name in names:
        row = budget.get(name)
        share = row.get("share") if isinstance(row, dict) else None
        share = float(share) if share is not None else 1 / len(names)
        out[name] = max(round(total * max(share, floor)), MIN_CANDIDATES)
    return out


def income(pool: Path = POOL) -> dict[str, float]:
    """Ledger score per block: total dividends so far (``wallets.json``)."""
    rows = (read_json(pool / "wallets.json", {}) or {}).get("blocks", {})  # type: ignore[union-attr]
    return {n: float(r.get("income_total", 0)) for n, r in rows.items()}


def top_extracts(root: Path | None = None, n: int = TOP_EXTRACTS) -> dict:
    """The ``n`` best live quantity extract blocks (name -> body) by ledger
    income, then training score: the formula generator's extra features."""
    from arcagi.dsl.features import NUMERIC_PROPS

    from ..catalog import load_catalog  # lazy: catalog is heavier than budget

    catalog = load_catalog(root)
    rules = {k: r.get("body") for k, r in catalog.rules("extract").items()}
    ok = {k: b for k, b in rules.items() if isinstance(b, list) and b}
    ok = {k: b for k, b in ok.items() if b[0] in NUMERIC_PROPS}
    paid, meta = income(), {k: catalog.blocks[k].meta for k in ok}
    best = sorted(ok, key=lambda k: (-paid.get(k, 0), -meta[k].get("score", 0), k))
    return {k: ok[k] for k in best[:n]}


def announce(generator: str, budget: int) -> None:
    """Print the budget a generator enumerates with (the log line)."""
    print(json.dumps({"generator": generator, "budget": budget}))


__all__ = [
    "DEFAULT_TOTAL",
    "GENERATORS",
    "allocate",
    "announce",
    "income",
    "shares",
    "top_extracts",
]
