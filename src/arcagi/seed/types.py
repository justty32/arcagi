"""Types of the seed language: int, bool, list[T], function types, type variables.

Types are immutable and hashable so they can key value banks. ``unify`` works on
a substitution dict (variable name -> type) and never mutates its input.
"""

from __future__ import annotations

from dataclasses import dataclass


class Type:
    """Base class of all seed types."""

    __slots__ = ()

    def __str__(self) -> str:
        return show(self)


@dataclass(frozen=True, slots=True)
class IntT(Type):
    pass


@dataclass(frozen=True, slots=True)
class BoolT(Type):
    pass


@dataclass(frozen=True, slots=True)
class ListT(Type):
    elem: Type


@dataclass(frozen=True, slots=True)
class FnT(Type):
    args: tuple[Type, ...]
    ret: Type


@dataclass(frozen=True, slots=True)
class VarT(Type):
    name: str


INT = IntT()
BOOL = BoolT()
INPUT = ListT(ListT(INT))  # task inputs and outputs are list[list[int]]

Subst = dict[str, Type]


def resolve(t: Type, s: Subst) -> Type:
    """Apply a substitution fully."""
    if isinstance(t, VarT):
        bound = s.get(t.name)
        return t if bound is None else resolve(bound, s)
    if isinstance(t, ListT):
        return ListT(resolve(t.elem, s))
    if isinstance(t, FnT):
        return FnT(tuple(resolve(a, s) for a in t.args), resolve(t.ret, s))
    return t


def _occurs(name: str, t: Type, s: Subst) -> bool:
    t = resolve(t, s)
    if isinstance(t, VarT):
        return t.name == name
    if isinstance(t, ListT):
        return _occurs(name, t.elem, s)
    if isinstance(t, FnT):
        return any(_occurs(name, a, s) for a in t.args) or _occurs(name, t.ret, s)
    return False


def unify(a: Type, b: Type, s: Subst | None = None) -> Subst | None:
    """Return an extended substitution making ``a`` and ``b`` equal, or None."""
    s = {} if s is None else s
    a = _walk(a, s)
    b = _walk(b, s)
    if a == b:
        return s
    if isinstance(a, VarT):
        if _occurs(a.name, b, s):
            return None
        return {**s, a.name: b}
    if isinstance(b, VarT):
        return unify(b, a, s)
    if isinstance(a, ListT) and isinstance(b, ListT):
        return unify(a.elem, b.elem, s)
    if isinstance(a, FnT) and isinstance(b, FnT):
        if len(a.args) != len(b.args):
            return None
        for x, y in zip(a.args, b.args, strict=True):
            s = unify(x, y, s)
            if s is None:
                return None
        return unify(a.ret, b.ret, s)
    return None


def _walk(t: Type, s: Subst) -> Type:
    while isinstance(t, VarT) and t.name in s:
        t = s[t.name]
    return t


def is_ground(t: Type) -> bool:
    if isinstance(t, VarT):
        return False
    if isinstance(t, ListT):
        return is_ground(t.elem)
    if isinstance(t, FnT):
        return all(is_ground(a) for a in t.args) and is_ground(t.ret)
    return True


def show(t: Type) -> str:
    """Render a type in the syntax accepted by ``parse``."""
    if isinstance(t, IntT):
        return "int"
    if isinstance(t, BoolT):
        return "bool"
    if isinstance(t, VarT):
        return t.name
    if isinstance(t, ListT):
        return f"list[{show(t.elem)}]"
    if isinstance(t, FnT):
        return f"({', '.join(show(a) for a in t.args)}) -> {show(t.ret)}"
    raise TypeError(t)


def parse(text: str) -> Type:
    """Parse ``int``, ``bool``, ``list[T]``, ``(A, B) -> R``, ``A -> R`` or a var."""
    toks = _tokens(text)
    t, i = _parse(toks, 0)
    if i != len(toks):
        raise ValueError(f"trailing tokens in type: {text!r}")
    return t


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith("->", i):
            out.append("->")
            i += 2
        elif c in "[](),":
            out.append(c)
            i += 1
        else:
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            if j == i:
                raise ValueError(f"bad character in type: {text!r}")
            out.append(text[i:j])
            i = j
    return out


def _parse(toks: list[str], i: int) -> tuple[Type, int]:
    if i < len(toks) and toks[i] == "(":
        args: list[Type] = []
        i += 1
        while toks[i] != ")":
            a, i = _parse(toks, i)
            args.append(a)
            if toks[i] == ",":
                i += 1
        i += 1
        if i < len(toks) and toks[i] == "->":
            ret, i = _parse(toks, i + 1)
            return FnT(tuple(args), ret), i
        if len(args) != 1:
            raise ValueError("tuple types are not supported")
        return args[0], i
    head, i = _atom(toks, i)
    if i < len(toks) and toks[i] == "->":
        ret, i = _parse(toks, i + 1)
        return FnT((head,), ret), i
    return head, i


def _atom(toks: list[str], i: int) -> tuple[Type, int]:
    name = toks[i]
    if name == "int":
        return INT, i + 1
    if name == "bool":
        return BOOL, i + 1
    if name == "list":
        if toks[i + 1] != "[":
            raise ValueError("expected '[' after list")
        elem, j = _parse(toks, i + 2)
        if toks[j] != "]":
            raise ValueError("expected ']'")
        return ListT(elem), j + 1
    if name.isidentifier():
        return VarT(name), i + 1
    raise ValueError(f"bad type token {name!r}")
