"""The fixed hammer-v1 genome boundary and projection rules."""

import os
from pathlib import Path, PurePosixPath

PROFILE = "hammer-v1"
JSON_FILES = frozenset(("_metainfo.json", "frozen.json"))
FILE_STUBS = frozenset(("ctl", "_view.sh", "README.md"))
EXCLUDED_DIRS = frozenset(("epochs", "live", "foundry", "tmp", "think1", "ops"))
EXCLUDED_FILES = frozenset(("RUN", "ledger.jsonl"))
OP_DEFINITION_FIELDS = (
    "id",
    "kind",
    "status",
    "payload",
    "sig",
    "mdl_bits",
    "parent_route",
    "by",
    "born",
)
OP_STATE_FIELDS = ("evidence", "ttl", "env_hash", "blamed_by", "tried_env_hashes")
# Source: arcagi/hammer/epoch.py:444; only comb/decomp have this projection.
PROJECTION_KINDS = frozenset(("comb", "decomp"))
PROJECTION_FIELDS = ("id", "kind", "status", "by", "born", "evidence", "payload")


def check_stop() -> None:
    """Respect the user's stop switch before doing more work."""
    if (Path.home() / "arcagi-STOP").exists():
        raise RuntimeError("~/arcagi-STOP exists; stopped")


def file_kind(relative: str) -> str | None:
    """Classify a path admitted by hammer-v1."""
    parts = PurePosixPath(relative).parts
    if relative in JSON_FILES:
        return "json"
    if relative == "ops.jsonl":
        return "ops"
    if relative in FILE_STUBS:
        return "file"
    if len(parts) == 3 and parts[0] == "nodes" and parts[2] == "_metainfo.json":
        return "json"
    if len(parts) >= 2 and parts[0] == "truth" and parts[-1].endswith(".json"):
        return "json"
    return None


def inventory(root: Path) -> tuple[list[str], list[str]]:
    """List genome files and unknown files, pruning excluded runtime trees."""
    included, skipped = [], []
    for directory, dirs, files in os.walk(root, followlinks=False):
        check_stop()
        relative_dir = Path(directory).relative_to(root)
        parts = relative_dir.parts
        if not parts:
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        elif parts[0] == "nodes" and len(parts) >= 2:
            dirs[:] = []
        else:
            dirs.sort()
        for name in sorted(files):
            relative = (relative_dir / name).as_posix()
            if file_kind(relative):
                if (root / relative).is_symlink():
                    raise ValueError(f"genome file is a symlink: {relative}")
                included.append(relative)
            elif relative in EXCLUDED_FILES or (parts and parts[0] == "nodes"):
                continue
            else:
                skipped.append(relative)
    return sorted(included), sorted(skipped)


def safe_path(root: Path, relative: str) -> Path:
    """Reject absolute paths, traversal and symlinks outside the destination."""
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or not path.parts
        or any(p in (".", "..") for p in relative.split("/"))
    ):
        raise ValueError(f"invalid relative path: {relative!r}")
    result = root.joinpath(*path.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes destination: {relative!r}")
    return result


def empty_directory(path: Path) -> None:
    """Create a destination, refusing to overwrite a nonempty directory."""
    check_stop()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError(f"destination must be absent or empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
