"""Two conserved credit layers, using epoch-local solution differences."""

import math
from collections import defaultdict
from collections.abc import Callable, Mapping
from pathlib import Path

from arcagi.hammer.formats import NODES, read_json, read_jsonl

from . import boundary, cost

SPLIT = {"root_keep": 0.2, "node_keep": 0.2, "op_star": 0.7, "op_base": 0.1}
OP_NODE = {"comb": "solve", "decomp": "solve", "gate": "gate", "route": "route"}


def amounts(curves: Mapping[int, dict[str, str]]) -> dict[int, float]:
    """Compute unrounded cumulative efficiency differences (epoch 0 is baseline)."""
    total_evals = auc = 0
    previous = 0.0
    result = {}
    for epoch, row in curves.items():
        total_evals += sum(
            int(row[field]) for field in cost.FIELDS if field.startswith("evals_")
        )
        if total_evals <= 0:
            raise ValueError(
                f"epoch {epoch}: efficiency needs positive cumulative evals"
            )
        if epoch:
            auc += int(row["solved_L"])
            eff = auc / (total_evals / 1_000_000)
            result[epoch] = eff - previous
            previous = eff
    return result


def live_ops(root: Path, epoch: int) -> dict[str, list[str]]:
    """Use historical comb blocks and the documented terminal non-comb proxy."""
    result = {name: [] for name in NODES}
    blocks = read_json(root / "epochs" / str(epoch) / "blocks.json")
    result["solve"] = [f"comb_{block['name']}" for block in blocks]
    for op in read_jsonl(root / "ops.jsonl"):
        if (
            op["kind"] != "comb"
            and op["status"] == "live"
            and op.get("born", {}).get("epoch", 0) <= epoch
        ):
            if op["kind"] not in OP_NODE:
                raise ValueError(f"unmapped live op kind: {op['kind']}")
            result[OP_NODE[op["kind"]]].append(op["id"])
    for name, ids in result.items():
        if len(set(ids)) != len(ids):
            raise ValueError(f"epoch {epoch}: duplicate live op in {name}")
        ids.sort()
    return result


def new_solves(
    root: Path, epoch: int, block_refs: Callable[[object], set[str]]
) -> tuple[dict[str, list[str]], list[str]]:
    """Attribute each newly train-correct L16 task once per explicit blk name."""

    def solved(t: int) -> dict[str, set[str]]:
        result = defaultdict(set)
        for row in read_jsonl(root / "epochs" / str(t) / "solutions.jsonl"):
            if row["set"] == "L16" and row["train_ok"]:
                result[row["task_id"]].update(block_refs(row["program"]))
        return result

    previous, current = solved(epoch - 1), solved(epoch)
    tasks = defaultdict(list)
    unassigned = []
    for task_id in sorted(current.keys() - previous.keys()):
        refs = current[task_id]
        if not refs:
            unassigned.append(task_id)
        for name in sorted(refs):
            tasks[f"comb_{name}"].append(task_id)
    return dict(tasks), unassigned


def _parts(amount: float, weights: list[float]) -> list[float]:
    """Allocate proportionally, giving the final recipient the remainder."""
    if not weights or sum(weights) <= 0:
        raise ValueError("allocation needs positive total weight")
    total = sum(weights)
    result = [amount * weight / total for weight in weights[:-1]]
    return [*result, amount - sum(result)]


def allocate(
    epoch: int,
    amount: float,
    weights: dict[str, float],
    live: dict[str, list[str]],
    tasks: dict[str, list[str]],
) -> list[dict]:
    """Split a positive, negative or zero amount without mixing the two layers."""
    if not math.isfinite(amount):
        raise ValueError("amount must be finite")
    for weight in weights.values():
        if type(weight) not in (float, int) or not math.isfinite(weight) or weight < 0:
            raise ValueError("weights must be finite nonnegative numbers")
    # Zero-weight nodes retain explicit zero rows; the final positive recipient
    # absorbs rounding so inactive nodes never receive a numerical remainder.
    names = sorted(weights, key=lambda name: weights[name] > 0)
    root_keep = SPLIT["root_keep"] * amount
    node_amounts = _parts(amount - root_keep, [weights[name] for name in names])
    rows = []

    def add(
        layer: int,
        source: str,
        target: str,
        value: float,
        share: str,
        solves: list[str] | None = None,
    ) -> None:
        rows.append(
            {
                "schema": "t2-credit/1",
                "epoch": epoch,
                "layer": layer,
                "from": source,
                "to": target,
                "amount": value,
                "why": {"share": share, "new_solves": solves or [], "d_eff": amount},
            }
        )

    add(1, "root", "keep", root_keep, "keep")
    # Reconcile against the entire group, including root retention.
    node_amounts[-1] = amount - sum([root_keep, *node_amounts[:-1]])
    for name, value in zip(names, node_amounts, strict=True):
        add(1, "root", f"nodes/{name}", value, "weight")
    for name, value in zip(names, node_amounts, strict=True):
        if name not in OP_NODE.values():
            continue
        source, ids = f"nodes/{name}", sorted(live.get(name, []))
        start = len(rows)
        if not ids:
            add(2, source, "keep", value, "keep")
            continue
        add(2, source, "keep", SPLIT["node_keep"] * value, "keep")
        base = _parts(SPLIT["op_base"] * value, [1] * len(ids))
        stars = [len(tasks.get(op, [])) for op in ids]
        star = _parts(SPLIT["op_star"] * value, stars if any(stars) else [1] * len(ids))
        for op, share in zip(ids, base, strict=True):
            add(2, source, f"ops/{op}", share, "base")
        for op, share in zip(ids, star, strict=True):
            add(2, source, f"ops/{op}", share, "star", tasks.get(op))
        rows[-1]["amount"] = value - sum(row["amount"] for row in rows[start:-1])
    return rows


