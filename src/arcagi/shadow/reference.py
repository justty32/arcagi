"""Agreement of shadow verdicts with S5's per-block overfit labels.

``reports/synth-s5/overfit.json`` (``scripts/synth_overfit.py``) gives, per
block, its original support and per claim the strict synthetic pass and the
chunk pass rate. Two reference labels per block (``good`` / ``bad``):

* ``majority``: >= 2/3 of its claims have chunk pass rate >= 0.5 (the shadow
  rule recomputed independently by S5: a consistency check);
* ``strict``: >= 2/3 of its claims survive all 24 synthetic pairs.

Only the synthetic part of the gate is compared (duplicates are a catalog
question, not a memorisation one); blocks missing from either side are skipped.
"""

import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from . import CHUNK_MAJORITY, MIN_SYNTH_FRAC


def labels(overfit: Path) -> dict[str, dict[str, bool]]:
    """Block name -> {"majority": good?, "strict": good?} from S5 claims."""
    data = json.loads(Path(overfit).read_text())
    claims = defaultdict(list)
    for row in data["claims"]:
        claims[row["block"]].append(row)
    out = {}
    for block in data["blocks"]:
        rows = claims.get(block["block"], [])
        if not rows:
            continue
        maj = sum(r["chunk_pass_rate"] >= CHUNK_MAJORITY for r in rows) / len(rows)
        strict = sum(r["synth_pass"] for r in rows) / len(rows)
        out[block["block"]] = {
            "majority": maj + 1e-9 >= MIN_SYNTH_FRAC,
            "strict": strict + 1e-9 >= MIN_SYNTH_FRAC,
        }
    return out


def synth_good(result: dict) -> bool:
    """Shadow verdict restricted to support + synthetic majority."""
    return bool(result["support"]) and not any(
        w.startswith(("synth", "no training")) for w in result["reasons"]
    )


def confusion(results: Sequence[dict], ref: dict[str, dict[str, bool]]) -> dict:
    """Per reference label: counts of (shadow, reference) good/bad and agreement."""
    out = {}
    for label in ("majority", "strict"):
        table = {"good/good": 0, "good/bad": 0, "bad/good": 0, "bad/bad": 0}
        for r in results:
            if r["name"] not in ref:
                continue
            ours = "good" if synth_good(r) else "bad"
            theirs = "good" if ref[r["name"]][label] else "bad"
            table[f"{ours}/{theirs}"] += 1
        n = sum(table.values())
        agree = table["good/good"] + table["bad/bad"]
        out[label] = table | {"n": n, "agreement": round(agree / n, 3) if n else None}
    return out


__all__ = ["confusion", "labels", "synth_good"]
