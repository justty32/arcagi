"""Train-only learning bits, deterministic paired gates and calibration strata."""

import math
import statistics
from pathlib import Path

from arcagi.hammer.formats import read_json, read_jsonl

from . import boundary
from .refs import sha12

B_REF = 50_000


def bits_table(root: str | Path, epochs: int) -> dict:
    """Read exactly one L16 row per task in every real search epoch 0..E."""
    if epochs < 0:
        raise ValueError("epochs must be nonnegative")
    root = Path(root)
    ids = read_json(root / "truth/train/taskset.json")["L16"]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("task IDs must be nonempty and unique")
    table = {tid: {k: [] for k in ("b", "ntf", "train_ok", "test_ok")} for tid in ids}
    for e in range(epochs + 1):
        boundary.check_stop()
        path = root / "epochs" / str(e) / "solutions.jsonl"
        if not path.is_file():
            raise ValueError(f"missing epoch solutions: {path}")
        rows = [r for r in read_jsonl(path) if r["set"] == "L16"]
        if len(rows) != len(ids) or {r["task_id"] for r in rows} != set(ids):
            raise ValueError(f"expected exactly one solution row per task: {path}")
        for row in rows:
            ntf, ok = row["nodes_to_first"], row["train_ok"]
            if type(ok) is not bool or type(row["test_ok"]) is not bool:
                raise ValueError("train_ok/test_ok must be booleans")
            if ntf is not None and (type(ntf) is not int or ntf < 0):
                raise ValueError("nodes_to_first must be a nonnegative integer or null")
            if ok and (ntf is None or ntf < 1):
                raise ValueError("train success needs positive nodes_to_first")
            bits = math.log2(B_REF) - math.log2(min(ntf, B_REF)) if ok else 0.0
            item = table[row["task_id"]]
            for key, value in zip(
                ("b", "ntf", "train_ok", "test_ok"),
                (bits, ntf, ok, row["test_ok"]),
                strict=True,
            ):
                item[key].append(value)
    return table


def components(item: dict) -> dict:
    """Return one task's base and gain without crediting epoch zero twice."""
    base = item["b"][0]
    gain = sum(b - base for b in item["b"][1:])
    return {"base_bits": base, "gain_bits": gain}


def score(table: dict, *, wall_s: float = 0.0) -> dict:
    """Aggregate bits; test answers contribute only the legacy AUC diagnostic."""
    rows = [(item, components(item)) for item in table.values()]
    return {
        "base_bits": sum(c["base_bits"] for _, c in rows),
        "gain_bits": sum(c["gain_bits"] for _, c in rows),
        "transfer_bits": sum(c["gain_bits"] for i, c in rows if not i["train_ok"][0]),
        "new_solves": sum(
            not i["train_ok"][0] and any(i["train_ok"][1:]) for i, _ in rows
        ),
        "auc_L": sum(sum(i["test_ok"][1:]) for i, _ in rows),
        "wall_s": wall_s,
    }


def load(value: dict | str | Path) -> dict:
    """Load a meter document from a run directory, report path or dictionary."""
    if isinstance(value, dict):
        return value
    path = Path(value)
    result = read_json(path / "meter.json" if path.is_dir() else path)
    if not result or result.get("schema") != "think4-meter/1":
        raise ValueError(f"unsupported or missing meter report: {path}")
    return result


def compare(
    a: dict | str | Path, b: dict | str | Path, metric: str = "gain_bits"
) -> dict:
    """Compare B minus A with closed-form sigma and ordered odd/even halves."""
    if metric not in ("gain_bits", "base_bits"):
        raise ValueError("only gain_bits and base_bits may enter a decision")
    a, b = load(a), load(b)
    ids = a["task_ids"]
    if (
        ids != b["task_ids"]
        or set(ids) != set(a["per_task"])
        or set(ids) != set(b["per_task"])
    ):
        raise ValueError("meter comparison needs identical ordered tasksets")
    if a["cfg"] != b["cfg"]:
        raise ValueError("meter comparison needs identical cfg")
    d = [
        components(b["per_task"][t])[metric] - components(a["per_task"][t])[metric]
        for t in ids
    ]
    delta = sum(d)
    sigma = math.sqrt(len(d)) * statistics.pstdev(d)
    halves = [sum(d[::2]), sum(d[1::2])]
    same_sign = all(h * delta > 0 for h in halves)
    all_equal = sigma == 0 and delta != 0
    z = delta / sigma if sigma else None
    significant = (
        abs(delta) >= 2
        and same_sign
        and (abs(z) >= 2 if z is not None else all_equal and len(d) >= 4)
    )
    return {
        "metric": metric,
        "delta": delta,
        "sigma": sigma,
        "z": z,
        "halves": halves,
        "halves_same_sign": same_sign,
        "all_equal": all_equal,
        "n_tasks": len(d),
        "per_task_delta": dict(zip(ids, d, strict=True)),
        "significant": significant,
    }


def sign_test(
    a: dict | str | Path, b: dict | str | Path, metric: str = "gain_bits"
) -> dict:
    """Return the exact one-sided negative sign test for paired B minus A."""
    paired = compare(a, b, metric)
    differences = paired["per_task_delta"].values()
    k = sum(d < 0 for d in differences)
    n_pos = sum(d > 0 for d in differences)
    n = k + n_pos
    return {
        "metric": metric,
        "n": n,
        "k": k,
        "n_pos": n_pos,
        "p_neg": sum(math.comb(n, j) for j in range(k, n + 1)) / 2**n,
        "delta": paired["delta"],
        "halves": paired["halves"],
        "halves_same_sign": paired["halves_same_sign"],
    }


def select_taskset(calib: dict | str | Path) -> dict:
    """Classify using train evidence only; keep all learned/sped tasks."""
    calib = load(calib)
    groups = {k: [] for k in ("learned", "sped", "edge", "never", "trivial")}
    classes = {}
    for tid in sorted(calib["per_task"]):
        i = calib["per_task"][tid]
        if not i["train_ok"][0]:
            kind = "learned" if any(i["train_ok"][1:]) else "never"
        elif max(i["b"][1:], default=i["b"][0]) - i["b"][0] >= 1:
            kind = "sped"
        else:
            kind = "edge" if i["ntf"][0] >= 1000 else "trivial"
        groups[kind].append(tid)
        classes[tid] = {
            "class": kind,
            "b": i["b"],
            "ntf": i["ntf"],
            "train_ok": i["train_ok"],
        }
    learning = groups["learned"] + groups["sped"]
    ids = learning + groups["edge"][: min(4, max(0, 16 - len(learning)))]
    ids += groups["never"][:4]
    return {
        "schema": "think4-taskset/1",
        "task_ids": ids,
        "taskset_sha": sha12(ids),
        "classes": classes,
        "groups": groups,
        "calibration_genome_sha": calib["genome_sha"],
        "cfg": calib["cfg"],
        "learning_tasks": len(learning),
        "needs_targeted": len(learning) < 4,
        "within_target": 16 <= len(ids) <= 24,
        "diagnosis": "剝光後看不到學習" if len(learning) < 4 else "",
    }
