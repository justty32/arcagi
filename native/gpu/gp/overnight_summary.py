"""Summarise the overnight gpgp run into a Markdown report.

Usage: python native/gpu/gp/overnight_summary.py --out-dir DIR --report MD
           [--n2-dir DIR] [--note TEXT]

Reads DIR/pass-*.jsonl, keeps the first solve per task, re-verifies every
solved program with the Python reference DSL (native/tools/gpu_verify.py),
and cross-references the N2 brute-force overnight results when present.
"""

import argparse
import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "native/tools"))
import gpu_verify  # noqa: E402


def read_jsonl(path: str) -> list[dict]:
    rows = []
    for line in open(path):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--n2-dir", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    passes = sorted(glob.glob(os.path.join(a.out_dir, "pass-*.jsonl")),
                    key=lambda p: int(p.rsplit("-", 1)[1].split(".")[0]))
    attempted: set[str] = set()
    first: dict[str, tuple[str, dict]] = {}
    pass_rows = []
    gpu_seconds = 0.0
    for p in passes:
        rows = [r for r in read_jsonl(p) if "skipped" not in r]
        name = Path(p).stem
        solved = [r for r in rows if r.get("solved")]
        secs = sum(float(r.get("seconds", 0)) for r in rows)
        gpu_seconds += secs
        pass_rows.append((name, len(rows), len(solved), secs))
        for r in rows:
            attempted.add(r["task"])
            if r.get("solved") and r["task"] not in first:
                first[r["task"]] = (name, r)

    n2_solved: dict[str, int] = {}
    if a.n2_dir:
        for f in glob.glob(os.path.join(a.n2_dir, "phase-*.jsonl")):
            for r in read_jsonl(f):
                if "best" in r:
                    n2_solved[r["task"]] = int(r["best"].get("depth", 0))

    checks = []
    for task, (name, r) in sorted(first.items()):
        try:
            c = gpu_verify.check(r, gpu_verify.DEFAULT_DATA)
        except Exception as e:  # keep the summary even when one task breaks
            c = {"task": task, "train_ok": False, "test_ok": False, "error": str(e)}
        checks.append((task, name, r, c))

    depths = Counter(int(r["best"]["depth"]) for _, (_, r) in first.items())
    lines = [
        "# GP 整夜彙總（gpgp，11-09→11-10）",
        "",
        f"產生時間 {datetime.now().isoformat(timespec='seconds')}。{a.note}",
        "",
        f"- 題池：主線未解的 training＋evaluation 題；跑過 {len(attempted)} 題，GPU 累計 {gpu_seconds/3600:.2f} 小時。",
        f"- GP 解出（train 全對）：**{len(first)}** 題；Python 重驗 train 對 "
        f"{sum(bool(c['train_ok']) for *_, c in checks)}、test 對 **{sum(bool(c['test_ok']) for *_, c in checks)}**。",
        f"- 化簡後深度分佈：{dict(sorted(depths.items()))}",
        "",
        "| 輪 | 題數 | 解出 | GPU 秒 |",
        "|---|---|---|---|",
    ]
    lines += [f"| {n} | {t} | {s} | {sec:.0f} |" for n, t, s, sec in pass_rows]
    lines += ["", "## 解出清單", "",
              "| 題 | 輪 | 深度 | 種類 | 秒 | Python train | Python test | N2 窮舉也解出（深度） | 程式 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for task, name, r, c in checks:
        b = r["best"]
        n2 = f"是（{n2_solved[task]}）" if task in n2_solved else "否"
        prog = json.dumps(b["program"], separators=(",", ":"))
        lines.append(f"| {task} | {name} | {b['depth']} | {b['kind']} | {r.get('solve_seconds', 0):.1f} | "
                     f"{c['train_ok']} | {c['test_ok']} | {n2} | `{prog}` |")
    only_gp = [t for t, *_ in checks if t not in n2_solved]
    lines += ["", f"GP 解出而 N2 窮舉（截至彙總時）未解出：{len(only_gp)} 題"
              + (f"：{', '.join(only_gp)}" if only_gp else "") + "。",
              "", "找到的解只寫報告，不進 `aos/blocks/`。原始資料：" + f"`{a.out_dir}/pass-*.jsonl`。", ""]
    Path(a.report).write_text("\n".join(lines))
    print(f"wrote {a.report}: solved {len(first)} / {len(attempted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
