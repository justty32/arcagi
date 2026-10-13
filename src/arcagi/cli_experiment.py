"""CLI adapter for file-based experiments and their persistent reports."""

import argparse
import json
import sys
from contextlib import redirect_stdout


def run_experiment_command(args: argparse.Namespace) -> int:
    """Run all selected jobs, write reports, and expose failures through exit status."""
    from arcagi.experiments import run_experiment
    from arcagi.experiments.report import write_report

    with redirect_stdout(sys.stderr):
        report = run_experiment(
            args.config, args.output, task_ids=args.task_ids, tags=args.tags
        )
        write_report(report, args.output)
    summary = {
        "schema": report["schema"],
        "output": str(args.output),
        "runs_total": len(report["runs"]),
        "errors": report["errors"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if report["errors"] else 0
