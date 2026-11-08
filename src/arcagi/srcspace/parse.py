"""Janet source text -> JSON block objects (``from_janet``), inverse of ``emit``.

A small reader for the Janet subset ``to_janet`` writes: tuples ``(...)``,
bracket tuples ``[...]``, structs ``{...}``, strings, numbers, symbols,
keywords, ``nil``/``true``/``false`` and ``#`` comments. Nothing is evaluated.

Top-level forms: ``(def sym "path" body)`` binds ``sym`` to a ``$ref`` path;
the last other form is the result. ``(prog step ...)`` is a program; a step
``(sym)`` naming a def turns back into ``{"$ref": path}``, other step heads
turn ``-`` back into ``_`` (quoted heads are taken verbatim).
"""

import re
from dataclasses import dataclass

from .emit import DEF, PROG

_DELIMS = set('()[]{}"#') | set(" \t\r\n\f\v,")
_INT = re.compile(r"[+-]?\d+\Z")
_FLOAT = re.compile(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?\Z")
_SIMPLE = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "0": "\0",
    "z": "\0",
    "f": "\f",
    "e": "\x1b",
    "v": "\v",
    '"': '"',
    "\\": "\\",
    "'": "'",
}
_CLOSE = {"(": ")", "[": "]", "{": "}"}


class JanetSyntaxError(ValueError):
    pass


@dataclass(frozen=True)
class Sym:
    name: str


@dataclass(frozen=True)
class Kw:
    name: str


@dataclass(frozen=True)
class Form:
    """A parsed ``(...)``/``[...]``/``{...}``; ``kind`` is the open char."""

    kind: str
    items: tuple


def _string(text: str, i: int) -> tuple[str, int]:
    out = []
    i += 1
    while i < len(text):
        ch = text[i]
        if ch == '"':
            return "".join(out), i + 1
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        esc = text[i + 1 : i + 2]
        width = {"x": 2, "u": 4, "U": 6}.get(esc)
        if width:
            digits = text[i + 2 : i + 2 + width]
            if len(digits) != width:
                raise JanetSyntaxError(f"bad \\{esc} escape at {i}")
            out.append(chr(int(digits, 16)))
            i += 2 + width
        elif esc in _SIMPLE:
            out.append(_SIMPLE[esc])
            i += 2
        else:
            raise JanetSyntaxError(f"unknown escape \\{esc} at {i}")
    raise JanetSyntaxError("unterminated string")


def _token(word: str) -> object:
    if word == "nil":
        return None
    if word in ("true", "false"):
        return word == "true"
    if word.startswith(":"):
        return Kw(word[1:])
    if _INT.match(word):
        return int(word)
    if _FLOAT.match(word):
        return float(word)
    if word[0].isdigit():
        raise JanetSyntaxError(f"unsupported number {word!r}")
    return Sym(word)


def read_all(text: str) -> list[object]:
    """Read every top-level form; raise ``JanetSyntaxError`` on bad input."""
    stack: list[tuple[str, list]] = [("", [])]
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in " \t\r\n\f\v,":
            i += 1
        elif ch == "#":
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif ch in _CLOSE:
            stack.append((ch, []))
            i += 1
        elif ch in ")]}":
            kind, items = stack.pop() if len(stack) > 1 else ("", [])
            if not kind or _CLOSE[kind] != ch:
                raise JanetSyntaxError(f"unbalanced {ch!r} at {i}")
            stack[-1][1].append(Form(kind, tuple(items)))
            i += 1
        elif ch == '"':
            value, i = _string(text, i)
            stack[-1][1].append(value)
        else:
            j = i
            while j < len(text) and text[j] not in _DELIMS:
                j += 1
            stack[-1][1].append(_token(text[i:j]))
            i = j
    if len(stack) != 1:
        raise JanetSyntaxError(f"unclosed {stack[-1][0]!r}")
    return stack[0][1]


def to_json(node: object) -> object:
    """Plain conversion: symbols/keywords -> str, forms -> list/dict."""
    if isinstance(node, (Sym, Kw)):
        return node.name
    if isinstance(node, Form):
        if node.kind == "{":
            if len(node.items) % 2:
                raise JanetSyntaxError("struct with odd number of items")
            pairs = zip(node.items[::2], node.items[1::2], strict=True)
            out = {}
            for key, value in pairs:
                name = to_json(key)
                if not isinstance(name, str):
                    raise JanetSyntaxError(f"non-string struct key {name!r}")
                out[name] = to_json(value)
            return out
        return [to_json(item) for item in node.items]
    return node


def _is_head(form: object, name: str) -> bool:
    return (
        isinstance(form, Form)
        and form.kind == "("
        and bool(form.items)
        and form.items[0] == Sym(name)
    )


def _program(form: Form, refs: dict[str, str]) -> list:
    steps: list = []
    for step in form.items[1:]:
        if not (isinstance(step, Form) and step.kind == "(" and step.items):
            raise JanetSyntaxError(f"bad program step {step!r}")
        head, *params = step.items
        if isinstance(head, Sym) and head.name in refs and not params:
            steps.append({"$ref": refs[head.name]})
            continue
        if isinstance(head, Sym):
            name = head.name.replace("-", "_")
        elif isinstance(head, str):
            name = head
        else:
            raise JanetSyntaxError(f"bad step head {head!r}")
        steps.append([name, *(to_json(p) for p in params)])
    return steps


def from_janet(text: str) -> object:
    """Parse ``to_janet`` output back to the JSON object it came from."""
    refs: dict[str, str] = {}
    result: list[object] = []
    for form in read_all(text):
        if _is_head(form, DEF):
            items = form.items  # type: ignore[union-attr]
            if (
                len(items) != 4
                or not isinstance(items[1], Sym)
                or not isinstance(items[2], str)
            ):
                raise JanetSyntaxError('expected (def sym "path" body)')
            refs[items[1].name] = items[2]
        elif _is_head(form, PROG):
            result.append(_program(form, refs))  # type: ignore[arg-type]
        else:
            result.append(to_json(form))
    if len(result) != 1:
        raise JanetSyntaxError(f"expected one value form, got {len(result)}")
    return result[0]
