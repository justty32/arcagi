"""Hybrid time budgets stay unchanged unless explicitly configured."""

import subprocess
import sys

import pytest

from arcagi.solvers import gated


@pytest.mark.parametrize(
    ("value", "expected"), [(None, 60), ("", 60), ("130", 130.0), ("130.5", 130.5)]
)
def test_hybrid_timeout(monkeypatch, value, expected):
    monkeypatch.delenv("ARCAGI_GATED_TIMEOUT", raising=False)
    if value is not None:
        monkeypatch.setenv("ARCAGI_GATED_TIMEOUT", value)
    assert gated._hybrid_timeout() == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(None, 60), ("", 60), ("130", 130.0), ("130.5", 130.5)]
)
def test_run_hybrid_preserves_argv(monkeypatch, tmp_path, value, expected):
    monkeypatch.delenv("ARCAGI_GATED_TIMEOUT", raising=False)
    if value is not None:
        monkeypatch.setenv("ARCAGI_GATED_TIMEOUT", value)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))

    monkeypatch.setattr(gated.subprocess, "run", fake_run)
    request, output, trace = (tmp_path / name for name in ("req", "out", "trace"))
    gated._run_hybrid(request, output, trace)
    assert calls == [
        (
            [
                str(gated.ROOT / "native" / "bin" / "solve"),
                str(request),
                str(output),
                str(trace),
            ],
            {"check": False, "timeout": expected},
        )
    ]


@pytest.mark.parametrize(
    ("value", "expected"), [(None, 19.0), ("", 19.0), ("40", 40.0), ("40.5", 40.5)]
)
def test_native_hybrid_deadline(monkeypatch, value, expected):
    monkeypatch.delenv("ARCAGI_HYBRID_DEADLINE", raising=False)
    if value is not None:
        monkeypatch.setenv("ARCAGI_HYBRID_DEADLINE", value)
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import runpy, sys; module = runpy.run_path(sys.argv[1]); "
            "print(module['DEADLINE'] - module['T0'])",
            str(gated.ROOT / "native" / "hybrid.py"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert float(completed.stdout) == pytest.approx(expected)
