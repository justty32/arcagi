"""Type signature inference for G1 templates (read-only use of seed.types).

Returns the type string expected by ``seed.library.Block``: with k holes a
function type of the k hole types to the body type, else the body type.
"""

from arcagi.seed import types as ty
from arcagi.seed.prims import PRIMS

from . import prog as pg


class _FailError(Exception):
    pass


class _Infer:
    def __init__(self, blocks: dict) -> None:
        self.n = 0
        self.s: dict = {}
        self.blocks = blocks
        self.holes: dict[str, ty.Type] = {}

    def fresh(self) -> ty.Type:
        self.n += 1
        return ty.VarT(f"v{self.n}")

    def inst(self, t: ty.Type) -> ty.Type:
        names: dict[str, ty.Type] = {}

        def rec(x):
            if isinstance(x, ty.VarT):
                names.setdefault(x.name, self.fresh())
                return names[x.name]
            if isinstance(x, ty.ListT):
                return ty.ListT(rec(x.elem))
            if isinstance(x, ty.FnT):
                return ty.FnT(tuple(rec(a) for a in x.args), rec(x.ret))
            return x

        return rec(t)

    def unify(self, a, b) -> None:
        s = ty.unify(a, b, self.s)
        if s is None:
            raise _FailError
        self.s = s

    def apply(self, fn_t: ty.FnT, args, env) -> ty.Type:
        if len(args) != len(fn_t.args):
            raise _FailError
        for a, want in zip(args, fn_t.args, strict=True):
            self.unify(self.infer(a, env), want)
        return fn_t.ret

    def infer(self, p, env: tuple) -> ty.Type:
        if isinstance(p, int):
            return ty.INT
        head = p[0]
        if head == "$in":
            return ty.INPUT
        if head in ("$0", "$1"):
            if not env:
                raise _FailError
            params = env[-1]
            i = int(head[1])
            if i >= len(params):
                raise _FailError
            return params[i]
        if head.startswith(pg.HOLE_PREFIX):
            return self.holes.setdefault(head, self.fresh())
        if head == "lam":
            params = tuple(self.fresh() for _ in range(p[1]))
            return ty.FnT(params, self.infer(p[2], (*env, params)))
        if head == "blk":
            b = self.blocks.get(p[1])
            if b is None:
                raise _FailError
            t = self.inst(ty.parse(b["sig"]) if isinstance(b["sig"], str) else b["sig"])
            if len(p) == 2:
                return t
            if not isinstance(t, ty.FnT):
                raise _FailError
            return self.apply(t, p[2:], env)
        prim = PRIMS.get(head)
        if prim is None:
            raise _FailError
        return self.apply(self.inst(prim.sig), p[1:], env)


def _rename(t: ty.Type) -> ty.Type:
    names: dict[str, ty.Type] = {}
    letters = "abcdefghijklmnop"

    def rec(x):
        if isinstance(x, ty.VarT):
            names.setdefault(x.name, ty.VarT(letters[len(names)]))
            return names[x.name]
        if isinstance(x, ty.ListT):
            return ty.ListT(rec(x.elem))
        if isinstance(x, ty.FnT):
            return ty.FnT(tuple(rec(a) for a in x.args), rec(x.ret))
        return x

    return rec(t)


def infer_sig(body, blocks: dict | None = None) -> str | None:
    """Signature string for a template body, or None if it does not type."""
    inf = _Infer(blocks or {})
    try:
        ret = inf.infer(body, ())
    except _FailError:
        return None
    k = len({s[0] for s in pg.subtrees(body) if pg.is_hole(s)})
    ret = ty.resolve(ret, inf.s)
    if k:
        args = tuple(
            ty.resolve(inf.holes[f"{pg.HOLE_PREFIX}{i}"], inf.s) for i in range(k)
        )
        t: ty.Type = ty.FnT(args, ret)
    else:
        t = ret
    return ty.show(_rename(t))