def build(root: Path, deltas: dict[int, float], block_refs: Callable) -> tuple:
    """Produce credit, same-layer subtree totals and attribution diagnostics."""
    weights = {}
    for name in NODES:
        meta = read_json(root / "nodes" / name / "_metainfo.json")
        weights[name] = meta["weight"] if meta["status"] == "active" else 0
    rows, diagnostics = [], {}
    totals = {f"nodes/{name}": 0.0 for name in NODES}
    for epoch, amount in deltas.items():
        boundary.check_stop()
        tasks, unassigned = new_solves(root, epoch, block_refs)
        live = live_ops(root, epoch)
        epoch_rows = allocate(epoch, amount, weights, live, tasks)
        rows.extend(epoch_rows)
        for row in epoch_rows:
            if row["layer"] == 1 and row["to"] != "keep":
                totals[row["to"]] += row["amount"]
        diagnostics[str(epoch)] = {
            "unassigned": unassigned,
            "attributed": tasks,
            "live_ops": sum(len(ids) for ids in live.values()),
        }
    return rows, totals, diagnostics


def check(
    rows: list[dict], expected: list[dict], totals: dict, deltas: dict[int, float]
) -> tuple[dict, dict]:
    """Independently check grouped conservation, allocations and op coverage."""

    def key(row: dict) -> tuple:
        return (row["epoch"], row["layer"], row["from"], row["to"], row["why"]["share"])

    errors, groups, actual = [], defaultdict(list), {}
    for row in rows:
        identity = key(row)
        where = f"epoch={row['epoch']} layer={row['layer']} from={row['from']}"
        if (
            row["schema"] != "t2-credit/1"
            or type(row["epoch"]) is not int
            or type(row["layer"]) is not int
            or row["layer"] not in (1, 2)
            or type(row["amount"]) not in (int, float)
            or not math.isfinite(row["amount"])
        ):
            raise ValueError(f"{where}: invalid credit schema/amount")
        if identity in actual:
            errors.append(f"{where}: duplicate credit recipient/share")
        actual[identity] = row
        groups[(row["epoch"], row["layer"], row["from"])].append(row["amount"])
    reference = {key(row): row for row in expected}
    max_allocation_error = 0.0
    for identity in actual.keys() | reference.keys():
        epoch, layer, source, target, _ = identity
        where = f"epoch={epoch} layer={layer} from={source} to={target}"
        if identity not in actual or identity not in reference:
            errors.append(f"{where}: missing or unexpected credit row")
            continue
        difference = abs(actual[identity]["amount"] - reference[identity]["amount"])
        max_allocation_error = max(max_allocation_error, difference)
        if difference > 1e-9 or actual[identity]["why"] != reference[identity]["why"]:
            errors.append(f"{where}: allocation or epoch evidence differs")
    upper = {(t, 1, "root"): amount for t, amount in deltas.items()}
    for row in rows:
        if row["layer"] == 1 and row["to"] != "keep":
            name = row["to"].removeprefix("nodes/")
            if name in OP_NODE.values():
                upper[(row["epoch"], 2, row["to"])] = row["amount"]
    residuals = []
    for group in upper.keys() | groups.keys():
        residual = abs(sum(groups.get(group, [])) - upper.get(group, 0))
        residuals.append(residual)
        if residual > 1e-9:
            errors.append(
                f"epoch={group[0]} layer={group[1]} "
                f"from={group[2]}: residual={residual}"
            )
    expected_totals = {f"nodes/{name}": 0.0 for name in NODES}
    for row in expected:
        if row["layer"] == 1 and row["to"] != "keep":
            expected_totals[row["to"]] += row["amount"]
    if totals != expected_totals:
        errors.append("by_subtree differs from first-layer node totals")
    required = {
        (r["epoch"], r["from"], r["to"])
        for r in expected
        if r["layer"] == 2 and r["to"].startswith("ops/")
    }
    covered = {
        (r["epoch"], r["from"], r["to"])
        for r in rows
        if r["layer"] == 2 and r["to"].startswith("ops/")
    }
    missing, extra = sorted(required - covered), sorted(covered - required)
    coverage_errors = [
        f"epoch={t} node={node}: uncovered {op}" for t, node, op in missing
    ]
    coverage_errors += [
        f"epoch={t} node={node}: unexpected {op}" for t, node, op in extra
    ]
    return (
        {
            "pass": not errors,
            "groups": len(upper),
            "max_residual": max(residuals, default=0),
            "max_allocation_error": max_allocation_error,
            "errors": errors,
        },
        {
            "pass": not coverage_errors,
            "live_op_epochs": len(required),
            "covered": len(required & covered),
            "missing": len(missing),
            "coverage": len(required & covered) / len(required) if required else 1.0,
            "errors": coverage_errors,
        },
    )
