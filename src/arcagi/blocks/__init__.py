"""aos integration: block folders, accounting (node-pool) and library learning.

Each search building block (primitive, learner, macro) may own a folder
``aos/blocks/<name>/`` holding ``_metainfo.json`` (identity, status, counters)
and an ``_entry`` script runnable with ``aos-exec``. Python keeps the fast
in-process implementations; folders hold identity and accounts.
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LEARNER_NAMES = frozenset({"colormap", "local_rule", "object_colormap"})


def default_blocks_root() -> Path:
    """``$ARCAGI_BLOCKS`` if set, else ``<repo>/aos/blocks``."""
    env = os.environ.get("ARCAGI_BLOCKS")
    return Path(env) if env else REPO_ROOT / "aos" / "blocks"


def read_json(path: Path, default: object = None) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
