"""Example JSON-file solver; the same protocol works in any language.

Run: python examples/file_identity.py --input request.json --output response.json
This baseline copies test inputs and is only a protocol demonstration.
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.input.read_text(encoding="utf-8"))
    if request["schema_version"] != "arcagi-solver-input/1":
        raise ValueError("Unsupported solver input schema")
    mode = request.get("params", {}).get("mode", "identity")
    if mode not in {"identity", "zero"}:
        raise ValueError("Example mode must be identity or zero")
    predictions = [
        example["input"]
        if mode == "identity"
        else [[0 for cell in row] for row in example["input"]]
        for example in request["task"]["test"]
    ]
    args.output.write_text(
        json.dumps({request["task_id"]: predictions}) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
