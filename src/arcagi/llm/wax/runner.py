"""Cast wax with the local model and measure empty-tree fittability.

One *call* = one prompt to the model for one (task, method, sample). The
reply's ``solve`` runs in the sandbox, the trajectory is aligned, and every
step is fitted by ``arcbatch seed-sub``. One JSON line per call is appended
to ``calls.jsonl`` as soon as it finishes, so an interrupted run keeps all
finished calls; ``summary`` rebuilds every number from that file.
"""

from __future__ import annotations

import json
import signal
import threading
import time
from collections import defaultdict
from pathlib import Path

from arcagi.llm.wax import client, prompts, sandbox
from arcagi.llm.wax.fit import Fitter

REPO = Path(__file__).resolve().parents[4]
TRAINING = REPO / "data" / "ARC-AGI" / "data" / "training"
HAMMER = Path.home() / "code" / "playground-arc1" / "ws" / "hammer"
STOP_FILE = Path.home() / "arcagi-STOP"  # user / watchdog kill switch

# r09 foundry requests (b27ca6d3, 74dd1130, 2204b7a8) + tasks the hammer tree
# still misses (L16 / P48), training only, small enough for an 8k context.
COMPARE_TASKS = (
    "b27ca6d3",
    "74dd1130",
    "2204b7a8",
    "a740d043",
    "6f8cd79b",
    "995c5fa3",
    "e76a88a6",
    "22233c11",
    "1b60fb0c",
    "8d5021e8",
    "7fe24cdd",
    "46442a0e",
    "0d3d703e",
    "f76d97a5",
    "d511f180",
    "3aa6fb7a",
)
MAX_CELLS = 1200


def load_task(tid: str) -> dict:
    return json.loads((TRAINING / f"{tid}.json").read_text())


def cells(t: dict) -> int:
    return sum(
        len(p["input"]) * len(p["input"][0]) + len(p["output"]) * len(p["output"][0])
        for p in t["train"]
    )


def held_out() -> set[str]:
    p = HAMMER / "truth" / "cal" / "ids.json"
    if not p.exists():
        return set()
    d = json.loads(p.read_text())
    return set(d.get("H8", [])) | set(d.get("H24", []))


def overnight_tasks() -> list[str]:
    """Compare tasks first, then every other small training task (no H8/H24)."""
    ho = held_out()
    rest = sorted(
        p.stem
        for p in TRAINING.glob("*.json")
        if p.stem not in ho
        and p.stem not in COMPARE_TASKS
        and cells(load_task(p.stem)) <= MAX_CELLS
    )
    return list(COMPARE_TASKS) + rest


def wax_lines(
    tid: str, model: str, method: str, tags: list, states: list
) -> list[dict]:
    """Foundry wax format (``hammer.foundry`` docstring)."""
    out = [
        {
            "task": tid,
            "pairs": len(states),
            "steps": tags,
            "by": f"{model}:{method}",
            "req": "wax-night-1109",
            "verified": True,
        }
    ]
    for p, st in enumerate(states):
        for i, tag in enumerate(tags):
            out.append({"pair": p, "step": i + 1, "tag": tag, "grid": st[i + 1]})
    return out


