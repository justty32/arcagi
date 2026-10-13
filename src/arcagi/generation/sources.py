"""Locate and verify the small, pinned upstream source snapshot."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def repository_root() -> Path:
    """Return the checkout root, with an override for installed environments."""
    return Path(os.environ.get("ARCAGI_ROOT", Path(__file__).resolve().parents[3]))


def vendor_directory() -> Path:
    """Locate the RE-ARC source submodule."""
    return repository_root() / "vendor" / "re-arc"


def verify_sources() -> dict[str, Any]:
    """Reject missing or changed upstream source files before execution."""
    directory = vendor_directory()
    try:
        source = json.loads((directory.parent / "re-arc-source.json").read_text())
    except FileNotFoundError as error:
        raise FileNotFoundError(
            "RE-ARC sources missing; run from the checkout or set ARCAGI_ROOT"
        ) from error
    for filename, expected in source["files"].items():
        actual = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"RE-ARC source checksum mismatch: {filename}")
    return source
