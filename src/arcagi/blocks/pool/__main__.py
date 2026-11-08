"""CLI: settle one node-pool epoch (``python -m arcagi.blocks.pool``)."""

import argparse
import json
from pathlib import Path

from .. import REPO_ROOT
from .ledger import EpochError, run_epoch


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
    keys = ("epoch", "income", "retained", "dividends_total", "conservation_ok")
    keys += ("suggest_retire", "retire", "generator_budget", "gradients_written")
    print(json.dumps({k: summary.get(k) for k in keys}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
