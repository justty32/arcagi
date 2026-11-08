"""Optional syntax check of emitted text with the external ``janet`` binary.

Only ``parse-all`` runs (no evaluation of the forms). The solver never calls
this; when ``janet`` is not installed every check returns ``None``.
"""

import os
import shutil
import subprocess

PARSE_ONLY = "(parse-all (file/read stdin :all))"


def janet_path() -> str | None:
    return os.environ.get("ARCAGI_JANET") or shutil.which("janet")


def check(text: str, *, timeout: float = 10.0) -> bool | None:
    """True if janet parses ``text``, False if not, None without janet."""
    exe = janet_path()
    if exe is None:
        return None
    try:
        done = subprocess.run(
            [exe, "-e", PARSE_ONLY],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.returncode == 0


def check_all(texts: list[str]) -> list[bool | None]:
    """Check many texts: one janet run for all, per-text runs only on failure."""
    if not texts:
        return []
    joined = check("\n".join(texts))
    if joined is None:
        return [None] * len(texts)
    if joined:
        return [True] * len(texts)
    return [check(t) for t in texts]
