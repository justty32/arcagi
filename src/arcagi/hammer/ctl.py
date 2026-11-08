"""Live-tree control: python -m arcagi.hammer.ctl --root DIR <cmd> ...

Commands: run, stop, status, say, pause, resume, weight, add-op, ops, ledger,
view. Messages are only written to nodes/<node>/inbox/<ts>.json; the engine
reads them at the next epoch boundary. `stop` deletes DIR/RUN.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import formats as F

ROOT_PY = Path(__file__).resolve().parents[3]


def _inbox(root: Path, node: str, msg: dict) -> Path:
    if node not in F.NODES:
        sys.exit(f"unknown node {node!r}; nodes: {', '.join(F.NODES)}")
    d = root / "nodes" / node / "inbox"
    d.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    p = d / f"{ts}.json"
    n = 1
    while p.exists():
        p = d / f"{ts}-{n}.json"
        n += 1
    F.write_json(p, msg)
    print(p)
    return p


def _pid(root: Path):
    try:
        return int((root / "live" / "daemon.pid").read_text().strip())
    except (OSError, ValueError):
        return None


def _alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cmd_run(root: Path, a) -> None:
    pid = _pid(root)
    if _alive(pid):
        sys.exit(f"already running (pid {pid}); `stop` first")
    (root / "live").mkdir(parents=True, exist_ok=True)
    (root / "RUN").write_text(F.now() + "\n")
    cmd = [sys.executable, str(ROOT_PY / "scripts" / "r09_hammer.py"),
           "--tree", "hammer", "--root", str(root)]
    if a.epochs:
        cmd += ["--epochs", str(a.epochs)]
    if not a.daemon:
        (root / "live" / "daemon.pid").write_text(f"{os.getpid()}\n")
        sys.exit(subprocess.call(cmd, cwd=ROOT_PY))
    log = open(root / "live" / "daemon.log", "ab")
    full = ["setsid", "nohup", "nice", "-n", "19"] + cmd
    p = subprocess.Popen(full, cwd=ROOT_PY, stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    (root / "live" / "daemon.pid").write_text(f"{p.pid}\n")
    print(f"daemon pid {p.pid}, log {root / 'live' / 'daemon.log'}")


def cmd_stop(root: Path, a) -> None:
    run = root / "RUN"
    if run.exists():
        run.unlink()
        print("RUN removed; engine exits at the next epoch boundary")
    else:
        print("RUN already absent")
    if a.now:
        pid = _pid(root)
        if _alive(pid):
            os.kill(pid, signal.SIGTERM)
            print(f"SIGTERM -> {pid}")
        else:
            print("no live daemon pid")


def cmd_status(root: Path, a) -> None:
    st = F.read_json(root / "live" / "_status.json", {})
    pid = _pid(root)
    print(f"RUN: {'yes' if (root / 'RUN').exists() else 'no'}  "
          f"daemon: {pid if _alive(pid) else 'not running'}")
    print("epoch:", st.get("epoch", "-"), " status:", json.dumps(st, ensure_ascii=False)[:600])
    ops = F.load_ops(root) if (root / "ops.jsonl").exists() else []
    cnt = {}
    for o in ops:
        cnt[o["status"]] = cnt.get(o["status"], 0) + 1
    print("ops:", cnt)
    for n in F.NODES:
        m = F.read_json(root / "nodes" / n / "_metainfo.json", {})
        inb = len(list((root / "nodes" / n / "inbox").glob("*.json")))
        print(f"  node {n:8s} {m.get('status', '?'):8s} inbox={inb}")
    pend = list((root / "foundry" / "requests" / "pending").glob("*"))
    print("pending foundry requests:", len(pend))
    ev = F.read_jsonl(root / "live" / "events.jsonl") if (root / "live" / "events.jsonl").exists() else []
    for e in ev[-5:]:
        print("  event", json.dumps(e, ensure_ascii=False))


def cmd_ops(root: Path, a) -> None:
    for o in F.load_ops(root):
        if a.status and o["status"] != a.status:
            continue
        print(f"{o['id']:28s} {o['kind']:7s} {o['status']:10s} by={o['by']} "
              f"sig={o['sig']} new_solves={len(o['evidence']['new_solves'])}")


def cmd_ledger(root: Path, a) -> None:
    for r in F.load_ledger(root)[-a.tail:]:
        print(json.dumps(r, ensure_ascii=False))


def cmd_view(root: Path, a) -> None:
    eps = sorted((p for p in (root / "epochs").iterdir() if p.name.isdigit()),
                 key=lambda p: int(p.name)) if (root / "epochs").exists() else []
    if not eps:
        print("no epochs yet")
        return
    d = root / "epochs" / str(a.epoch) if a.epoch is not None else eps[-1]
    print(d)
    for name in ("status.json", "curve.csv"):
        p = d / name
        if p.exists():
            print(f"--- {name}")
            print(p.read_text()[:3000])


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="arcagi.hammer.ctl")
    ap.add_argument("--root", required=True)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("run")
    s.add_argument("--epochs", type=int, default=8)
    s.add_argument("--daemon", action="store_true")
    s = sp.add_parser("stop")
    s.add_argument("--now", action="store_true")
    sp.add_parser("status")
    s = sp.add_parser("say")
    s.add_argument("node")
    s.add_argument("text")
    for c in ("pause", "resume"):
        s = sp.add_parser(c)
        s.add_argument("node")
    s = sp.add_parser("weight")
    s.add_argument("route_id")
    s.add_argument("w", type=float)
    s = sp.add_parser("add-op")
    s.add_argument("json")
    s.add_argument("--live", action="store_true")
    s = sp.add_parser("ops")
    s.add_argument("--status")
    s = sp.add_parser("ledger")
    s.add_argument("--tail", type=int, default=20)
    s = sp.add_parser("view")
    s.add_argument("epoch", nargs="?", type=int)
    a = ap.parse_args(argv)
    root = Path(a.root).expanduser()
    if a.cmd == "say":
        _inbox(root, a.node, {"cmd": "say", "node": a.node, "text": a.text})
    elif a.cmd in ("pause", "resume"):
        _inbox(root, a.node, {"cmd": a.cmd, "node": a.node})
    elif a.cmd == "weight":
        _inbox(root, "route", {"cmd": "weight", "route": a.route_id, "w": a.w})
    elif a.cmd == "add-op":
        try:
            op = json.loads(a.json)
        except ValueError as e:
            sys.exit(f"bad json: {e}")
        if not isinstance(op, dict) or not {"id", "kind", "payload"} <= op.keys():
            sys.exit("op needs at least id, kind, payload")
        full = F.new_op(op["id"], op["kind"], op["payload"], "user", 0,
                        status="live" if a.live else "incubating",
                        sig=op.get("sig"), mdl_bits=op.get("mdl_bits"))
        errs = F.check_op(full)
        if errs:
            sys.exit("; ".join(errs))
        _inbox(root, "grow", {"cmd": "add-op", "op": full, "live": a.live})
    else:
        globals()["cmd_" + a.cmd.replace("-", "_")](root, a)


if __name__ == "__main__":
    main()
