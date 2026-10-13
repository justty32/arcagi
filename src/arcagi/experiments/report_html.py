"""Render experiment comparisons as standalone HTML with inline SVG."""

from collections.abc import Iterable
from html import escape
from typing import Any


def _table(headers: list[str], rows: Iterable[list[str]]) -> str:
    head = "".join(f'<th scope="col">{escape(value)}</th>' for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return (
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _accuracy_chart(solvers: list[dict[str, Any]]) -> str:
    """Draw even zero scores explicitly, with escaped solver labels."""
    height = max(90, 50 + 44 * len(solvers))
    parts = [
        f'<svg viewBox="0 0 900 {height}" role="img" '
        'aria-labelledby="chart-title chart-description">',
        '<title id="chart-title">逐次實驗成功率 / Run accuracy by solver</title>',
        '<desc id="chart-description">Correct task runs divided by all task runs; '
        "errors and timeouts count as unsuccessful runs.</desc>",
    ]
    for index, row in enumerate(solvers):
        y = 25 + 44 * index
        label = escape(row["solver"])
        accuracy = row["run_accuracy"]
        parts.extend(
            [
                f'<text x="0" y="{y + 18}">{label}</text>',
                f'<rect class="track" x="290" y="{y}" width="480" height="26"/>',
                f'<rect class="bar" x="290" y="{y}" '
                f'width="{480 * accuracy:.2f}" height="26"/>',
                f'<text x="785" y="{y + 18}">{accuracy:.1%}</text>',
            ]
        )
    parts.append("</svg>")
    return "".join(parts)


def _render_html(report: dict[str, Any], summary: list[dict[str, Any]]) -> str:
    solvers = [row for row in summary if row["scope"] == "solver"]
    comparison = _table(
        ["Solver", "Correct / runs", "逐次成功率", "Errors", "Mean s", "Median s"],
        [
            [
                row["solver"],
                f"{row['runs_correct']}/{row['runs_total']}",
                f"{row['run_accuracy']:.1%}",
                str(row["errors"]),
                f"{row['elapsed_mean_seconds']:.4f}",
                f"{row['elapsed_median_seconds']:.4f}",
            ]
            for row in solvers
        ],
    )
    solver_names = [row["solver"] for row in solvers]
    task_rows = {
        (row["group"], row["solver"]): row for row in summary if row["scope"] == "task"
    }
    matrix = []
    for task_id in sorted({key[0] for key in task_rows}):
        cells = [task_id]
        for solver in solver_names:
            row = task_rows.get((task_id, solver))
            cells.append(
                f"{row['run_accuracy']:.1%} ({row['runs_correct']}/{row['runs_total']})"
                if row
                else "—"
            )
        matrix.append(cells)
    tasks = _table(["Task", *solver_names], matrix)
    tags = _table(
        ["Tag", "Solver", "Correct / runs", "Accuracy", "Errors", "Mean s", "Median s"],
        [
            [
                row["group"],
                row["solver"],
                f"{row['runs_correct']}/{row['runs_total']}",
                f"{row['run_accuracy']:.1%}",
                str(row["errors"]),
                f"{row['elapsed_mean_seconds']:.4f}",
                f"{row['elapsed_median_seconds']:.4f}",
            ]
            for row in summary
            if row["scope"] == "tag"
        ],
    )
    config = escape(str(report.get("config_path", "")))
    chart = _accuracy_chart(solvers)
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARC-AGI experiment report</title><style>
body {{ font-family:system-ui,sans-serif; max-width:1200px; margin:auto;
  padding:24px; background:#10151d; color:#e9edf3; }}
h1,h2 {{ color:#b8dcff; }} p {{ line-height:1.6; }}
.scroll {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; }}
th,td {{ padding:10px; text-align:left; border-bottom:1px solid #34445a; }}
th {{ background:#1a2432; }} td {{ font-variant-numeric:tabular-nums; }}
svg {{ width:100%; max-width:1000px; }} svg text {{ fill:#e9edf3; font-size:15px; }}
.track {{ fill:#34445a; }} .bar {{ fill:#56b4e9; }} code {{ overflow-wrap:anywhere; }}
</style></head><body><h1>ARC-AGI 實驗比較</h1>
<p>Config: <code>{config}</code></p>
<p>Top-1 exact match。每次執行獨立計分；錯誤與逾時納入分母。
重複試驗顯示成功率，不以任一次答對當作全對。耗時包含失敗執行。</p>
<h2>方法比較 / Solver comparison</h2>{chart}{comparison}
<h2>單題比較 / Task × solver</h2>{tasks}
<h2>題型比較 / Tags</h2>
<p>同一題可屬於多個 tag；各組可能重疊，不可把組別題數加總為整份資料集。</p>{tags}
<p>逐次原始紀錄：results.json、results.csv。分組統計：summary.csv。
這是本地公開題目或自訂題目的 top-1 結果，不是官方私有測試成績。</p>
</body></html>
"""
