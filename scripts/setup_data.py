"""Initialize and verify pinned public ARC-AGI-1 data and RE-ARC sources."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_REVISION = "399030444e0ab0cc8b4e199870fb20b863846f34"


def check_repository(directory: Path, expected_revision: str) -> str:
    """Check the actual submodule root, pinned revision, and pristine files."""
    top = subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"], text=True
    ).strip()
    if Path(top).resolve() != directory.resolve():
        raise ValueError(f"Submodule is not initialized: {directory}")
    revision = subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != expected_revision:
        raise ValueError(f"Dataset revision mismatch in {directory.name}: {revision}")
    status = subprocess.check_output(
        ["git", "-C", str(directory), "status", "--porcelain"], text=True
    ).strip()
    if status:
        raise ValueError(f"Source repository has local modifications: {directory}")
    return revision


def initialize_rearc(source: dict) -> None:
    """Fetch only six pinned RE-ARC files, excluding the large example ZIP."""
    directory = ROOT / "vendor" / "re-arc"
    if not (directory / ".git").exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                "--depth",
                "1",
                source["repository"] + ".git",
                str(directory),
            ],
            check=True,
        )
    else:
        # Never reset an existing checkout or discard its working changes.
        check_repository(directory, source["revision"])
    subprocess.run(
        [
            "git",
            "-C",
            str(directory),
            "fetch",
            "--depth",
            "1",
            "origin",
            source["revision"],
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(directory),
            "sparse-checkout",
            "set",
            "--no-cone",
            *("/" + name for name in source["files"]),
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(directory), "checkout", "--detach", source["revision"]],
        check=True,
    )
    subprocess.run(
        ["git", "submodule", "init", "--", "vendor/re-arc"], cwd=ROOT, check=True
    )
    subprocess.run(
        ["git", "submodule", "absorbgitdirs", "vendor/re-arc"], cwd=ROOT, check=True
    )


def main() -> int:
    """Initialize official data unless --check is supplied, then verify sources."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify locally; do not download"
    )
    args = parser.parse_args()
    source = json.loads((ROOT / "vendor" / "re-arc-source.json").read_text())
    if not args.check:
        subprocess.run(
            ["git", "submodule", "update", "--init", "--", "data/ARC-AGI"],
            cwd=ROOT,
            check=True,
        )
        initialize_rearc(source)
    official = ROOT / "data" / "ARC-AGI"
    revision = check_repository(official, OFFICIAL_REVISION)
    check_repository(ROOT / "vendor" / "re-arc", source["revision"])
    sys.path.insert(0, str(ROOT / "src"))
    from arcagi.generation.sources import verify_sources
    from arcagi.tasks import load_task

    counts = {}
    for split in ("training", "evaluation"):
        paths = sorted((official / "data" / split).glob("*.json"))
        if len(paths) != 400:
            raise ValueError(f"Expected 400 {split} tasks, found {len(paths)}")
        for path in paths:
            load_task(path, require_test_outputs=True)
        counts[split] = len(paths)
    source = verify_sources()
    print(
        json.dumps(
            {
                "official_revision": revision,
                "counts": counts,
                "re_arc_revision": source["revision"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Data setup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
