"""Three isolated forgeries exercise raw verification and genome identity."""

import math
import shutil
from pathlib import Path

from arcagi.hammer.formats import read_json, read_jsonl, write_json, write_jsonl

from . import boundary, meter
from .meter_stats import B_REF, bits_table, load, score


def identity(parent: dict, control: dict, recipe: str) -> bool:
    provenance = control.get("dumb") or {}
    return (
        control["genome_sha"] != parent["genome_sha"]
        and provenance.get("parent_sha") == parent["genome_sha"]
        and provenance.get("recipe") == recipe
    )


def fake_checks(parent_dir: Path, dumb_dir: Path, out: Path) -> dict:
    """Create three isolated forgeries; raw run artifacts remain untouched."""
    boundary.check_stop()
    out.mkdir(parents=True, exist_ok=False)
    parent = load(parent_dir)
    results = {}
    for kind in ("per_task", "same_sha", "test_as_train"):
        target = out / kind
        original = parent_dir if kind == "same_sha" else dumb_dir
        shutil.copytree(
            original,
            target,
            ignore=shutil.ignore_patterns(
                "tmp", "RUN", "live", "files", "targeted-probe"
            ),
        )
        # Targeted verification needs its probe solutions, but never its tmp.
        if (original / "targeted-probe").exists():
            shutil.copytree(
                original / "targeted-probe",
                target / "targeted-probe",
                ignore=shutil.ignore_patterns("tmp", "RUN", "live"),
            )
        report = read_json(target / "meter.json")
        if kind == "per_task":
            report["per_task"] = parent["per_task"]
            report["scores"] = {
                **parent["scores"],
                "wall_s": report["scores"]["wall_s"],
            }
        elif kind == "same_sha":
            # A coherent parent run claimed as a dumb control must be refused
            # by the identity gate even though raw verification passes.
            provenance = {"recipe": "no-learn", "parent_sha": parent["genome_sha"]}
            report["dumb"] = provenance
            for name in ("source.json", meter.PREPARED):
                document = read_json(target / name)
                document["dumb"] = provenance
                write_json(target / name, document)
        else:
            # Ensure a discriminating train/test conflict even when the real
            # run happens to have no false positives. This is a fake copy only.
            path = target / "root/epochs/0/solutions.jsonl"
            rows = read_jsonl(path)
            row = next(r for r in rows if r["set"] == "L16")
            row.update(train_ok=False, test_ok=True, nodes_to_first=1)
            write_jsonl(path, rows)
            table = bits_table(target / "root", report["cfg"]["E"])
            for item in table.values():
                item["train_ok"] = item["test_ok"][:]
                item["b"] = [
                    math.log2(B_REF) - math.log2(min(n or 1, B_REF)) if ok else 0.0
                    for n, ok in zip(item["ntf"], item["test_ok"], strict=True)
                ]
            report["per_task"] = table
            report["scores"] = score(table, wall_s=report["scores"]["wall_s"])
        write_json(target / "meter.json", report)
        verdict = meter.verify(target)
        identity_ok = (
            identity(parent, report, "no-learn") if kind == "same_sha" else True
        )
        results[kind] = {
            "rejected": not verdict["pass"] or not identity_ok,
            "identity_ok": identity_ok,
            "verify": verdict,
            "run_dir": str(target),
        }
    return {"pass": all(r["rejected"] for r in results.values()), "checks": results}
