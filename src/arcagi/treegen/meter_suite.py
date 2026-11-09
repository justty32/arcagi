"""Bounded subprocess batches and adversarial meter acceptance."""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from arcagi.hammer.formats import read_json, write_json

from . import boundary, dumb, meter
from .meter_fake import fake_checks
from .meter_fake import identity as _identity
from .meter_stats import compare, load, sign_test

T4B_LABELS = ("parent-1", "parent-2", *(r for r in dumb.RECIPES if r != "no-learn-all"))
T4C_LABELS = ("parent-1", "parent-2", "no-learn-all", "no-learn", "null")
LABELS = ("parent-1", "parent-2", *dumb.RECIPES)


def _worker(job: dict, taskset: Path, cfg: dict, log: Path) -> dict:
    boundary.check_stop()
    argv = [
        sys.executable,
        "-m",
        "arcagi.treegen.cli",
        "meter",
        job["tree_json"],
        "--run-dir",
        job["run_dir"],
        "--taskset",
        str(taskset),
        "--L",
        str(cfg["L"]),
        "--epochs",
        str(cfg["E"]),
        "--strip",
        cfg["strip"],
        "--threads",
        "1",
    ]
    env = {
        **os.environ,
        **dict.fromkeys(
            ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"), "1"
        ),
    }
    with log.open("x") as output:
        process = subprocess.Popen(
            argv,
            stdout=output,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        try:
            while process.poll() is None:
                boundary.check_stop()
                time.sleep(0.2)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
    return {
        **job,
        "returncode": process.returncode,
        "log": str(log),
        "verify": meter.verify(job["run_dir"]),
    }


def batch(
    parent: str | Path,
    taskset: str | Path,
    out: str | Path,
    *,
    jobs: int = 4,
    base_dir: str | Path = meter.RUN_BASE,
    L: int = 50_000,  # noqa: N803 - Public meter budget name.
    epochs: int = 4,
    strip: str = "all",
    labels: Sequence[str] | None = None,
) -> dict:
    """Run selected labels in one-thread processes; default to the t4b suite."""
    boundary.check_stop()
    if not 1 <= jobs <= 4:
        raise ValueError("meter-batch jobs must be between 1 and 4")
    labels = list(T4B_LABELS if labels is None else labels)
    if not labels or len(set(labels)) != len(labels) or not set(labels) <= set(LABELS):
        raise ValueError("batch labels must be nonempty, unique and known")
    parent, taskset, out = Path(parent).resolve(), Path(taskset).resolve(), Path(out)
    if out.exists():
        raise ValueError(f"batch manifest already exists: {out}")
    # Validate all options before starting any process.
    selected = read_json(taskset)
    ids = selected if isinstance(selected, list) else selected["task_ids"]
    if not ids or not set(ids) <= set(meter.source_tasks(parent)):
        raise ValueError("invalid batch taskset")
    if L <= 0 or epochs < 0 or strip not in ("all", "targeted"):
        raise ValueError("invalid batch budget/strip")
    suite = meter.fresh_run("suite", read_json(parent)["genome_sha"], base_dir)
    suite.mkdir(parents=True, exist_ok=False)
    sources = {}
    for label in labels:
        if label.startswith("parent-"):
            sources[label] = parent
        else:
            target = suite / "genomes" / label / "tree.json"
            dumb.make(parent, label, target)
            sources[label] = target
    plan = [
        {
            "label": label,
            "tree_json": str(src),
            "run_dir": str(
                meter.fresh_run(label, read_json(src)["genome_sha"], base_dir)
            ),
        }
        for label, src in sources.items()
    ]
    cfg = {"L": L, "E": epochs, "strip": strip}
    report = {
        "schema": "think4-batch/1",
        "jobs": jobs,
        "threads": 1,
        "cfg": cfg,
        "runs": plan,
        "pass": False,
    }
    write_json(out, report)
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [
            executor.submit(_worker, job, taskset, cfg, suite / f"{job['label']}.log")
            for job in plan
        ]
        results = []
        for job, future in zip(plan, futures, strict=True):
            try:
                results.append(future.result())
            except (OSError, RuntimeError, ValueError) as exc:
                results.append({**job, "returncode": 1, "error": str(exc)})
    report["runs"] = results
    report["pass"] = all(r["returncode"] == 0 and r["verify"]["pass"] for r in results)
    write_json(out, report)
    return report


def accept(
    manifest: str | Path,
    out: str | Path,
    *,
    fake: bool = False,
    fake_dir: str | Path | None = None,
    criterion: str = "t4b",
) -> dict:
    """Apply every acceptance gate; a missing/invalid run makes the report red."""
    boundary.check_stop()
    if criterion not in ("t4b", "t4c"):
        raise ValueError("criterion must be t4b or t4c")
    manifest, out = Path(manifest), Path(out)
    checks, comparisons, errors = {}, {}, []
    sign_tests, report_only = {}, {}
    data = read_json(manifest)
    directories, runs = {}, {}
    try:
        rows = data["runs"]
        if len({r["label"] for r in rows}) != len(rows):
            raise ValueError("duplicate batch label")
        directories = {r["label"]: Path(r["run_dir"]).resolve() for r in rows}
        required = set(T4C_LABELS if criterion == "t4c" else T4B_LABELS)
        if set(directories) != required or len(set(directories.values())) != len(
            required
        ):
            raise ValueError(
                f"need {len(required)} independent run directories with all labels"
            )
        verification = {k: meter.verify(p) for k, p in directories.items()}
        checks["raw_verify"] = verification
        if not all(v["pass"] for v in verification.values()):
            raise ValueError("one or more raw verifications failed")
        runs = {k: load(p) for k, p in directories.items()}
        parent, repeat = runs["parent-1"], runs["parent-2"]
        for label, other in runs.items():
            if label != "parent-1":
                comparisons[label] = {
                    m: compare(parent, other, m) for m in ("gain_bits", "base_bits")
                }
        pcomp = comparisons["parent-2"]
        checks["repeat"] = (
            parent["genome_sha"] == repeat["genome_sha"]
            and all(
                parent["per_task"][t]["b"] == repeat["per_task"][t]["b"]
                for t in parent["task_ids"]
            )
            and all(c["delta"] == 0 and not c["significant"] for c in pcomp.values())
        )
        recipes = [r for r in dumb.RECIPES if r in runs]
        checks["identity"] = {r: _identity(parent, runs[r], r) for r in recipes}
        checks["null"] = all(not c["significant"] for c in comparisons["null"].values())
        checks["taskset_size"] = len(parent["task_ids"]) >= 16
        # An all-equal negative difference follows the specified sigma=0 rule.
        checks["learning_drop"] = any(
            comparisons[r]["gain_bits"]["significant"]
            and comparisons[r]["gain_bits"]["delta"] < 0
            for r in dumb.RECIPES[:3]
            if r in runs
        )
        if criterion == "t4c":
            control = runs["no-learn-all"]
            checks["control_clean"] = abs(control["scores"]["gain_bits"]) < 1
            sign_tests = {
                r: sign_test(parent, runs[r]) for r in ("no-learn-all", "null")
            }
            drop, null = sign_tests["no-learn-all"], sign_tests["null"]
            checks["learning_drop"] = (
                drop["p_neg"] <= 0.05
                and drop["delta"] <= -2
                and all(h < 0 for h in drop["halves"])
            )
            checks["null"] = checks["null"] and (
                null["delta"] == 0 or null["p_neg"] > 0.05
            )
            report_only = {
                "no-learn": {
                    "sign_test": sign_test(parent, runs["no-learn"]),
                    "compare": comparisons["no-learn"],
                },
                "no-learn-all_vs_no-learn": {
                    "sign_test": sign_test(runs["no-learn"], control),
                },
            }
            if not checks["control_clean"]:
                errors.append("control_clean failed: 對照不乾淨")
        checks["recipes"] = {}
        for recipe in recipes:
            if recipe not in (*dumb.RECIPES[:3], "no-learn-all"):
                continue
            g = runs[recipe]["gates"]
            effective = g["promotes"] == 0 and (
                recipe == "judge-block" or g["new_ops"] == 0
            )
            if recipe == "no-learn-all":
                effective = effective and g.get("freeze_uses") is True
            checks["recipes"][recipe] = {
                "inert": not effective,
                "promotes": g["promotes"],
                "new_ops": g["new_ops"],
            }
        if not all(checks["identity"].values()):
            errors.append("dumb genome identity failed")
        if any(v["inert"] for v in checks["recipes"].values()):
            errors.append("a replacement recipe is inert")
        for name in ("repeat", "null", "taskset_size", "learning_drop"):
            if not checks[name]:
                errors.append(f"{name} failed")
        if fake:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            fake_out = Path(fake_dir) if fake_dir else out.parent / f"fakes_{stamp}"
            checks["fake"] = fake_checks(
                directories["parent-1"], directories["no-learn"], fake_out
            )
            if not checks["fake"]["pass"]:
                errors.append("a fake was not rejected")
        else:
            errors.append("--fake required for full acceptance")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(str(exc))
    report = {
        "schema": "think4-accept/1",
        "criterion": criterion,
        "pass": not errors,
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "comparisons": comparisons,
        "sign_tests": sign_tests,
        "report_only": report_only,
        "checks": checks,
        "manifest": str(manifest),
    }
    boundary.check_stop()
    write_json(out, report)
    return report
