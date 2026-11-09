"""Command-line tree export, import, diff and the three-check roundtrip."""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from arcagi.hammer.check import check_root
from arcagi.hammer.formats import ids_sha, read_json, write_json

from . import boundary
from .diff import diff_trees
from .export import _export_tree, export_tree
from .import_ import import_tree


def _snapshot(root: Path) -> dict[str, tuple[str, int]]:
    paths, _ = boundary.inventory(root)
    paths = sorted(
        set(paths)
        | {
            p.relative_to(root).as_posix()
            for p in root.glob("ops/*/_metainfo.json")
            if p.is_file()
        }
    )
    result = {}
    for relative in paths:
        boundary.check_stop()
        path = root / relative
        result[relative] = (
            hashlib.sha1(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
    return result


def _byte_reason(a: bytes, b: bytes) -> str:
    if a.rstrip(b"\r\n") == b.rstrip(b"\r\n"):
        return "trailing newline differs"
    try:
        left = [json.loads(line) for line in a.splitlines() if line.strip()]
        right = [json.loads(line) for line in b.splitlines() if line.strip()]
    except (ValueError, UnicodeDecodeError):
        try:
            left, right = json.loads(a), json.loads(b)
        except (ValueError, UnicodeDecodeError):
            return "file bytes differ"
    if left == right:
        return "JSON content equal; key order or whitespace differs"
    return "JSON content differs"


def _compare_bytes(src: Path, dest: Path, paths: dict) -> list[dict]:
    differences = []
    for relative in paths:
        boundary.check_stop()
        a, b = src / relative, dest / relative
        if not a.is_file() or not b.is_file():
            differences.append({"path": relative, "reason": "file missing"})
            continue
        left, right = a.read_bytes(), b.read_bytes()
        if hashlib.sha1(left).digest() != hashlib.sha1(right).digest():
            differences.append({"path": relative, "reason": _byte_reason(left, right)})
    return differences


def roundtrip(tree_root: str | Path, out: str | Path, accept: str | Path) -> dict:
    """Run the design's twelve steps and write only its acceptance report."""
    src, out, accept = Path(tree_root).resolve(), Path(out).resolve(), Path(accept)
    boundary.check_stop()
    if out.is_relative_to(src) or src.is_relative_to(out):
        raise ValueError("roundtrip output and live source must not overlap")
    if accept.resolve().is_relative_to(src):
        raise ValueError("accept report must not be written inside the source tree")
    boundary.empty_directory(out)
    before = _snapshot(src)
    started = time.perf_counter()
    first = export_tree(src, out)
    t_export = time.perf_counter() - started
    _export_tree(src, out, False, tree_name="tree.nodedup.json", state_name=None)
    started = time.perf_counter()
    import_tree(out / "tree.json", out / "tree2", out / "state.json")
    t_import = time.perf_counter() - started
    second = _export_tree(
        out / "tree2", out, tree_name="tree2.json", state_name="tree2.state.json"
    )
    content = diff_trees(out / "tree.json", out / "tree2.json")
    write_json(out / "diff.json", content)
    no_dedup = diff_trees(out / "tree.json", out / "tree.nodedup.json")
    state_equal = (
        read_json(out / "state.json")["ops"]
        == read_json(out / "tree2.state.json")["ops"]
    )
    import_tree(out / "tree.json", out / "tree2_nostate")
    _export_tree(
        out / "tree2_nostate", out, tree_name="tree2_nostate.json", state_name=None
    )
    no_state = diff_trees(out / "tree.json", out / "tree2_nostate.json")
    files_differ = _compare_bytes(src, out / "tree2", before)
    errors_src, errors_tree2 = check_root(src), check_root(out / "tree2")
    ids_src = read_json(src / "truth/cal/ids.json")
    ids_tree2 = read_json(out / "tree2/truth/cal/ids.json")
    frozen = read_json(src / "frozen.json")
    seals = {
        name: {
            "calc": ids_sha(ids_src[name]),
            "frozen": frozen["holdout"][name]["sha"],
            "tree2": ids_sha(ids_tree2[name]),
        }
        for name in ("H8", "H24")
    }
    after = _snapshot(src)
    p1 = {
        "n_diff": content["n_diff"],
        "n_diff_dedup_off": no_dedup["n_diff"],
        "n_diff_nostate": no_state["n_diff"],
        "state_equal": state_equal,
        "genome_sha_equal": first["genome_sha"] == second["genome_sha"],
    }
    p1["pass"] = (
        all(p1[k] == 0 for k in ("n_diff", "n_diff_dedup_off", "n_diff_nostate"))
        and state_equal
        and p1["genome_sha_equal"]
    )
    p2 = {
        "mode": "bytes",
        "files_compared": len(before),
        "files_differ": files_differ,
        "check_root_errors_src": len(errors_src),
        "check_root_errors_tree2": len(errors_tree2),
        "pass": not files_differ and len(errors_src) == len(errors_tree2),
    }
    wall_s = t_export + t_import
    p3 = {
        **seals,
        "wall_s": wall_s,
        "live_untouched": before == after,
        "pass": all(s["calc"] == s["frozen"] == s["tree2"] for s in seals.values())
        and wall_s <= 5
        and before == after,
    }
    report = {
        "schema": "think2-rt-accept/1",
        "src": str(src),
        "out": str(out),
        "at": datetime.now().astimezone().isoformat(),
        "checks": {"P1_content": p1, "P2_bytes": p2, "P3_seal_speed": p3},
        "stats": first["stats"],
        "pass": p1["pass"] and p2["pass"] and p3["pass"],
    }
    boundary.check_stop()
    write_json(accept, report)
    return report


def main(argv: list[str] | None = None) -> int:
    """Dispatch the four treegen subcommands."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("tree_root", type=Path)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--dedup", choices=("on", "off"), default="on")
    export.add_argument("--tree-name", default="tree.json")
    importer = commands.add_parser("import")
    importer.add_argument("tree_json", type=Path)
    importer.add_argument("--dest", type=Path, required=True)
    importer.add_argument("--state", type=Path)
    importer.add_argument("--files", type=Path)
    diff = commands.add_parser("diff")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)
    diff.add_argument("--ignore-op-order", action="store_true")
    diff.add_argument("--out", type=Path)
    rt = commands.add_parser("roundtrip")
    rt.add_argument("tree_root", type=Path)
    rt.add_argument("--out", type=Path, required=True)
    rt.add_argument("--accept", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        boundary.check_stop()
        if args.command == "export":
            _export_tree(
                args.tree_root, args.out, args.dedup == "on", tree_name=args.tree_name
            )
            print(args.out / args.tree_name)
        elif args.command == "import":
            print(import_tree(args.tree_json, args.dest, args.state, args.files))
        elif args.command == "diff":
            result = diff_trees(args.a, args.b, args.ignore_op_order)
            if args.out:
                write_json(args.out, result)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=1))
            return int(result["n_diff"] != 0)
        else:
            report = roundtrip(args.tree_root, args.out, args.accept)
            print(
                json.dumps(
                    {
                        "pass": report["pass"],
                        "accept": str(args.accept),
                        "out": report["out"],
                    },
                    ensure_ascii=False,
                )
            )
            return int(not report["pass"])
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"treegen: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
