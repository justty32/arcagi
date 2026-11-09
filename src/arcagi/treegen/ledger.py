"""Offline epochs 0..8 ledger generation and independent acceptance checks."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from arcagi.hammer.formats import read_json, read_jsonl, write_json, write_jsonl

from . import boundary, cost, credit, guards, health

EPOCHS = list(range(9))


def snapshot(root: Path) -> dict[str, str]:
    """SHA256 every file, including runtime data excluded by genome export."""
    result = {}
    for path in sorted(root.rglob("*")):
        boundary.check_stop()
        if path.is_symlink():
            raise ValueError(f"source snapshot refuses symlinks: {path}")
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            result[path.relative_to(root).as_posix()] = digest.hexdigest()
    if not result:
        raise ValueError(f"empty or missing source tree: {root}")
    return result


def _destination(root: Path, path: Path) -> Path:
    path = path.resolve()
    if path.is_relative_to(root) or root.is_relative_to(path):
        raise ValueError("ledger output/report and source tree must not overlap")
    return path


def _read(directory: Path, name: str) -> dict | list:
    path = directory / name
    if not path.is_file():
        raise ValueError(f"missing ledger artifact: {name}")
    return read_jsonl(path) if name.endswith(".jsonl") else read_json(path)


def _reference(root: Path) -> tuple[dict, dict, list, list, dict, dict, list]:
    meter = health.load_script("think1_meter")
    if meter.completed_epochs(root) != EPOCHS:
        raise ValueError("block 3 requires completed epochs exactly 0..8")
    summary = meter.summarize(root)
    curves = cost.curves(root, EPOCHS)
    deltas = credit.amounts(curves)
    audit = health.load_script("think1_audit")
    rows, totals, attribution = credit.build(root, deltas, audit.block_refs)
    card, suggestions = health.summarize(root, EPOCHS[-1], EPOCHS)
    return (
        summary,
        deltas,
        cost.records(curves),
        rows,
        totals,
        attribution,
        [card, suggestions],
    )


def generate(tree_root: str | Path, out: str | Path, rates: str | Path) -> dict:
    """Write an isolated ledger plus a snapshot/rates provenance sidecar."""
    boundary.check_stop()
    root = Path(tree_root).resolve()
    dest = _destination(root, Path(out))
    selected_rates = read_json(Path(rates))
    errors = cost.validate(selected_rates, rates=True)
    if errors:
        raise ValueError("; ".join(errors))
    before = snapshot(root)
    summary, deltas, costs, rows, totals, attribution, (card, suggestions) = _reference(
        root
    )
    boundary.empty_directory(dest)
    artifacts = {
        "cost.jsonl": costs,
        "credit.jsonl": rows,
        "by_subtree.json": totals,
        "health.json": card,
        "retire_suggest.jsonl": suggestions,
    }
    for name, payload in artifacts.items():
        boundary.check_stop()
        writer = write_jsonl if name.endswith(".jsonl") else write_json
        writer(dest / name, payload)
    after = snapshot(root)
    meta = {
        "schema": "t2-ledger-meta/1",
        "tree_root": str(root),
        "epochs": EPOCHS,
        "rates": selected_rates,
        "rates_file": str(Path(rates).resolve()),
        "sha256_before": before,
        "sha256_after": after,
        "amounts": deltas,
        "attribution": attribution,
        "prices": {
            row["epoch"]: cost.price(row["cost"], selected_rates) for row in costs
        },
        "meter": {key: summary[key] for key in ("cost", "eff", "auc_L")},
        "limitations": [
            "Non-comb live ops use terminal status and born.epoch as a proxy.",
            "Credit uses epoch solutions, excluding terminal evidence/blamed_by.",
            "Negative deltas use the same split; efficacy is unproven.",
            "Costs are hammer-level only; missing token counts are not invented.",
        ],
    }
    boundary.check_stop()
    write_json(dest / "ledger_meta.json", meta)
    return {
        "out": str(dest),
        "files": len(artifacts) + 1,
        "cost_rows": len(costs),
        "credit_rows": len(rows),
        "source_unchanged": before == after,
        "legacy_price": sum(
            cost.price(row["cost"], cost.LEGACY_RATES) for row in costs
        ),
        "amount_sum": sum(deltas.values()),
    }


def _regression() -> dict:
    """Run the requested regression suite without caches, plus the repo guard."""
    boundary.check_stop()
    started = time.monotonic()
    env = {
        **os.environ,
        "PYTHONPATH": str(health.REPO / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/treegen",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=health.REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        while True:
            boundary.check_stop()
            try:
                output, _ = process.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started >= 55:
                    raise ValueError("treegen regression exceeded 55 seconds")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
    gate = guards.thresholds()
    errors = []
    if process.returncode:
        errors.append(f"pytest exit={process.returncode}: {output[-4000:]}")
    if gate["status"] != "PASS":
        errors.append(f"guard-thr FAIL: {json.dumps(gate, ensure_ascii=False)}")
    passed = re.search(r"(\d+) passed", output)
    return {
        "pass": not errors,
        "pytest_exit": process.returncode,
        "tests_passed": int(passed[1]) if passed else 0,
        "guard_status": gate["status"],
        "guard_missing": len(gate["unregistered"]),
        "wall_s": time.monotonic() - started,
        "errors": errors,
    }


def _checked(callback) -> dict:
    boundary.check_stop()
    try:
        return callback()
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        return {"pass": False, "errors": [str(exc)]}


def check(
    directory: str | Path, tree_root: str | Path, accept: str | Path | None = None
) -> dict:
    """Recompute checks from source/artifacts; never trust saved pass flags."""
    boundary.check_stop()
    root, directory = Path(tree_root).resolve(), Path(directory).resolve()
    report_path = _destination(root, Path(accept)) if accept is not None else None
    start = snapshot(root)
    summary, deltas, expected_costs, expected_credit, _, _, (card, suggestions) = (
        _reference(root)
    )
    checks = {}

    def conserved() -> tuple[dict, dict]:
        return credit.check(
            _read(directory, "credit.jsonl"),
            expected_credit,
            _read(directory, "by_subtree.json"),
            deltas,
        )

    checks["C2"] = _checked(lambda: conserved()[0])
    checks["C3"] = _checked(lambda: conserved()[1])
    checks["C4"] = _checked(
        lambda: cost.check_legacy(
            _read(directory, "cost.jsonl"),
            expected_costs,
            summary,
            _read(directory, "credit.jsonl"),
        )
    )
    checks["C5"] = _checked(
        lambda: cost.check_open(
            _read(directory, "cost.jsonl"),
            _read(directory, "ledger_meta.json")["rates"],
        )
    )
    checks["C6"] = _checked(
        lambda: health.check(
            _read(directory, "health.json"),
            _read(directory, "retire_suggest.jsonl"),
            card,
            suggestions,
        )
    )
    checks["C7"] = _checked(_regression)

    def unchanged() -> dict:
        meta = _read(directory, "ledger_meta.json")
        end = snapshot(root)
        snapshots = [meta["sha256_before"], meta["sha256_after"], start, end]
        paths = set().union(*(set(s) for s in snapshots))
        differing = sorted(p for p in paths if len({s.get(p) for s in snapshots}) != 1)
        valid = (
            meta["schema"] == "t2-ledger-meta/1"
            and meta["tree_root"] == str(root)
            and meta["epochs"] == EPOCHS
        )
        return {
            "pass": valid and not differing,
            "files": len(paths),
            "files_differ": len(differing),
            "hash": "sha256",
            "errors": (["invalid ledger provenance"] if not valid else []) + differing,
        }

    checks["C1"] = _checked(unchanged)
    checks = dict(sorted(checks.items()))
    result = {
        "schema": "t2-ledger-accept/1",
        "tree_root": str(root),
        "ledger": str(directory),
        "checks": checks,
        "pass": all(item["pass"] for item in checks.values()),
    }
    boundary.check_stop()
    if report_path is not None:
        write_json(report_path, result)
    return result
