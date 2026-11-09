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
    quick = commands.add_parser("quick")
    quick.add_argument("tree_json", type=Path, nargs="?")
    quick.add_argument("--from-root", type=Path)
    quick.add_argument("--state", type=Path)
    quick.add_argument("--dest", type=Path, required=True)
    quick.add_argument("--L", type=int, required=True)
    quick.add_argument("--epochs", type=int, required=True)
    quick.add_argument("--threads", type=int, default=4)
    quick.add_argument("--no-clear-p", action="store_true")
    noise = commands.add_parser("noise")
    noise.add_argument("dirs", nargs="+", type=Path)
    noise.add_argument("--out", type=Path, required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("a", type=Path)
    compare.add_argument("b", type=Path)
    compare.add_argument("--out", type=Path, required=True)
    ledger = commands.add_parser("ledger")
    ledger.add_argument("tree_root", type=Path)
    ledger.add_argument("--out", type=Path, required=True)
    ledger.add_argument("--rates", type=Path, required=True)
    ledger_check = commands.add_parser("ledger-check")
    ledger_check.add_argument("directory", type=Path)
    ledger_check.add_argument("--tree", type=Path, required=True)
    ledger_check.add_argument("--accept", type=Path)
    leak = commands.add_parser("guard-leak")
    leak.add_argument("target", type=Path)
    leak.add_argument("--state", type=Path)
    leak.add_argument("--forbid-root", type=Path)
    leak.add_argument("--base-ops", type=Path)
    leak.add_argument("--out", type=Path)
    thresholds = commands.add_parser("guard-thr")
    thresholds.add_argument("--scan", type=Path, nargs="+")
    thresholds.add_argument("--registry", type=Path)
    thresholds.add_argument("--init", action="store_true")
    thresholds.add_argument("--out", type=Path)
    ga = commands.add_parser("ga")
    ga.add_argument("--parent", type=Path, required=True)
    ga.add_argument("--pop", type=int, default=8)
    ga.add_argument("--gens", type=int, default=1)
    ga.add_argument("--out", type=Path, required=True)
    ga.add_argument("--seed", type=int, default=0)
    ga.add_argument("--ledger", type=Path, required=True)
    ga.add_argument("--threads", type=int, default=4)
    ga.add_argument("--accept", type=Path)
    ga_check = commands.add_parser("ga-check")
    ga_check.add_argument("tree_json", type=Path)
    ga_check.add_argument("--parent", type=Path, action="append", required=True)
    ga_check.add_argument("--fit", type=Path)
    ga_check.add_argument("--quick", type=Path)
    ga_fake = commands.add_parser("ga-fake")
    ga_fake.add_argument("--out", type=Path, required=True)
    from . import meter_cli

    meter_cli.add_commands(commands)
    args = parser.parse_args(argv)
    try:
        boundary.check_stop()
        if args.command in meter_cli.COMMANDS:
            return meter_cli.dispatch(args)
        if args.command in ("ga", "ga-check", "ga-fake"):
            return _block4(args)
        if args.command in ("ledger", "ledger-check"):
            return _block3(args)
        if args.command in ("quick", "noise", "compare", "guard-leak", "guard-thr"):
            return _block2(args)
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


def _block2(args: argparse.Namespace) -> int:
    """Dispatch additive block-2 commands without changing legacy paths."""
    from . import guards, noise, quick

    code = 0
    if args.command == "quick":
        if (args.tree_json is None) == (args.from_root is None):
            raise ValueError("quick requires either tree.json or --from-root")
        if not 1 <= args.threads <= 4:
            raise ValueError("quick threads must be between 1 and 4")
        quick.prepare(
            args.tree_json or args.from_root,
            args.dest,
            state=args.state,
            L=args.L,
            epochs=args.epochs,
            clear_p=not args.no_clear_p,
        )
        result = quick.run(args.dest, epochs=args.epochs, threads=args.threads)
    elif args.command == "noise":
        result = noise.noise(args.dirs)
        code = int(not result["deterministic"])
    elif args.command == "compare":
        result = noise.compare(args.a, args.b)
    elif args.command == "guard-leak":
        kwargs = {"forbid_root": args.forbid_root} if args.forbid_root else {}
        result = guards.leak(
            args.target, state=args.state, base_ops=args.base_ops, **kwargs
        )
        code = int(result["status"] != "PASS")
    else:
        kwargs = {"registry": args.registry} if args.registry else {}
        result = guards.thresholds(args.scan, init=args.init, **kwargs)
        code = int(result["status"] != "PASS")
    boundary.check_stop()
    if getattr(args, "out", None):
        write_json(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return code


def _block3(args: argparse.Namespace) -> int:
    """Dispatch offline block-3 ledger commands."""
    from . import ledger

    if args.command == "ledger":
        result = ledger.generate(args.tree_root, args.out, args.rates)
        code = int(not result["source_unchanged"])
    else:
        result = ledger.check(args.directory, args.tree, args.accept)
        code = int(not result["pass"])
        for name, item in result["checks"].items():
            if not item["pass"]:
                print(f"{name} FAIL: {'; '.join(item['errors'])}", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return code


def _block4(args: argparse.Namespace) -> int:
    """Dispatch additive block-4 generation and adversarial checks."""
    from . import check, ga, ga_fake

    if args.command == "ga":
        result = ga.run(
            args.parent,
            args.out,
            args.ledger,
            pop=args.pop,
            gens=args.gens,
            seed=args.seed,
            threads=args.threads,
            accept=args.accept,
        )
        code = int(not result["pass"])
    elif args.command == "ga-check":
        result = check.ga_check(
            args.tree_json, args.parent, fit=args.fit, quick_dir=args.quick
        )
        code = int(not result["ok"])
        for error in result["errors"]:
            print(f"ga-check FAIL: {error}", file=sys.stderr)
    else:
        result = ga_fake.run(args.out)
        code = int(not result["pass"])
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
