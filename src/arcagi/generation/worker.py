"""Isolated RE-ARC execution without optional plotting dependencies."""

import ast
import importlib.util
import json
import random
import sys
import types
from pathlib import Path
from typing import Any

from arcagi.generation.sources import vendor_directory, verify_sources


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_upstream() -> tuple[types.ModuleType, types.ModuleType, types.ModuleType]:
    """Load unmodified upstream generation code in this dedicated process.

    Only the optional plotting imports and plot_task function are excluded
    from utils at execution time. Vendored files retain their original bytes.
    """
    verify_sources()
    directory = vendor_directory()
    _load_module("dsl", directory / "dsl.py")
    path = directory / "utils.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.Import)
            and any(alias.name.startswith("matplotlib") for alias in node.names)
            or isinstance(node, ast.ImportFrom)
            and (node.module or "").startswith("matplotlib")
            or isinstance(node, ast.FunctionDef)
            and node.name == "plot_task"
        )
    ]
    utilities = types.ModuleType("utils")
    sys.modules["utils"] = utilities
    exec(compile(tree, str(path), "exec"), utilities.__dict__)
    generators = _load_module("generators", directory / "generators.py")
    verifiers = _load_module("verifiers", directory / "verifiers.py")
    return generators, verifiers, utilities


def generate_task(request: dict[str, Any]) -> dict[str, Any]:
    """Generate unique verified pairs, bounded by the parent's wall clock."""
    generators, verifiers, utilities = load_upstream()
    generator = getattr(generators, "generate_" + request["task_id"])
    verifier = getattr(verifiers, "verify_" + request["task_id"])
    random.seed(request["seed"])
    pairs = []
    seen: set[str] = set()
    total = request["train_examples"] + request["test_examples"]
    for _ in range(total * 100):
        utilities.rng.clear()
        try:
            pair = generator(request["difficulty_lower"], request["difficulty_upper"])
            if not all(utilities.is_grid(pair[key]) for key in ("input", "output")):
                continue
            if verifier(pair["input"]) != pair["output"]:
                continue
            key = json.dumps(pair["input"], separators=(",", ":"))
            if key in seen:
                continue
            seen.add(key)
            pairs.append(pair)
        except (ArithmeticError, IndexError, KeyError, StopIteration, ValueError):
            continue
        if len(pairs) == total:
            return {
                "train": pairs[: request["train_examples"]],
                "test": pairs[request["train_examples"] :],
            }
    raise RuntimeError(
        f"Could not generate {total} distinct verified pairs "
        f"within {total * 100} attempts"
    )


def main() -> None:
    """Read one generation request and write a single ARC task."""
    request = json.load(sys.stdin)
    json.dump(generate_task(request), sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
