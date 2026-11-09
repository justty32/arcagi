"""CLI: ``python -m arcagi.llm.wax {compare,overnight,summary}``.

compare    every (task, model, method) x samples, one calls.jsonl
overnight  one (model, method) over many tasks in rounds until --until
summary    markdown tables from one or more calls.jsonl files
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import os
import sys
import time
from pathlib import Path

from arcagi.llm.wax import client, prompts
from arcagi.llm.wax import runner as rn
from arcagi.llm.wax.fit import Fitter

SCRATCH = Path(os.environ.get("WAX_SCRATCH", "/tmp/wax-scratch"))
LIB = rn.REPO / "reports" / "wax-night-1109" / "hammer-lib.json"


def _fitter(name: str, threads: int) -> Fitter:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return Fitter(
        SCRATCH / f"work-{name}-{os.getpid()}",
        LIB,
        threads,
        SCRATCH / f"fitcache-{name}.jsonl",
    )


def _until(s: str) -> float:
    """'06:45' -> next such local time (epoch seconds)."""
    h, m = map(int, s.split(":"))
    now = dt.datetime.now()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t <= now:
        t += dt.timedelta(days=1)
    return t.timestamp()


def cmd_compare(a) -> None:
    tasks = a.tasks.split(",") if a.tasks else list(rn.COMPARE_TASKS)
    models, methods = a.models.split(","), a.methods.split(",")
    jobs = [
        (t, mo, me, s)
        for s in range(a.samples)
        for t in tasks
        for mo in models
        for me in methods
    ]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # resume: skip (task, model, method, sample) already in the output
    have = {
        (r["task"], r.get("model"), r["method"], r["sample"])
        for r in rn.read_calls(out)
    }
    jobs = [j for j in jobs if j not in have]
    f = _fitter(a.name, a.threads)
    n = rn.loop(
        jobs,
        out,
        f,
        Path(a.wax) if a.wax else None,
        SCRATCH / f"raw-{a.name}.jsonl",
        None,
        a.workers,
    )
    print(f"{n} calls -> {out}")


def write_summary(
    calls: list[Path],
    out: Path,
    title: str,
    cmd: str,
    direct: bool,
    fitter_name: str = "summary",
) -> None:
    rows = [r for c in calls for r in rn.read_calls(c)]
    arms = rn.arms_of(rows)
    d = None
    if direct and rows:
        d = rn.direct_fit(sorted({r["task"] for r in rows}), _fitter(fitter_name, 6))
    ts = [r["ts"] for r in rows if r.get("ts")]
    lines = (
        [
            f"# {title}",
            "",
            f"寫於 {time.strftime('%Y-%m-%d %H:%M:%S')}（Asia/Taipei）。"
            f"呼叫時間 {min(ts) if ts else '—'} ～ {max(ts) if ts else '—'}。",
            "",
            f"- 來源：{', '.join(str(c) for c in calls)}",
            f"- 指令：`{cmd}`",
            f"- 模型：{client.MODEL}（關 thinking）與 {client.THINK}（開 thinking）走 LM Studio，"
            f"{client.SHARED_UNTIL[11:16]} 前與 2 個 aos agent **共用**（見「共用呼叫」欄），"
            "之後獨用；使用者約 23:00 關掉 LM Studio，gemma 兩組**中途關閉**、只有部分數據。"
            "chatgpt-* 走 litellm proxy（不用本機顯卡）。",
            "- 擬合：`arcbatch --mode seed-sub`，預算 200k 節點，空樹 32 原語＋活樹 3 個 live 積木"
            "（reports/wax-night-1109/hammer-lib.json）；不改變任何格的步（no-op）已剔除。",
            f"- 狀態計數：{rn.status_counts(rows)}",
            "",
            "## 各組合",
            "",
        ]
        + rn.method_table(rows, arms)
        + [""]
    )
    if len({r["task"] for r in rows}) <= 40:
        lines += [
            "## 逐題（驗過／呼叫，可擬合步／對齊軌跡總步，全步可擬合且驗過的蠟模數）",
            "",
        ]
        lines += rn.task_table(rows, arms, d) + [""]
    else:
        good = sorted(
            {r["task"] for r in rows if r.get("verified") and r.get("all_fit")}
        )
        ver = sorted({r["task"] for r in rows if r.get("verified")})
        lines += [
            "## 題目層級",
            "",
            f"- 嘗試過的題：{len({r['task'] for r in rows})}",
            f"- 至少一個驗過蠟模的題：{len(ver)}",
            f"- 至少一個全步可擬合且驗過蠟模的題（{len(good)}）："
            + (", ".join(good) if good else "無"),
            "",
        ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))


def cmd_summary(a) -> None:
    write_summary(
        [Path(c) for c in a.calls], Path(a.out), a.title, " ".join(sys.argv), a.direct
    )


def cmd_overnight(a) -> None:
    tasks = rn.overnight_tasks()
    if a.offset:
        # Rotate so parallel runs start on different task segments.
        k = a.offset % len(tasks)
        tasks = tasks[k:] + tasks[:k]
    if a.limit:
        tasks = tasks[: a.limit]
    jobs = ((t, a.model, a.method, r) for r in itertools.count() for t in tasks)
    out = Path(a.out_dir) / "calls.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    f = _fitter(a.name, a.threads)
    print(
        f"overnight: {len(tasks)} tasks, {a.model} {a.method}, until {a.until}",
        flush=True,
    )
    try:
        rn.loop(
            jobs,
            out,
            f,
            Path(a.out_dir) / "wax",
            SCRATCH / f"raw-{a.name}.jsonl",
            _until(a.until),
            a.workers,
        )
    finally:
        summarize_overnight(Path(a.out_dir).parent, a.name + "-sum")


def summarize_overnight(root: Path, name: str = "overnight-sum") -> None:
    """All ``<root>/*/calls.jsonl`` -> ``<root>/../overnight-summary.md``."""
    calls = sorted(Path(root).glob("*/calls.jsonl"))
    write_summary(
        calls,
        Path(root).parent / "overnight-summary.md",
        "整夜鑄蠟模彙總（wax-night-1109）",
        " ".join(sys.argv),
        False,
        name,
    )


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m arcagi.llm.wax")
    sp = p.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("compare")
    c.add_argument("--models", default=client.MODEL)
    c.add_argument("--methods", default=",".join(prompts.METHODS))
    c.add_argument("--tasks", default="")
    c.add_argument("--samples", type=int, default=2)
    c.add_argument("--workers", type=int, default=1)
    c.add_argument("--threads", type=int, default=6)
    c.add_argument("--out", required=True)
    c.add_argument("--wax", default="")
    c.add_argument("--name", default="compare")
    c.set_defaults(fn=cmd_compare)
    s = sp.add_parser("summary")
    s.add_argument("calls", nargs="+")
    s.add_argument("--out", required=True)
    s.add_argument("--title", default="鑄蠟模提示法比較")
    s.add_argument("--direct", action="store_true")
    s.set_defaults(fn=cmd_summary)
    so = sp.add_parser("summary-overnight")
    so.add_argument("root")
    so.set_defaults(fn=lambda a: summarize_overnight(Path(a.root)))
    o = sp.add_parser("overnight")
    o.add_argument("--model", default=client.MODEL)
    o.add_argument("--method", required=True)
    o.add_argument("--until", default="06:00")
    o.add_argument("--out-dir", required=True)
    o.add_argument("--workers", type=int, default=1)
    o.add_argument("--threads", type=int, default=6)
    o.add_argument("--limit", type=int, default=0)
    o.add_argument("--offset", type=int, default=0)
    o.add_argument("--name", default="overnight")
    o.set_defaults(fn=cmd_overnight)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
