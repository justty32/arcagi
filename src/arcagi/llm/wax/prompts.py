"""Wax request prompts (one per method) for a small local model.

All methods ask for a Python ``solve(grid)`` that calls ``step(tag, grid)``
after every whole-grid transform; the program is run locally and only its
trajectory is kept (the wax). They differ in how hard they steer each step
towards the empty tree's language (32 list primitives, ``seed.prims``):

* ``base``: the r09 foundry rules only (control).
* ``prims``: + the 32 primitives and "each step = a few nodes of these".
* ``prims_py``: + the primitives as Python helpers ``P.<name>``; each step
  must be one expression over ``P`` (no loops / comprehensions).
* ``prims_shot``: ``prims_py`` + one worked example on another task.
"""

from __future__ import annotations

METHODS = ("base", "prims", "prims_py", "prims_shot")

PRIM_LIST = """\
Integers: add(a,b) sub(a,b) mul(a,b) neg(a) mod(a,b) max(a,b) min(a,b)
Booleans: eq(a,b) lt(a,b) and(a,b) or(a,b) not(a) if(cond,then,else)
Lists:    len(xs) nth(xs,i) head(xs) last(xs) take(n,xs) drop(n,xs)
          reverse(xs) cons(x,xs) append(xs,ys) concat(xss) range(n)
          repeat(n,x) count(x,xs) sort(xs)
Higher:   map(f,xs) filter(f,xs) zipwith(f,xs,ys) fold(f,z,xs) transpose(xss)
A grid is a list of rows; a row is a list of ints 0-9. Lambdas take 1-2
arguments and their body may only see their own arguments (not outer ones).
Constants allowed: 0, 1, -1 and numbers that occur in the task."""

CHEAP = """\
Cheap steps (2-6 nodes) look like:
  flip rows upside down          reverse(g)
  mirror each row                map(lambda r: reverse(r), g)
  transpose                      transpose(g)
  keep first 3 rows              take(3, g)
  drop first column              map(lambda r: drop(1, r), g)
  stack grid on its mirror       append(g, reverse(g))
  double each row                map(lambda r: append(r, r), g)
  sort each row                  map(lambda r: sort(r), g)
Expensive (often impossible): per-cell colour rules with conditions,
object detection, flood fill, anything needing loops over coordinates.
So split the solution into MANY tiny steps of the cheap kind; if a colour
change is needed, make it its own step that changes as little as possible."""

PY_HELPERS = """\
In your code a ready-made object P has exactly these functions:
P.add P.sub P.mul P.neg P.mod P.max P.min P.eq P.lt P.and_ P.or_ P.not_
P.if_ P.len P.nth P.head P.last P.take P.drop P.reverse P.cons P.append
P.concat P.range P.repeat P.count P.sort P.map P.filter P.zipwith P.fold
P.transpose   (lists in, lists out; map/filter/zipwith/fold take a lambda)
Each step must be ONE expression built only from P.* calls and lambdas,
for example: g = step("mirror_rows", P.map(lambda r: P.reverse(r), g)).
No for/while loops, no list comprehensions, no indexing like g[i][j]."""

SHOT = """\
Worked example (a different task): every output is the input rotated by
180 degrees and then stacked under the input.
```python
def solve(grid):
    g = grid
    r = step("flip_rows", P.reverse(g))
    r = step("mirror_rows", P.map(lambda row: P.reverse(row), r))
    g = step("stack", P.append(g, r))
    return g
```"""

BASE_RULES = """\
Rules:
- Write Python `def solve(grid):` that transforms the input grid step by
  step. After every whole-grid transform call `g = step("tag", g)`
  (step returns its argument). Use 2-8 steps; each step is a whole-grid
  transform (do not turn single cells of a loop into steps).
- The same tag must mean the same transform in every pair, and every pair
  must go through the same sequence of tags. The last step must equal the
  output. `step` is already defined; do not define it.
- Reply with one short ```python block only (no comments, no docstrings,
  no explanation)."""


def grid_text(g: list) -> str:
    return "\n".join("".join(str(c) for c in row) for row in g)


def task_text(task: dict) -> str:
    out = []
    for i, p in enumerate(task["train"]):
        out += [
            f"Pair {i} input ({len(p['input'])}x{len(p['input'][0])}):",
            grid_text(p["input"]),
            f"Pair {i} output ({len(p['output'])}x{len(p['output'][0])}):",
            grid_text(p["output"]),
            "",
        ]
    return "\n".join(out)


def build(method: str, task: dict) -> str:
    if method not in METHODS:
        raise ValueError(method)
    head = (
        "Solve this ARC puzzle. Each grid row is shown as a string of "
        "digits (colours 0-9); in code a grid is a list of lists of ints."
        "\n\n" + task_text(task)
    )
    parts = [head, BASE_RULES]
    if method != "base":
        parts += [
            "The steps will be re-learned by a tiny program search over "
            "these 32 primitives:\n" + PRIM_LIST,
            "Each step must be a small transform that a few (2-6) nodes "
            "of these primitives can write.\n" + CHEAP,
        ]
    if method in ("prims_py", "prims_shot"):
        parts.append(PY_HELPERS)
    if method == "prims_shot":
        parts.append(SHOT)
    return "\n\n".join(parts)