def cast_one(
    tid: str,
    model: str,
    method: str,
    sample: int,
    fitter: Fitter,
    wax_dir: Path | None,
    raw_path: Path | None,
) -> dict:
    task = load_task(tid)
    prompt = prompts.build(method, task)
    local = client.is_local(model)
    rep = client.chat(
        prompt,
        model=model,
        max_tokens=(2500 if model == client.MODEL else 5000) if local else 16000,
        max_wait=600 if local else 300,
    )
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "task": tid,
        "method": method,
        "sample": sample,
        "model": model,
        "shared": local and time.strftime("%Y-%m-%dT%H:%M:%S") < client.SHARED_UNTIL,
        "prompt_chars": len(prompt),
        "prompt_tokens": rep.prompt_tokens,
        "completion_tokens": rep.completion_tokens,
        "seconds": round(rep.seconds, 2),
        "wait": round(rep.wait, 2),
        "retries": rep.retries,
        "finish": rep.finish,
        "error": rep.error,
    }
    if raw_path:
        with raw_path.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "task": tid,
                        "model": model,
                        "method": method,
                        "sample": sample,
                        "text": rep.text,
                    }
                )
                + "\n"
            )
    if rep.error:
        rec["status"] = "llm_error"
        return rec
    code = sandbox.extract_code(rep.text)
    if code is None:
        rec["status"] = "no_code"
        return rec
    run = sandbox.run_code(code, [p["input"] for p in task["train"]])
    tr = sandbox.trajectory(task, run)
    rec["status"] = tr["status"]
    if tr["status"] != "ok":
        rec["detail"] = {k: v for k, v in tr.items() if k != "status"}
        return rec
    states, tags = tr["states"], tr["tags"]
    segs = [[(st[i], st[i + 1]) for st in states] for i in range(len(tags))]
    fits = fitter.fit(segs)
    rec.update(
        {
            "verified": tr["verified"],
            "n_steps": len(tags),
            "tags": tags,
            "fit": [f["program"] is not None for f in fits],
            "programs": [f["program"] for f in fits],
            "sizes": [f["size"] for f in fits],
        }
    )
    rec["all_fit"] = all(rec["fit"])
    if tr["verified"] and wax_dir is not None:
        wax_dir.mkdir(parents=True, exist_ok=True)
        tag = model.replace("/", "_")
        path = wax_dir / f"{tid}__{tag}__{method}__s{sample:03d}.jsonl"
        path.write_text(
            "".join(
                json.dumps(r) + "\n"
                for r in wax_lines(tid, model, method, tags, states)
            )
        )
        rec["wax"] = (
            str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
        )
    return rec


def direct_fit(tids: list[str], fitter: Fitter) -> dict[str, bool]:
    """Is the whole task (input -> output) already one fittable step?"""
    out = {}
    for t in tids:
        task = load_task(t)
        f = fitter.fit([[(p["input"], p["output"]) for p in task["train"]]])[0]
        out[t] = f["program"] is not None
    return out


_STOP = threading.Event()


def _on_term(_sig, _frm):
    _STOP.set()


def loop(
    jobs,
    out: Path,
    fitter: Fitter,
    wax_dir: Path | None,
    raw_path: Path | None,
    deadline: float | None,
    workers: int = 1,
) -> int:
    """Run (task, model, method, sample) jobs with ``workers`` threads,
    appending one line per call to ``out``. SIGTERM / SIGINT or ``deadline``
    (epoch seconds) stop new calls; running calls finish. Returns calls done."""
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    lock = threading.Lock()
    it = iter(jobs)
    done = [0]

    class _Locked:
        def fit(self, segs):
            with lock:
                return fitter.fit(segs)

    lf = _Locked()

    def worker():
        while not _STOP.is_set():
            if deadline is not None and time.time() >= deadline:
                return
            if STOP_FILE.exists():
                _STOP.set()
                return
            with lock:
                job = next(it, None)
            if job is None:
                return
            tid, model, method, sample = job
            try:
                rec = cast_one(tid, model, method, sample, lf, wax_dir, raw_path)
            except Exception as e:  # keep going on any per-call failure
                rec = {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "task": tid,
                    "model": model,
                    "method": method,
                    "sample": sample,
                    "status": "crash",
                    "error": f"{type(e).__name__}: {e}"[:300],
                }
            with lock:
                with out.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
                done[0] += 1

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in ts:
        t.start()
    while any(t.is_alive() for t in ts):
        for t in ts:
            t.join(timeout=1.0)
    return done[0]


# ---------------------------------------------------------------- summary


