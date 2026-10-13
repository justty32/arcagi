"""Write raw experiment JSON/CSV, summary CSV, and the standalone report."""

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .report_html import _render_html
from .statistics import summarize_runs

SUMMARY_FIELDS = (
    "scope",
    "group",
    "solver",
    "runs_total",
    "runs_correct",
    "run_accuracy",
    "tests_total",
    "tests_correct",
    "test_accuracy",
    "errors",
    "elapsed_mean_seconds",
    "elapsed_median_seconds",
)

RUN_FIELDS = (
    "solver",
    "task_id",
    "tags",
    "seed",
    "repeat",
    "params",
    "correct",
    "tests_total",
    "tests_correct",
    "elapsed_seconds",
    "error",
    "artifact_dir",
    "returncode",
    "predictions",
)


def _csv_value(value: Any) -> Any:
    """Quote spreadsheet-formula prefixes without altering raw JSON records."""
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, str) and (
        value.lstrip().startswith(("=", "+", "-", "@"))
        or value.startswith(("\t", "\r", "\n"))
    ):
        return "'" + value
    return value


def _write_csv(path: Path, fields: tuple[str, ...], rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def write_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Write raw JSON/CSV and aggregated CSV/HTML without changing run records."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    summary = summarize_runs(report["runs"])
    paths = {
        name: directory / name
        for name in (
            "results.json",
            "results.csv",
            "summary.csv",
            "report.html",
        )
    }
    paths["results.json"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["results.csv"], RUN_FIELDS, report["runs"])
    _write_csv(paths["summary.csv"], SUMMARY_FIELDS, summary)
    paths["report.html"].write_text(_render_html(report, summary), encoding="utf-8")
    return {name: str(path) for name, path in paths.items()}
