"""Collect block JSON objects and check ``from_janet(to_janet(x)) == x``."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .emit import json_text, to_janet
from .parse import from_janet


@dataclass
class Report:
    checked: int = 0
    failures: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return self.checked - len(self.failures)


def block_objects(root: Path) -> Iterator[tuple[str, object, Path]]:
    """(label, object, base dir) for every program.json, _rule.json and body."""
    for path in sorted(Path(root).glob("*/program.json")):
        yield str(path), json.loads(path.read_text(encoding="utf-8")), path.parent
    for path in sorted(Path(root).glob("*/_rule.json")):
        rule = json.loads(path.read_text(encoding="utf-8"))
        yield str(path), rule, path.parent
        if isinstance(rule, dict) and "body" in rule:
            yield f"{path}#/body", rule["body"], path.parent


def trace_programs(paths: list[Path]) -> Iterator[tuple[str, object, None]]:
    """Raw JSON of every ``kind=program`` attempt in trace JSONL files."""
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            for i, att in enumerate((record.get("trace") or {}).get("attempts", [])):
                if att.get("kind") == "program" and "program" in att:
                    label = f"{record['task_id']}#{i}"
                    yield label, json.loads(att["program"]), None


def roundtrip(objects, report: Report | None = None) -> Report:
    report = report or Report()
    for label, obj, base in objects:
        report.checked += 1
        try:
            text = to_janet(obj, base=base)
            report.texts.append(text)
            if json_text(from_janet(text)) != json_text(obj):
                report.failures.append(label)
        except (ValueError, TypeError) as exc:
            report.failures.append(f"{label}: {exc}")
    return report
