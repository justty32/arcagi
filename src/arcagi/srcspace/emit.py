"""JSON block objects -> Janet source text (``to_janet``).

Three shapes are rendered (all losslessly, see ``parse.from_janet``):

* program ``[[name, *params], ...]`` -> ``(prog (crop-object "4same" "smallest"))``;
  step names turn ``_`` into ``-``; strings inside steps are always quoted, lists
  become ``[...]``. A step ``{"$ref": path}`` becomes ``(m-x)`` plus a leading
  ``(def m-x "path" (prog ...))``; the docstring slot carries the exact path.
* dict (e.g. a whole ``_rule.json``) -> struct ``{:kind "pred" :body (...)}``.
* S-expression data (a rule ``body``) -> ``(lin n_obj 1 0)``: lists become
  ``(...)`` and strings that are plain identifiers become symbols.

JSON has no symbols, so a symbol and a quoted string both read back as ``str``;
what must survive is ``str`` vs number/bool/null, which the rendering keeps.
"""

import json
import math
import re
from pathlib import Path

PROG = "prog"
DEF = "def"
RESERVED = frozenset({"nil", "true", "false", PROG, DEF})
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_KEYWORD = re.compile(r"[A-Za-z_$][A-Za-z0-9_$\-]*\Z")
_ESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\t": "\\t", "\r": "\\r"}
LINE_WIDTH = 78


def is_ref(value: object) -> bool:
    """True for a pure ``{"$ref": "<non-empty str>"}`` step."""
    return (
        isinstance(value, dict)
        and list(value) == ["$ref"]
        and isinstance(value["$ref"], str)
        and bool(value["$ref"])
    )


def is_program(value: object) -> bool:
    """A list whose items are all ``[str, ...]`` steps or ``$ref`` steps."""
    return isinstance(value, list) and all(
        is_ref(step) or (isinstance(step, list) and step and isinstance(step[0], str))
        for step in value
    )


def quote(text: str) -> str:
    out = []
    for ch in text:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif not ch.isprintable():
            code = ord(ch)
            out.append(f"\\x{code:02x}" if code < 0x80 else f"\\U{code:06x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _number(value: int | float) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number {value!r} has no JSON form")
    return repr(value)


def _atom(value: object, symbols: bool, taken: frozenset[str]) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, str):
        if symbols and _IDENT.match(value) and value not in RESERVED | taken:
            return value
        return quote(value)
    raise TypeError(f"not a JSON value: {type(value).__name__}")


def _key(key: str) -> str:
    return ":" + key if _KEYWORD.match(key) else quote(key)


def value_text(
    value: object, *, symbols: bool, taken: frozenset[str] = frozenset()
) -> str:
    """One JSON value; ``symbols`` selects data mode (``(...)`` + bare symbols)."""
    if isinstance(value, list):
        items = " ".join(value_text(v, symbols=symbols, taken=taken) for v in value)
        return f"({items})" if symbols else f"[{items}]"
    if isinstance(value, dict):
        pairs = " ".join(
            f"{_key(k)} {value_text(v, symbols=symbols, taken=taken)}"
            for k, v in value.items()
        )
        return "{" + pairs + "}"
    return _atom(value, symbols, taken)


def step_head(name: str, taken: frozenset[str]) -> str:
    """``crop_object`` -> ``crop-object``; odd or colliding names stay quoted."""
    symbol = name.replace("_", "-")
    if _IDENT.match(name) and name not in RESERVED and symbol not in taken | RESERVED:
        return symbol
    return quote(name)


def ref_symbol(path: str) -> str:
    """Readable def name for a ``$ref`` path: ``../m_x/program.json`` -> ``m-x``."""
    file, _, pointer = path.partition("#")
    parts = [p for p in file.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    stem = (
        parts[-2]
        if len(parts) >= 2 and parts[-1] == "program.json"
        else (Path(parts[-1]).stem if parts else "ref")
    )
    base = re.sub(r"[^A-Za-z0-9]+", "-", stem + pointer).strip("-").lower() or "ref"
    return base if base[0].isalpha() else "r-" + base


def ref_names(program: list) -> dict[str, str]:
    """path -> unique def symbol, in order of first use."""
    names: dict[str, str] = {}
    used: set[str] = set()
    for step in program:
        if is_ref(step) and step["$ref"] not in names:
            base = ref_symbol(step["$ref"])
            sym, n = base, 2
            while sym in used or sym in RESERVED:
                sym, n = f"{base}-{n}", n + 1
            used.add(sym)
            names[step["$ref"]] = sym
    return names


def program_text(program: list, refs: dict[str, str]) -> str:
    taken = frozenset(refs.values())
    steps = []
    for step in program:
        if is_ref(step):
            steps.append(f"({refs[step['$ref']]})")
            continue
        head = step_head(step[0], taken)
        params = [value_text(p, symbols=False) for p in step[1:]]
        steps.append("(" + " ".join([head, *params]) + ")")
    flat = "(" + " ".join([PROG, *steps]) + ")"
    if len(flat) <= LINE_WIDTH or not steps:
        return flat
    return f"({PROG}\n  " + "\n  ".join(steps) + ")"


def _def_body(path: str, base: Path | None) -> str:
    if base is None:
        return "nil"
    from arcagi.blocks.catalog import RefError, expand_steps

    try:
        steps = expand_steps([{"$ref": path}], base)
    except RefError:
        return "nil"
    return program_text(steps, {}) if is_program(steps) else "nil"


def _dict_text(obj: dict) -> str:
    lines = []
    for key, value in obj.items():
        if isinstance(value, (list, dict)):
            text = value_text(value, symbols=True)
        else:
            text = _atom(value, False, frozenset())
        lines.append(f"{_key(key)} {text}")
    return "{" + "\n ".join(lines) + "}"


def to_janet(obj: object, *, base: Path | None = None) -> str:
    """Render ``obj`` as Janet source; ``base`` resolves ``$ref`` def bodies."""
    if is_program(obj):
        refs = ref_names(obj)  # type: ignore[arg-type]
        defs = [
            f"({DEF} {sym} {quote(path)}\n  {_def_body(path, base)})"
            for path, sym in refs.items()
        ]
        return "\n".join([*defs, program_text(obj, refs)]) + "\n"  # type: ignore[arg-type]
    if isinstance(obj, dict):
        return _dict_text(obj) + "\n"
    return value_text(obj, symbols=True) + "\n"


def json_text(obj: object) -> str:
    """Canonical compact JSON, used to compare round trips."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
