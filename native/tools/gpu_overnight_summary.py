# ruff: noqa: E501  (Markdown table rows are long f-strings)
"""Summarise an overnight gpusearch run into a Markdown report.

Usage: python native/tools/gpu_overnight_summary.py --out-dir DIR --report PATH
       [--solved LIST ...] [--note TEXT]

Reads DIR/phase-*.jsonl (gpusearch output), re-verifies every best program and
sample with the Python reference DSL (native/tools/gpu_verify.py), and writes
the report: per-phase tasks, candidates, GPU seconds and throughput, found
programs (train-verified, test result, whether the mainline already solves
the task). Safe to call on partial output (interrupted runs).
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpu_verify import DEFAULT_DATA, find, runs  # noqa: E402

from arcagi.tasks import load_task  # noqa: E402


def split_of(task_id: str) -> str:
    path = find(task_id, DEFAULT_DATA)
    return path.parent.name


def main(argv: list[str]) -> int:
    out_dir, report, solved_lists, notes = None, None, [], []
    it = iter(argv)
    for arg in it:
        if arg == "--out-dir":
            out_dir = Path(next(it))
        elif arg == "--report":
            report = Path(next(it))
        elif arg == "--solved":
            solved_lists.append(Path(next(it)))
        elif arg == "--note":
            notes.append(next(it))
    assert out_dir and report
    solved: set[str] = set()
    for path in solved_lists:
        solved |= {
            line.strip() for line in path.read_text().splitlines() if line.strip()
        }

    lines = ["# 整夜 GPU 暴力搜尋彙總（自動產生）", ""]
    lines.append(
        f"- 產生時間：{time.strftime('%Y-%m-%dT%H:%M:%S%z')}（由 `native/tools/gpu_overnight_summary.py` 寫）"
    )
    lines.append(f"- 原始輸出：`{out_dir}`（每題一行 JSON）")
    lines += [f"- {n}" for n in notes]
    lines.append("")
    lines.append("## 各階段")
    lines.append("")
    lines.append(
        "| 階段 | 題數 | 有 train 解 | 完整掃完 | 候選數 | GPU 秒 | 候選／秒 |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    found: dict[str, dict[str, object]] = {}
    total_space, total_secs = 0.0, 0.0
    for path in sorted(out_dir.glob("phase-*.jsonl")):
        records = []
        for line in path.read_text().splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a line cut by the timeout
        rows = [r for r in records if "gpu" in r]
        space = sum(r["gpu"]["space"] for r in rows)
        secs = sum(r["gpu"]["seconds"] for r in rows)
        total_space += space
        total_secs += secs
        complete = sum(
            bool(r["gpu"]["complete"]) and not r.get("prefixes", {}).get("truncated")
            for r in rows
        )
        with_best = [r for r in rows if "best" in r]
        rate = f"{space / secs:.3g}" if secs else "-"
        lines.append(
            f"| {path.stem} | {len(rows)} | {len(with_best)} | {complete} | {space:.3g} | {secs:.0f} | {rate} |"
        )
        for r in with_best:
            found[r["task"]] = r | {"phase": path.stem}
    lines.append("")
    if total_secs:
        lines.append(
            f"合計候選 {total_space:.3g}，GPU 計時 {total_secs:.0f} 秒，平均 {total_space / total_secs:.3g} 候選／秒（GPU 與 LM Studio 共用）。"
        )
        lines.append("")

    verified = []
    for task_id, r in sorted(found.items()):
        task = load_task(find(task_id, DEFAULT_DATA))
        train_ok, test_ok = runs(task, r["best"]["program"])  # type: ignore[index]
        samples = r.get("samples") or []
        sample_ok = sum(runs(task, s)[0] for s in samples)  # type: ignore[union-attr]
        verified.append((task_id, r, train_ok, test_ok, len(samples), sample_ok))  # type: ignore[arg-type]

    n_train = sum(v[2] for v in verified)
    n_test = sum(v[3] for v in verified)
    new = [v for v in verified if v[3] and v[0] not in solved]
    n_samples = sum(v[4] for v in verified)
    n_samples_ok = sum(v[5] for v in verified)
    lines.append("## 找到的程式")
    lines.append("")
    lines.append(
        f"- 有 train 解的題：{len(verified)}；Python `arcagi.dsl.program` 重驗 train 全對 {n_train}/{len(verified)}，抽樣程式 {n_samples_ok}/{n_samples} train 全對。"
    )
    lines.append(
        f"- test 也對：{n_test}；其中主線（training gated-r07／evaluation gated-r08）未解的新題：**{len(new)}**。"
    )
    lines.append("- 找到的解只寫在這裡，不進 `aos/blocks/`。")
    lines.append("")
    if new:
        lines.append("### 主線未解、test 對的題")
        lines.append("")
        lines.append("| 題 | 集 | 深度 | 程式 |")
        lines.append("|---|---|---|---|")
        for task_id, r, *_ in new:
            best = r["best"]
            lines.append(
                f"| {task_id} | {split_of(task_id)} | {best['depth']} | `{json.dumps(best['program'])}` |"
            )  # type: ignore[index]
        lines.append("")
    lines.append("### 全部有 train 解的題")
    lines.append("")
    lines.append("| 題 | 集 | 階段 | 深度 | train(Py) | test(Py) | 主線已解 | 程式 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for task_id, r, train_ok, test_ok, _, _ in verified:
        best = r["best"]
        lines.append(
            f"| {task_id} | {split_of(task_id)} | {r['phase']} | {best['depth']} | {'✓' if train_ok else '✗'} | "  # type: ignore[index]
            f"{'✓' if test_ok else '✗'} | {'是' if task_id in solved else '否'} | `{json.dumps(best['program'])}` |"  # type: ignore[index]
        )
    lines.append("")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines))
    print(
        f"wrote {report}: {len(verified)} train-solved, {n_test} test-ok, {len(new)} new"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
