"""CLI: ``python -m arcagi.llm {prompts,check,record,rescore,summary}``.

- ``prompts --split S (--ids ID.. | --unsolved N)``: write
  ``aos/llm/prompts/tasks/<id>.md`` (train pairs + test inputs only).
- ``check ID RESPONSE --split S``: train-only feedback for the LLM (no test data).
- ``record ID RESPONSE --split S --run R --model M [--tokens T --seconds X]``:
  score every rule (train + test), append traces, and - training only - write
  candidates for train-passing rules. Prints the per-task summary row.
- ``rescore``: training support / verdict of every candidate.
- ``summary --split S --run R [--csv OUT]``: per-task table from the traces.

A response file is a rule dict or ``{"rules": [rule, ...]}`` (best first).
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from . import candidates as cd
from . import tasks as tk
from . import trace as tr
from . import verify as vf


def _rules(path: Path) -> list:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "rules" in data:
        return list(data["rules"])
    return [data]


def cmd_prompts(args) -> int:
    ids = args.ids or tk.unsolved(args.split)[: args.unsolved]
    for tid in ids:
        print(tk.write_prompt(tid, args.split))
    return 0


def cmd_check(args) -> int:
    for rank, rule in enumerate(_rules(args.response)):
        res = vf.check(args.task, args.split, rule)
        res.pop("rule", None)
        res.pop("program", None)
        print(json.dumps({"rank": rank} | res, separators=(",", ":")))
    return 0


def cmd_record(args) -> int:
    path = tr.path_for(args.split, args.run)
    data = json.loads(args.response.read_text())
    notes = (
        {k: data.get(k) for k in ("idea", "missing")} if isinstance(data, dict) else {}
    )
    prompt_hash = cd.prompt_hash()
    for rank, rule in enumerate(_rules(args.response)):
        res = vf.score(args.task, args.split, rule)
        made: list[str] = []
        if res.get("train_all") and args.split == "training":
            made = cd.emit(
                res["rule"],
                res["program"],
                task_id=args.task,
                split=args.split,
                model=args.model,
            )
        tr.append(
            path,
            {
                "task": args.task,
                "split": args.split,
                "model": args.model,
                "rank": rank,
                "rule": res.get("rule"),
                "valid": res.get("valid"),
                "train_pass": res.get("train_pass"),
                "train_all": res.get("train_all"),
                "test_exact": res.get("test_exact"),
                "error": res.get("error"),
                "tokens": args.tokens,
                "seconds": args.seconds,
                "candidates": made,
                "prompt_hash": prompt_hash,
            }
            | notes,
        )
    rows = [r for r in tr.summarize(tr.read(path)) if r["task"] == args.task]
    print(json.dumps(rows[0], separators=(",", ":")))
    return 0


def cmd_rescore(_args) -> int:
    from .mainline import formula_verdict, pred_verdict
    from .rescore import rescore

    rows = rescore()
    folders = {f.parent.name: f.parent for f in cd.all_folders()}
    for kind, exact_fn in (("pred", pred_verdict), ("formula", formula_verdict)):
        picked = [r for r in rows if r["kind"] == kind]
        if not picked:
            continue
        bodies = [
            json.loads((folders[r["candidate"]] / "_rule.json").read_text())["body"]
            for r in picked
        ]
        for row, exact in zip(picked, exact_fn(bodies), strict=True):
            exact.pop("body")
            row["mainline"] = exact
            meta_path = folders[row["candidate"]] / "_metainfo.json"
            meta = json.loads(meta_path.read_text())
            meta["mainline"] = exact
            meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    for row in rows:
        row["support_tasks"] = len(row["support_tasks"])
        row["new_vs_r04"] = len(row["new_vs_r04"])
        print(json.dumps(row, separators=(",", ":")))
    return 0


def cmd_summary(args) -> int:
    rows = tr.summarize(tr.read(tr.path_for(args.split, args.run)))
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["task"])
            w.writeheader()
            w.writerows(rows)
    n = len(rows)
    print(
        json.dumps(
            {
                "tasks": n,
                "train_all": sum(r["train_all"] for r in rows),
                "test_exact": sum(r["test_exact"] for r in rows),
                "mean_best_train_pass": round(
                    sum(r["best_train_pass"] for r in rows) / n, 3
                )
                if n
                else 0,
            }
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="arcagi.llm")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prompts")
    a.add_argument("--split", default="training", choices=tk.SPLITS)
    a.add_argument("--ids", nargs="*")
    a.add_argument("--unsolved", type=int, default=0)
    for name in ("check", "record"):
        a = sub.add_parser(name)
        a.add_argument("task")
        a.add_argument("response", type=Path)
        a.add_argument("--split", default="training", choices=tk.SPLITS)
        if name == "record":
            a.add_argument("--run", required=True)
            a.add_argument("--model", required=True)
            a.add_argument("--tokens", type=int)
            a.add_argument("--seconds", type=float)
    sub.add_parser("rescore")
    a = sub.add_parser("summary")
    a.add_argument("--split", default="training", choices=tk.SPLITS)
    a.add_argument("--run", required=True)
    a.add_argument("--csv", type=Path)
    args = p.parse_args(argv)
    return {
        "prompts": cmd_prompts,
        "check": cmd_check,
        "record": cmd_record,
        "rescore": cmd_rescore,
        "summary": cmd_summary,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
