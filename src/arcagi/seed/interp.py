"""Interpreter for seed programs.

Program forms (nested tuples)::

    ("op", *args)          primitive application, op in PRIMS
    ("$in",)               the task input
    ("$0",) / ("$1",)      innermost lambda parameters (de Bruijn style)
    ("lam", n, body)       lambda with n in {1, 2} parameters
    ("blk", name, *args)   library block; args go into its holes $h0..$h1
    int                    integer literal

Blocks are expanded syntactically (holes replaced by argument programs) before
evaluation, so a hole inside a lambda may refer to that lambda's parameters.
Every node evaluation costs one step; exceeding the limit raises ``EvalError``
as does any other failure.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .prims import PRIMS

if TYPE_CHECKING:
    from .library import Library

Program = tuple | int
MAX_STEPS = 200_000
HOLES = ("$h0", "$h1")


class EvalError(Exception):
    """Any failure while evaluating a program."""


class StepLimitError(EvalError):
    pass


# A compiled node takes (ctx, env); ctx = [input, steps_left], env = lambda args.
Node = Callable[[list, tuple], Any]


def expand(prog: Program, lib: Library | None) -> Program:
    """Inline library blocks so the result uses primitives only."""
    if isinstance(prog, int) or not prog:
        return prog
    head = prog[0]
    if head == "blk":
        if lib is None or prog[1] not in lib.by_name:
            raise EvalError(f"unknown block {prog[1]!r}")
        args = tuple(expand(a, lib) for a in prog[2:])
        body = expand(lib.by_name[prog[1]].body, lib)
        return substitute(body, args)
    if head == "lam":
        return ("lam", prog[1], expand(prog[2], lib))
    if len(prog) == 1:
        return prog
    return (head, *(expand(a, lib) for a in prog[1:]))


def substitute(body: Program, args: tuple) -> Program:
    """Replace hole leaves $hK by ``args[K]``."""
    if isinstance(body, int):
        return body
    if len(body) == 1:
        name = body[0]
        if name in HOLES:
            k = HOLES.index(name)
            if k >= len(args):
                raise EvalError(f"missing argument for {name}")
            return args[k]
        return body
    if body[0] == "lam":
        return ("lam", body[1], substitute(body[2], args))
    return (body[0], *(substitute(a, args) for a in body[1:]))


def compile_prog(prog: Program) -> Node:
    """Compile a block-free program into a closure ``f(ctx, env)``."""
    if isinstance(prog, bool) or not isinstance(prog, (int, tuple)):
        raise EvalError(f"bad program node {prog!r}")
    if isinstance(prog, int):
        k = prog

        def const(ctx: list, env: tuple) -> int:
            return k

        return const
    head = prog[0]
    if head == "$in":
        return _input
    if head in ("$0", "$1"):
        idx = int(head[1])

        def var(ctx: list, env: tuple) -> Any:
            return env[idx]

        return var
    if head == "lam":
        n, body = prog[1], compile_prog(prog[2])
        if n not in (1, 2):
            raise EvalError(f"bad lambda arity {n}")

        def lam(ctx: list, env: tuple) -> Callable:
            return lambda *a: body(ctx, a)

        return lam
    prim = PRIMS.get(head)
    if prim is None:
        raise EvalError(f"unknown op {head!r}")
    if len(prog) - 1 != prim.arity:
        raise EvalError(f"{head} expects {prim.arity} args")
    fn = prim.fn
    kids = tuple(compile_prog(a) for a in prog[1:])
    if len(kids) == 1:
        (k0,) = kids

        def app1(ctx: list, env: tuple) -> Any:
            ctx[1] -= 1
            if ctx[1] < 0:
                raise StepLimitError("step limit")
            return fn(k0(ctx, env))

        return app1

    def app(ctx: list, env: tuple) -> Any:
        ctx[1] -= 1
        if ctx[1] < 0:
            raise StepLimitError("step limit")
        return fn(*[k(ctx, env) for k in kids])

    return app


def _input(ctx: list, env: tuple) -> Any:
    return ctx[0]


def to_value(x: Any) -> Any:
    """Convert nested lists to the internal tuple form."""
    if isinstance(x, (list, tuple)):
        return tuple(to_value(v) for v in x)
    return x


def run(
    prog: Program,
    x: Any,
    lib: Library | None = None,
    max_steps: int = MAX_STEPS,
) -> Any:
    """Evaluate ``prog`` on input ``x``; every failure becomes ``EvalError``."""
    try:
        node = compile_prog(expand(prog, lib))
        return node([to_value(x), max_steps], ())
    except EvalError:
        raise
    except Exception as exc:
        raise EvalError(f"{type(exc).__name__}: {exc}") from exc


def size(prog: Program) -> int:
    """Number of nodes. The lambda binder itself is free (a lambda costs its
    body); a block reference costs one plus its arguments."""
    if isinstance(prog, int) or len(prog) == 1:
        return 1
    if prog[0] == "lam":
        return size(prog[2])
    if prog[0] == "blk":
        return 1 + sum(size(a) for a in prog[2:])
    return 1 + sum(size(a) for a in prog[1:])


def to_json(prog: Program) -> Any:
    if isinstance(prog, int):
        return prog
    return [to_json(p) if not isinstance(p, str) else p for p in prog]


def from_json(data: Any) -> Program:
    if isinstance(data, int):
        return data
    return tuple(from_json(p) if not isinstance(p, str) else p for p in data)
