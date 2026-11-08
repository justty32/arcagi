"""``python -m arcagi.hammer.check <root>``: full format check of a hammer tree.

Exit code 0 when every file parses and every row has its fields, else 1
(one error per line on stderr).
"""

import json
import sys
from pathlib import Path

from . import formats as fm


def check_root(root: Path) -> list[str]:
    root = Path(root)
    err: list[str] = []

    def load(fn, what):
        try:
            return fn()
        except (OSError, json.JSONDecodeError) as e:
            err.append(f"{what}: {e}")
            return None

    frozen = load(lambda: fm.load_frozen(root), "frozen.json")
    if frozen is None:
        err.append("frozen.json: missing")
    else:
        err += fm.check_frozen(frozen)
    meta = load(lambda: fm.load_metainfo(root), "_metainfo.json")
    if meta is None:
        err.append("_metainfo.json: missing")
    else:
        err += fm.check_metainfo(meta, "_metainfo.json")
    if not (root / "ops.jsonl").exists():
        err.append("ops.jsonl: missing")
    ops = load(lambda: fm.load_ops(root), "ops.jsonl") or []
    seen = set()
    for o in ops:
        err += fm.check_op(o)
        if o.get("id") in seen:
            err.append(f"op {o.get('id')}: duplicate id")
        seen.add(o.get("id"))
    if not (root / "ledger.jsonl").exists():
        err.append("ledger.jsonl: missing")
    for i, r in enumerate(load(lambda: fm.load_ledger(root), "ledger.jsonl") or []):
        err += fm.check_ledger_row(r, i)
    for name in fm.NODES:
        d = root / "nodes" / name
        if not d.is_dir():
            err.append(f"nodes/{name}: missing")
            continue
        m = load(lambda d=d: fm.load_metainfo(d), f"nodes/{name}/_metainfo.json")
        if m is None:
            err.append(f"nodes/{name}/_metainfo.json: missing")
        else:
            err += fm.check_metainfo(m, f"nodes/{name}/_metainfo.json")
        wit = load(lambda d=d: fm.load_witness(d), f"nodes/{name}/_witness.jsonl")
        for i, r in enumerate(wit or []):
            err += fm.check_witness_row(r, f"nodes/{name}/_witness.jsonl:{i + 1}")
    for d in sorted((root / "ops").glob("*/")) if (root / "ops").is_dir() else ():
        if load(lambda d=d: fm.read_json(d / "_metainfo.json"),
                f"ops/{d.name}/_metainfo.json") is None:
            err.append(f"ops/{d.name}/_metainfo.json: missing")
    return err


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m arcagi.hammer.check <root>", file=sys.stderr)
        return 2
    err = check_root(Path(argv[0]))
    for e in err:
        print(e, file=sys.stderr)
    print(f"{'ok' if not err else 'FAIL'}: {len(err)} errors")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
