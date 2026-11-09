"""Independent scratch forgeries exercising the real ga-check CLI."""

import copy
import json
from pathlib import Path

from arcagi.hammer.formats import read_json, write_json

from . import boundary, check, genome

REPORT = genome.REPORTS / "b4/fake.json"
CASES = (
    "eff",
    "born",
    "budget",
    "truth",
    "dangling_ref",
    "genome_sha",
    "priority",
    "leak",
)


def run(out: str | Path) -> dict:
    """Make each forgery separately, record its actual exit and structured errors."""
    from .cli import main

    boundary.check_stop()
    out = genome.destination(out)
    parent = genome.PARENT
    baseline = check.check(parent, parent)
    if not baseline["ok"]:
        raise ValueError(
            "ga-fake requires a valid parent: " + "; ".join(baseline["errors"])
        )
    boundary.empty_directory(out)
    results = {}
    for case in CASES:
        boundary.check_stop()
        doc = read_json(parent)
        tree = genome.expanded(doc)
        fit = None
        if case == "born":
            tree["ops.jsonl"][0]["born"]["epoch"] += 1
        elif case == "budget":
            tree["frozen.json"]["budgets"]["L"] += 1
        elif case == "truth":
            tree["truth"]["train"]["taskset.json"]["L16"][0] += "_forged"
        elif case == "priority":
            next(o for o in tree["ops.jsonl"] if o["kind"] == "route")["payload"][
                "priority"
            ] = 999
        elif case == "leak":
            op = copy.deepcopy(
                next(o for o in tree["ops.jsonl"] if o["kind"] == "comb")
            )
            op["id"] = "comb_fake_leak"
            op["payload"]["src_tasks"] = [
                tree["truth"]["train"]["taskset.json"]["P"][0]
            ]
            tree["ops.jsonl"].append(op)
        elif case == "dangling_ref":
            tree["frozen.json"]["judge"] = {"$ref": "#/defs/deadbeef0000"}
        directory = out / case
        if case == "dangling_ref":
            # Interning is inappropriate for a deliberately invalid reference.
            doc = {**doc, "defs": {}, "tree": tree}
        else:
            doc = genome.pack(doc, tree)
        doc = genome.write(directory / "tree.json", doc, parent.parent / "files")
        if case == "genome_sha":
            doc["genome_sha"] = "000000000000"
            write_json(directory / "tree.json", doc)
        if case == "eff":
            # Synthetic C25 evidence is local to this forgery, never a real score.
            measured = {
                "schema": "think2-quick/1",
                "genome_sha": doc["genome_sha"],
                "auc_L": 1,
                "cost": 1000000,
                "eff": 1.0,
                "wall_s": 0.01,
                "cfg": {"L": 25000, "epochs": 4, "clear_p": True, "threads": 4},
                "per_task": {"fake": {"auc": 1, "solved": [1, 0, 0, 0]}},
            }
            write_json(directory / "quick/quick.json", measured)
            fit = directory / "fit.json"
            write_json(fit, {**measured, "check": baseline, "eff": 123.0})
        # CLI and direct API must agree. The positive baseline above prevents
        # a broken always-failing validator from making this suite pass.
        args = ["ga-check", str(directory / "tree.json"), "--parent", str(parent)]
        if fit:
            args.extend(["--fit", str(fit)])
        code = main(args)
        checked = check.ga_check(directory / "tree.json", parent, fit=fit)
        expected = {
            "eff": "fitness:eff",
            "born": "immutable:",
            "budget": "immutable:",
            "truth": "immutable:",
            "dangling_ref": "dangling_ref:",
            "genome_sha": "genome_sha:",
            "priority": "bounds:",
            "leak": "alien_op:",
        }[case]
        rejected = (
            code == 1
            and not checked["ok"]
            and any(e.startswith(expected) for e in checked["errors"])
        )
        results[case] = {
            "exit": code,
            "status": "FAIL" if not checked["ok"] else "PASS",
            "errors": checked["errors"],
            "rejected": rejected,
            "tree": str(directory / "tree.json"),
        }
    report = {
        "schema": "think2-ga-fake/1",
        "baseline_ok": baseline["ok"],
        "cases": results,
        "pass": all(r["rejected"] for r in results.values()),
        "n_rejected": sum(r["rejected"] for r in results.values()),
    }
    boundary.check_stop()
    write_json(REPORT, report)
    print(json.dumps({"fake_report": str(REPORT), "rejected": report["n_rejected"]}))
    return report