def read_calls(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _rate(a: int, b: int) -> str:
    return f"{a}/{b} = {a / b:.1%}" if b else f"{a}/0 = —"


def stats(rows: list[dict]) -> dict:
    n = len(rows)
    answered = [r for r in rows if r.get("status") not in ("llm_error", "crash")]
    aligned = [r for r in rows if r.get("status") == "ok"]
    ver = [r for r in aligned if r.get("verified")]
    s_ver = sum(r["n_steps"] for r in ver)
    f_ver = sum(sum(r["fit"]) for r in ver)
    s_all = sum(r["n_steps"] for r in aligned)
    f_all = sum(sum(r["fit"]) for r in aligned)
    full_ver = [r for r in ver if r["all_fit"]]
    toks = sum(r.get("completion_tokens", 0) for r in answered)
    secs = sum(r.get("seconds", 0) for r in answered)
    wall = sum(r.get("seconds", 0) + r.get("wait", 0) for r in rows)
    return {
        "calls": n,
        "answered": len(answered),
        "aligned": len(aligned),
        "verified": len(ver),
        "steps_ver": s_ver,
        "fit_ver": f_ver,
        "steps_all": s_all,
        "fit_all": f_all,
        "full_ver": len(full_ver),
        "full_all": sum(1 for r in aligned if r["all_fit"]),
        "tasks_full": len({r["task"] for r in full_ver}),
        "tasks": len({r["task"] for r in rows}),
        "tok": toks,
        "secs": secs,
        "wall": wall,
        "tok_per_s": toks / secs if secs else 0.0,
        "tok_per_call": toks / len(answered) if answered else 0.0,
        "wall_per_call": wall / n if n else 0.0,
        "shared": sum(
            1
            for r in rows
            if client.is_local(r.get("model", ""))
            and r.get("ts", "") < client.SHARED_UNTIL
        ),
    }


def arm(r: dict) -> str:
    return f"{r.get('model', '?')} · {r['method']}"


def arms_of(rows: list[dict]) -> list[str]:
    return sorted({arm(r) for r in rows})


def method_table(rows: list[dict], arms) -> list[str]:
    by = defaultdict(list)
    for r in rows:
        by[arm(r)].append(r)
    out = [
        "| 模型 · 提示法 | 呼叫 | 有回覆 | 軌跡對齊 | 驗過 train | 每步可擬合（驗過的蠟模） | "
        "全步可擬合（驗過的蠟模） | 全步可擬合且驗過／呼叫 | 每步可擬合（所有對齊軌跡） | "
        "全步可擬合（所有對齊軌跡） | 有全步可擬合蠟模的題 | tok／呼叫 | tok／秒 | 牆鐘秒／呼叫 | 共用呼叫 |",
        "|" + "---|" * 16,
    ]
    for m in arms:
        s = stats(by.get(m, []))
        out.append(
            f"| {m} | {s['calls']} | {s['answered']} | {s['aligned']} | {s['verified']} | "
            f"{_rate(s['fit_ver'], s['steps_ver'])} | {_rate(s['full_ver'], s['verified'])} | "
            f"{_rate(s['full_ver'], s['calls'])} | {_rate(s['fit_all'], s['steps_all'])} | "
            f"{_rate(s['full_all'], s['aligned'])} | {s['tasks_full']}/{s['tasks']} | "
            f"{s['tok_per_call']:.0f} | {s['tok_per_s']:.1f} | {s['wall_per_call']:.0f} | "
            f"{s['shared']} |"
        )
    return out


def task_table(rows: list[dict], methods, direct: dict | None = None) -> list[str]:
    by = defaultdict(list)
    for r in rows:
        by[(r["task"], arm(r))].append(r)
    tids = sorted({r["task"] for r in rows})
    head = (
        "| 題 | 直接可擬合 | "
        + " | ".join(f"{m} 驗過／步擬合／全步" for m in methods)
        + " |"
    )
    out = [head, "|" + "---|" * (2 + len(methods))]
    for t in tids:
        cols = []
        for m in methods:
            s = stats(by.get((t, m), []))
            cols.append(
                f"{s['verified']}/{s['calls']}，{s['fit_all']}/{s['steps_all']}，"
                f"{s['full_ver']}"
            )
        d = "—" if direct is None else ("是" if direct.get(t) else "否")
        out.append(f"| {t} | {d} | " + " | ".join(cols) + " |")
    return out


def status_counts(rows: list[dict]) -> str:
    c = defaultdict(int)
    for r in rows:
        c[r.get("status")] += 1
    return "、".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1]))
