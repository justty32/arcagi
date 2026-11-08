from arcagi.seed.prims import PRIMS
from arcagi.seed.types import (
    BOOL,
    INPUT,
    INT,
    FnT,
    ListT,
    VarT,
    is_ground,
    parse,
    resolve,
    show,
    unify,
)


def test_parse_show_roundtrip():
    for text in [
        "int",
        "bool",
        "list[list[int]]",
        "(a) -> b",
        "((a, b) -> c, list[a], list[b]) -> list[c]",
        "(list[int]) -> (int) -> bool",
    ]:
        assert show(parse(text)) == text
    assert parse("int -> bool") == FnT((INT,), BOOL)
    assert INPUT == ListT(ListT(INT))


def test_unify_binds_and_resolves():
    a, b = VarT("a"), VarT("b")
    s = unify(ListT(a), INPUT)
    assert s is not None and resolve(a, s) == ListT(INT)
    s = unify(FnT((a,), b), FnT((INT,), ListT(a)))
    assert s is not None and resolve(b, s) == ListT(INT)
    assert unify(INT, BOOL) is None
    assert unify(a, ListT(a)) is None  # occurs check
    assert unify(FnT((INT,), INT), FnT((INT, INT), INT)) is None


def test_prim_signatures_are_functions():
    for p in PRIMS.values():
        assert isinstance(p.sig, FnT)
        assert not is_ground(p.sig) or p.sig.args
