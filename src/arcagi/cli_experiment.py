"""CLI adapters for file-based experiments, reports, and comparisons."""

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


def run_compare_command(args: argparse.Namespace) -> int:
    """Compare reports task by task; write JSON/CSV files and print a summary."""
    from pathlib import Path

    from arcagi.experiments.compare import (
        compare_reports,
        render_markdown,
        write_matrix_csv,
    )
    from arcagi.experiments.labels import load_labels

    inputs = {Path(spec.partition("=")[2] or spec).resolve() for spec in args.reports}
    inputs |= {Path(spec).resolve() for spec in args.reports}
    for output in (args.output, args.matrix_csv):
        if output is not None and output.resolve() in inputs:
            raise ValueError("Output must not overwrite an input report")
    labels = None
    if args.labels is not None:
        labels = load_labels(
            args.labels, column=args.label_column, separator=args.label_sep
        )
    comparison = compare_reports(args.reports, labels)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(comparison, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.matrix_csv is not None:
        args.matrix_csv.parent.mkdir(parents=True, exist_ok=True)
        write_matrix_csv(comparison, args.matrix_csv)
    if args.format == "markdown":
        print(render_markdown(comparison), end="")
    else:
        summary = {
            key: comparison[key]
            for key in ("schema", "solved_rule", "baseline", "methods", "categories")
        }
        summary["changes"] = comparison["changes"]
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0
