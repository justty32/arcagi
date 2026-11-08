"""CLI: ``python -m arcagi.blocks.meta --scratch DIR [--out FILE]``."""

import argparse
from pathlib import Path

from .run import main

parser = argparse.ArgumentParser(description="Two-fold meta experiment.")
parser.add_argument("--scratch", type=Path, required=True)
parser.add_argument("--out", type=Path, default=None)
args = parser.parse_args()
main(args.scratch, args.out)
