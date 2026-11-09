"""Offline tests for the wax night run (no model, no arcbatch)."""

import pytest

from arcagi.llm.wax import client, prompts, runner, sandbox

TASK = {
    "train": [
        {"input": [[1, 2], [3, 4]], "output": [[4, 3], [2, 1]]},
        {"input": [[5, 6, 7]], "output": [[7, 6, 5]]},
    ]
}

CODE = """
def solve(grid):
    g = step("flip", P.reverse(grid))
    g = step("noop", g)
    g = step("mirror", P.map(lambda r: P.reverse(r), g))
    return g
"""


def test_extract_code_takes_last_solve_block():
    text = "x\n```python\nprint(1)\n```\n```python\ndef solve(g):\n    return g\n```"
    assert sandbox.extract_code(text).startswith("def solve")
    assert sandbox.extract_code("no code") is None


def test_trajectory_drops_noops_and_verifies():
    run = sandbox.run_code(CODE, [p["input"] for p in TASK["train"]])
    tr = sandbox.trajectory(TASK, run)
    assert tr["status"] == "ok" and tr["verified"]
    # pair 1 has one row: "flip" changes nothing there, but it changes pair 0
    assert tr["tags"] == ["flip", "mirror"]
    assert tr["states"][0][-1] == [[4, 3], [2, 1]]


def test_trajectory_unaligned_and_errors():
    code = "def solve(g):\n    for r in g:\n        step('row', g)\n    return g"
    tr = sandbox.trajectory(
        TASK, sandbox.run_code(code, [p["input"] for p in TASK["train"]])
    )
    assert tr["status"] == "unaligned"
    bad = sandbox.run_code("def solve(g):\n    return 1/0", [[[1]]])
    assert "error" in bad[0]
    assert sandbox.trajectory({"train": [TASK["train"][0]]}, bad)["status"] == "error"


def test_sandbox_timeout():
    r = sandbox.run_code("def solve(g):\n    while True: pass", [[[1]]], timeout=3)
    assert isinstance(r, dict) and "error" in r


def test_prompts_steer_differently():
    t = {"train": [{"input": [[1]], "output": [[2]]}]}
    base = prompts.build("base", t)
    assert "transpose(xss)" not in base
    for m in ("prims", "prims_py", "prims_shot"):
        assert "transpose(xss)" in prompts.build(m, t)
    assert "Worked example" in prompts.build("prims_shot", t)
    with pytest.raises(ValueError):
        prompts.build("nope", t)


def test_client_never_routes_other_lm_studio_models():
    assert client.url_for(client.MODEL) == client.url_for(client.THINK) == client.URL
    assert client.url_for("chatgpt-gpt-6-sol-low") == client.LITELLM_URL
    for m in ("qwen/qwen3.5-9b", "lm-gemma-4-12b"):
        with pytest.raises(ValueError):
            client.url_for(m)


def test_stats_counts_steps_and_full_fit():
    rows = [
        {
            "task": "a",
            "model": "m",
            "method": "x",
            "status": "ok",
            "verified": True,
            "n_steps": 2,
            "fit": [True, True],
            "all_fit": True,
            "completion_tokens": 10,
            "seconds": 2,
            "wait": 0,
        },
        {
            "task": "a",
            "model": "m",
            "method": "x",
            "status": "ok",
            "verified": False,
            "n_steps": 3,
            "fit": [True, False, False],
            "all_fit": False,
            "completion_tokens": 10,
            "seconds": 2,
            "wait": 0,
        },
        {
            "task": "b",
            "model": "m",
            "method": "x",
            "status": "llm_error",
            "seconds": 0,
            "wait": 5,
        },
    ]
    s = runner.stats(rows)
    assert (s["verified"], s["fit_ver"], s["steps_ver"], s["full_ver"]) == (1, 2, 2, 1)
    assert (s["fit_all"], s["steps_all"]) == (3, 5)
    assert s["tok_per_s"] == 5.0
    assert len(runner.method_table(rows, runner.arms_of(rows))) == 3


def test_trajectory_collapses_loops():
    code = (
        "def solve(g):\n    g = step('a', P.reverse(g))\n    g = step('b', P.reverse(g))\n"
        "    g = step('c', P.reverse(P.map(lambda r: P.reverse(r), g)))\n    return g"
    )
    tr = sandbox.trajectory(
        TASK, sandbox.run_code(code, [p["input"] for p in TASK["train"]])
    )
    assert tr["status"] == "ok" and tr["verified"] and tr["tags"] == ["c"]
