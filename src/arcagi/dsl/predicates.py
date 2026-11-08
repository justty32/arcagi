"""Predicate AST over one object's attribute dict (JSON S-expressions).

Forms: ``["eq"|"ne"|"gt"|"lt", attr, value]``, ``["rank", attr, "max"|"min"]``
(needs the object's group), ``["and", p, ...]``, ``["or", p, ...]``,
``["not", p]``. A single-attribute selector ``(attr, value)`` is the depth-1
special case ``["eq", attr, value]``; ``attr == "all"`` is the always-true
predicate.

Live predicates are generated blocks ``aos/blocks/pred_<hash>/`` (see
``arcagi.blocks.gen_predicates``); ``install`` registers them by name and
``resolve`` falls back to reading ``_rule.json`` for names not installed.

CLI (the block ``_entry``): ``python -m arcagi.dsl.predicates RULE.json`` reads
stdin (a props dict, or ``{"object": props, "group": [props, ...]}``) and prints
``true`` / ``false``.
"""

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

type Props = Mapping[str, object]
type Body = list[object]

OPS = ("eq", "ne", "gt", "lt", "rank", "and", "or", "not")
LIVE: dict[str, Body] = {}


def _cmp(op: str, have: object, want: object) -> bool:
    if op == "eq":
        return have == want
    if op == "ne":
        return have != want
    if not isinstance(have, int) or not isinstance(want, int):
        return False
    return have > want if op == "gt" else have < want


def evaluate(
    body: Sequence[object],
    props: Props,
    group: Sequence[Props] | None = None,
    _stats: dict | None = None,
) -> bool:
    """Truth of ``body`` for one object; ``group`` is needed only by ``rank``."""
    op = body[0]
    if op in ("eq", "ne", "gt", "lt"):
        _, attr, want = body
        return _cmp(op, props.get(attr), want)  # type: ignore[arg-type]
    if op == "rank":
        _, attr, which = body
        if group is None:
            raise ValueError("rank needs the object group")
        stats = _stats if _stats is not None else {}
        key = (attr, which)
        if key not in stats:
            values = [p.get(attr) for p in group if isinstance(p.get(attr), int)]  # type: ignore[arg-type]
            stats[key] = (max if which == "max" else min)(values) if values else None
        return stats[key] is not None and props.get(attr) == stats[key]  # type: ignore[arg-type]
    if op == "and":
        return all(evaluate(p, props, group, _stats) for p in body[1:])  # type: ignore[arg-type]
    if op == "or":
        return any(evaluate(p, props, group, _stats) for p in body[1:])  # type: ignore[arg-type]
    if op == "not":
        return not evaluate(body[1], props, group, _stats)  # type: ignore[arg-type]
    raise ValueError(f"unknown predicate op {op!r}")


def evaluate_group(body: Sequence[object], group: Sequence[Props]) -> list[bool]:
    """``evaluate`` for every member of ``group`` (rank stats computed once)."""
    stats: dict = {}
    return [evaluate(body, p, group, stats) for p in group]


def literals(body: Sequence[object]) -> int:
    """Number of leaf comparisons (the predicate's description length)."""
    if body[0] in ("and", "or"):
        return sum(literals(p) for p in body[1:])  # type: ignore[arg-type]
    if body[0] == "not":
        return literals(body[1])  # type: ignore[arg-type]
    return 1


def validate(body: object) -> bool:
    if not isinstance(body, list) or not body or body[0] not in OPS:
        return False
    op = body[0]
    if op in ("eq", "ne", "gt", "lt"):
        return len(body) == 3 and isinstance(body[1], str)
    if op == "rank":
        return len(body) == 3 and body[2] in ("max", "min")
    if op == "not":
        return len(body) == 2 and validate(body[1])
    return len(body) >= 2 and all(validate(p) for p in body[1:])


def from_selector(attr: str, value: object) -> Body:
    """Old ``(attr, value)`` selector parameters as a predicate AST."""
    return ["and"] if attr == "all" else ["eq", attr, value]


def read_rule(folder: Path) -> Body | None:
    try:
        rule = json.loads((folder / "_rule.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    body = rule.get("body") if isinstance(rule, dict) else None
    return body if validate(body) else None


def install(bodies: Mapping[str, Body]) -> None:
    LIVE.clear()
    LIVE.update(bodies)


def resolve(name: str) -> Body:
    """Body of a predicate block: installed live ones, else its folder."""
    if name in LIVE:
        return LIVE[name]
    from arcagi.blocks import default_blocks_root

    body = read_rule(default_blocks_root() / name)
    if body is None:
        raise ValueError(f"unknown predicate {name!r}")
    return body


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(
            "usage: python -m arcagi.dsl.predicates RULE.json < obj.json",
            file=sys.stderr,
        )
        return 2
    try:
        body = read_rule(Path(argv[0]).parent)
        if body is None:
            raise ValueError(f"bad rule file {argv[0]}")
        data = json.loads(sys.stdin.read())
        if isinstance(data, dict) and "object" in data:
            group = data.get("group") or [data["object"]]
            result = evaluate(body, data["object"], group)
        else:
            result = evaluate(body, data, [data])
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        print(f"arcagi.dsl.predicates: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print("true" if result else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
