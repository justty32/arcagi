"""Numeric mutation bounds, shared by generation and validation."""

import math
from collections.abc import Iterator

from arcagi.hammer.formats import read_json

from .genome import REPORTS

BOUNDS = REPORTS / "ga/bounds.json"


def leaves(value: dict, prefix: tuple = ()) -> Iterator[tuple[tuple, object]]:
    """Enumerate nested scalar parameters without coercing booleans."""
    for key, item in value.items():
        path = (*prefix, key)
        if isinstance(item, dict):
            yield from leaves(item, path)
        else:
            yield path, item


def targets(tree: dict) -> list[tuple[str, dict, str, str | None, str]]:
    """Return path, container, key, owning op and bound-name for each surface."""
    result = []
    judge = tree["frozen.json"]["judge"]
    for path, value in leaves(judge):
        if isinstance(value, bool):
            continue
        container = judge
        for part in path[:-1]:
            container = container[part]
        result.append(
            (
                "frozen.json/judge/" + "/".join(path),
                container,
                path[-1],
                None,
                "judge." + ".".join(path),
            )
        )
    for op in tree["ops.jsonl"]:
        if op["kind"] == "gate":
            params = op["payload"]["params"]
            for key in params:
                if isinstance(params[key], bool):
                    continue
                result.append(
                    (
                        f"ops/{op['id']}/payload/params/{key}",
                        params,
                        key,
                        op["id"],
                        "gate." + key,
                    )
                )
        elif op["kind"] == "route":
            result.append(
                (
                    f"ops/{op['id']}/payload/priority",
                    op["payload"],
                    "priority",
                    op["id"],
                    "route.priority",
                )
            )
    for name, node in tree["nodes"].items():
        result.append(
            (
                f"nodes/{name}/_metainfo.json/weight",
                node["_metainfo.json"],
                "weight",
                None,
                "weight",
            )
        )
    return result


def validate(tree: dict) -> list[str]:
    """Reject missing bounds, invalid types, nonfinite and out-of-range values."""
    limits = read_json(BOUNDS)["limits"]
    errors = []
    for path, container, key, _, name in targets(tree):
        rule, value = limits.get(name), container[key]
        valid = rule is not None and type(value) in (int, float)
        if valid:
            try:
                valid = math.isfinite(value) and rule["min"] <= value <= rule["max"]
            except OverflowError:
                valid = False
            if rule["type"] == "int":
                valid = valid and type(value) is int
        if not valid:
            errors.append(f"bounds:{path}={value!r}")
    return errors
