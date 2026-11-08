"""``python -m arcagi.hammer.exec <node> <in.jsonl >out.jsonl``.

Runs one node's entry (``run(rows) -> rows``) on JSONL rows from stdin and
writes JSONL rows to stdout; ``seconds`` fields are the only non-repeatable
values (drop them before comparing with an in-process call).
"""

import json
import sys

from . import node


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m arcagi.hammer.exec <node> <in.jsonl >out.jsonl",
              file=sys.stderr)
        return 2
    rows = [json.loads(ln) for ln in sys.stdin if ln.strip()]
    for r in node.run(argv[0], rows):
        sys.stdout.write(json.dumps(r, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
