"""G1 gate: parameters come from the live ``kind: gate`` row.

The gate itself (MDL: size < train output cells / mdl_div; leave-one-out
re-search at ``loo_frac`` of the budget when the task has >= loo_min_pairs
train pairs, D-r8-6) runs inside ``body.solve_batch`` (arcbatch re-searches).
"""

from . import formats as fm

BODY_KEYS = ("mdl_div", "loo_frac", "loo_min_pairs")


def live_params(ops: list[dict]) -> dict:
    """Params of the live gate row (first by id), defaults filled in."""
    rows = sorted((o for o in ops if o["kind"] == "gate" and o["status"] == "live"),
                  key=lambda o: o["id"])
    return {**fm.GATE_G1, **(rows[0]["payload"]["params"] if rows else {})}


def body_gate(params: dict) -> dict:
    return {k: params[k] for k in BODY_KEYS}
