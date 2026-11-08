"""A node run through ``python -m arcagi.hammer.exec`` equals the in-process call."""

import json
import subprocess
import sys

import pytest

from arcagi.hammer import body, node


def _strip(rows):
    return [{k: v for k, v in r.items() if k != "seconds"} for r in rows]


def test_exec_equals_in_process(tmp_path):
    if not body.ARCBATCH.exists():
        pytest.skip("native/bin/arcbatch not built")
    lib = tmp_path / "blocks.json"
    lib.write_text("[]")
    rows = [{"task_id": t, "budget": 20000, "lib": str(lib),
             "cfg": {"threads": 2}, "gate": True}
            for t in ("68b16354", "d10ecb37", "a740d043")]
    inproc = node.run("solve", rows)
    out = subprocess.run([sys.executable, "-m", "arcagi.hammer.exec", "solve"],
                         input="".join(json.dumps(r) + "\n" for r in rows),
                         capture_output=True, text=True, check=True).stdout
    sub = [json.loads(ln) for ln in out.splitlines()]
    assert _strip(sub) == _strip(inproc)
    assert inproc[0]["train_ok"]
