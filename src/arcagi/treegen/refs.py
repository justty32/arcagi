"""Canonical JSON, bottom-up subtree interning and recursive references."""

import hashlib
import json
import re
from collections import Counter, defaultdict


def canonical(value: object) -> str:
    """Return the canonical spelling specified by aos-tree/1."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha12(value: object) -> str:
    """Hash the UTF-8 canonical spelling to twelve hexadecimal digits."""
    return hashlib.sha1(canonical(value).encode()).hexdigest()[:12]


def genome_sha(defs: dict, tree: dict) -> str:
    """Hash only the representation's definitions and tree."""
    return sha12({"defs": defs, "tree": tree})


def deduplicate(tree: dict) -> tuple[dict, dict]:
    """Intern repeated containers after replacing their children, bottom up.

    A post-order collection groups containers by original subtree height.
    For each height, count canonical forms with already substituted children,
    then replace repeated forms. First-level values and file stubs stay inline.
    """
    levels: dict[int, list[tuple[object, bool]]] = defaultdict(list)

    def collect(value: object, depth: int) -> int:
        if not isinstance(value, (dict, list)):
            return -1
        if isinstance(value, dict) and "$file" in value:
            return -1
        children = value.values() if isinstance(value, dict) else value
        height = 1 + max((collect(v, depth + 1) for v in children), default=-1)
        levels[height].append((value, depth > 1))
        return height

    collect(tree, 0)
    defs, replaced = {}, {}

    def child(value: object) -> object:
        return replaced.get(id(value), value)

    for height in sorted(levels):
        candidates = []
        for value, eligible in levels[height]:
            result = (
                {k: child(v) for k, v in value.items()}
                if isinstance(value, dict)
                else [child(v) for v in value]
            )
            encoded = canonical(result).encode()
            candidates.append((value, eligible, result, encoded))
        counts = Counter(encoded for _, eligible, _, encoded in candidates if eligible)
        for value, eligible, result, encoded in candidates:
            if eligible and len(encoded) >= 64 and counts[encoded] >= 2:
                key = hashlib.sha1(encoded).hexdigest()[:12]
                if key in defs and canonical(defs[key]).encode() != encoded:
                    raise ValueError(f"subtree hash collision: {key}")
                defs[key] = result
                result = {"$ref": f"#/defs/{key}"}
            replaced[id(value)] = result
    return defs, replaced[id(tree)]


def expand(tree: object, defs: dict) -> object:
    """Expand local references recursively, rejecting cycles and foreign refs."""

    def visit(value: object, active: frozenset[str]) -> object:
        if isinstance(value, list):
            return [visit(v, active) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            ref = value["$ref"]
            if (
                set(value) != {"$ref"}
                or not isinstance(ref, str)
                or not re.fullmatch(r"#/defs/[0-9a-f]{12}", ref)
            ):
                raise ValueError(f"invalid reference: {ref!r}")
            key = ref.rsplit("/", 1)[1]
            if key not in defs:
                raise ValueError(f"missing definition: {ref}")
            if key in active:
                raise ValueError(f"cyclic reference: {ref}")
            return visit(defs[key], active | {key})
        return {k: visit(v, active) for k, v in value.items()}

    return visit(tree, frozenset())


def count_refs(value: object) -> int:
    """Count stored reference objects, including references inside defs."""
    if isinstance(value, list):
        return sum(count_refs(v) for v in value)
    if isinstance(value, dict):
        return int("$ref" in value) + sum(count_refs(v) for v in value.values())
    return 0
