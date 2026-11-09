"""Block-4 operators, rejection, conserved activity, caching and orchestration."""

import copy
import random
from pathlib import Path

import pytest

from arcagi.hammer import formats as fm
from arcagi.treegen import (
    boundary,
    bounds,
    check,
    crossover,
    fitness,
    ga,
    ga_fake,
    genome,
    guards,
    ledger,
    mutate,
    quick,
    refs,
)
from arcagi.treegen import select as selection
from arcagi.treegen.cli import main
from arcagi.treegen.export import export_tree


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(genome, "EVO", tmp_path / "evo")
    monkeypatch.setattr(genome, "SCRATCH", tmp_path / "t2e")
    monkeypatch.setattr(quick, "EVO", genome.EVO)
    taskset = tmp_path / "tasks.json"
    fm.write_json(
        taskset,
        {"learn": ["a", "b"], "P48": ["p"], "holdout": ["h8"], "holdout24": ["h24"]},
    )
    root = fm.init_root(tmp_path / "source", taskset)
    fm.write_ops(
        root,
        fm.load_ops(root)
        + [
            fm.new_op(
                "comb_alpha",
                "comb",
                {"name": "alpha", "body": ["$in"], "src_tasks": ["p"]},
                "user",
                0,
                status="live",
            ),
            fm.new_op(
                "comb_beta",
                "comb",
                {"name": "beta", "body": ["reverse", ["$in"]]},
                "user",
                0,
                status="dormant",
            ),
        ],
    )
    # File blobs must survive every candidate write and imported-root check.
    (root / "ctl").write_text("#!/bin/sh\nexit 0\n")
    (root / "ctl").chmod(0o755)
    path = tmp_path / "export/tree.json"
    doc = export_tree(root, path.parent)
    monkeypatch.setattr(genome, "PARENT", path)
    monkeypatch.setattr(guards, "LIVE_ROOT", root)
    monkeypatch.setattr(ga, "ACCEPT", tmp_path / "accept.json")
    monkeypatch.setattr(ga_fake, "REPORT", tmp_path / "fake.json")
    guide = tmp_path / "ledger"
    fm.write_jsonl(
        guide / "retire_suggest.jsonl",
        [
            {"op_id": "comb_beta", "verdict": "dormant-stale"},
            {"op_id": "decomp_nest", "verdict": "dormant-active"},
        ],
    )
    fm.write_jsonl(
        guide / "credit.jsonl",
        [
            {"layer": 1, "to": "ops/ignore", "amount": 999},
            {"layer": 2, "to": "ops/gate_g1", "amount": 4},
            {"layer": 2, "to": "ops/gate_g1", "amount": 5},
            {"layer": 2, "to": "ops/comb_alpha", "amount": -2},
        ],
    )
    return path, doc, root, guide


def validate(doc, sample, parents=None):
    path, parent, _, _ = sample
    return check.check(doc, parents or parent, files_dir=path.parent / "files")


def test_legal_parent_blobs_and_inherited_taint(sample):
    path, doc, _, _ = sample
    result = check.check(path, path)
    assert result["ok"] and not result["errors"]
    assert result["inherited_taint"][0]["op_id"] == "comb_alpha"
    assert check.check(doc, doc)["ok"]
    assert main(["ga-check", str(path), "--parent", str(path)]) == 0
    assert doc["genome_sha"] == refs.genome_sha(doc["defs"], doc["tree"])


def test_mutations_preserve_seals_bounds_and_original(sample):
    path, parent, _, guide_dir = sample
    original = copy.deepcopy(parent)
    guide = mutate.load_guide(guide_dir, parent)
    assert guide["high"][0] == "gate_g1" and guide["low"] == "comb_alpha"
    observed, arms = set(), set()
    for seed in range(100):
        child, record = mutate.mutate(parent, random.Random(seed), guide)
        observed.add(record["ops"][0]["op"])
        arms.add(record["arm"])
        assert not bounds.validate(genome.expanded(child))
        assert not genome.immutable_errors(
            genome.expanded(child), [genome.expanded(parent)]
        )
        assert child["genome_sha"] == refs.genome_sha(child["defs"], child["tree"])
        if seed < 8:
            assert validate(child, sample)["ok"]
    assert parent == original
    assert observed == {"M1", "M2", "M3", "M5"} and arms == {"guided", "uniform"}
    tree = genome.expanded(parent)
    choices = mutate.candidates(tree)
    assert all(o["kind"] != "gate" for o in choices["M2"] + choices["M3"])
    assert not any(o["id"] == "comb_alpha" for o in choices["M2"] + choices["M3"])
    tree["ops.jsonl"] = [o for o in tree["ops.jsonl"] if o["id"] != "decomp_nest"]
    assert not any(o["kind"] == "decomp" for o in mutate.candidates(tree)["M3"])
    assert mutate.target_weight("M3", {"id": "comb_beta"}, guide) == 4
    assert (
        mutate.target_weight("M2", {"id": "decomp_nest", "status": "dormant"}, guide)
        == 2
    )
    assert (
        mutate.target_weight("M2", {"id": "comb_alpha", "status": "live"}, guide) == 2
    )
    assert mutate.target_weight("M1", ("", {}, "", "gate_g1", ""), guide) == 2


@pytest.mark.parametrize(
    "field", ["id", "kind", "born", "by", "sig", "parent_route", "body", "src_tasks"]
)
def test_op_immutable_fields(sample, field):
    _, parent, _, _ = sample
    tree = genome.expanded(parent)
    op = next(o for o in tree["ops.jsonl"] if o["kind"] == "comb")
    if field in ("body", "src_tasks"):
        op["payload"][field] = ["forged"]
    elif field == "born":
        op[field]["epoch"] += 1
    else:
        op[field] = "forged"
    result = validate(genome.pack(parent, tree), sample)
    assert not result["ok"]
    assert any(
        e.startswith("alien_op:" if field == "id" else "immutable:")
        for e in result["errors"]
    )


@pytest.mark.parametrize(
    "case,prefix",
    [
        ("L", "immutable:"),
        ("epochs", "immutable:"),
        ("truth", "immutable:"),
        ("holdout", "immutable:"),
        ("taskset", "immutable:"),
        ("ctl", "immutable:"),
        ("weight", "bounds:"),
        ("priority", "bounds:"),
        ("judge", "bounds:"),
        ("gate", "bounds:"),
        ("bool", "immutable:"),
        ("gate_bool", "immutable:"),
        ("gate_delete", "gate_not_live:"),
        ("gate_dormant", "gate_not_live:"),
        ("comb", "missing_live_comb"),
        ("decomp", "missing_decomp"),
        ("alien", "alien_op:"),
        ("schema", "schema:"),
        ("sha", "genome_sha:"),
        ("ref", "dangling_ref:"),
        ("unused", "unused_def:"),
    ],
)
def test_structural_forgeries(sample, case, prefix):
    _, parent, _, _ = sample
    tree = genome.expanded(parent)
    frozen = tree["frozen.json"]
    if case in ("L", "epochs"):
        frozen["budgets"][case] += 1
    elif case == "truth":
        tree["truth"]["train"]["taskset.json"]["L16"][0] = "forged"
    elif case in ("holdout", "taskset"):
        frozen[case]["forged"] = True
    elif case == "ctl":
        tree["ctl"]["sha1"] = "0" * 40
    elif case == "weight":
        tree["nodes"]["grow"]["_metainfo.json"]["weight"] = 4.01
    elif case == "priority":
        next(o for o in tree["ops.jsonl"] if o["kind"] == "route")["payload"][
            "priority"
        ] = 999
    elif case == "judge":
        frozen["judge"]["stage2"]["se_mult"] = float("inf")
    elif case == "gate":
        tree["ops.jsonl"][0]["payload"]["params"]["m"] = -1
    elif case == "bool":
        frozen["judge"]["stage1"]["h24_regress"] = True
    elif case == "gate_bool":
        tree["ops.jsonl"][0]["payload"]["params"]["m"] = True
    elif case in ("gate_delete", "comb", "decomp"):
        kind = {"gate_delete": "gate", "comb": "comb", "decomp": "decomp"}[case]
        tree["ops.jsonl"] = [o for o in tree["ops.jsonl"] if o["kind"] != kind]
    elif case == "gate_dormant":
        tree["ops.jsonl"][0]["status"] = "dormant"
    elif case == "alien":
        op = copy.deepcopy(tree["ops.jsonl"][-2])
        op["id"] = "alien"
        tree["ops.jsonl"].append(op)
    elif case == "ref":
        tree["frozen.json"]["judge"] = {"$ref": "#/defs/deadbeef0000"}
    child = genome.pack(parent, tree)
    if case == "schema":
        child["schema"] = "invalid"
    elif case == "sha":
        child["genome_sha"] = "0" * 12
    elif case == "unused":
        child["defs"]["deadbeef0000"] = {"unused": True}
        child["genome_sha"] = refs.genome_sha(child["defs"], child["tree"])
    result = validate(child, sample)
    assert not result["ok"] and any(e.startswith(prefix) for e in result["errors"]), (
        result
    )
    if case == "alien":
        assert any(e.startswith("leak:") for e in result["errors"])


def test_expanded_crossover_order_refs_and_provenance(sample):
    _, parent, _, _ = sample
    a, b = genome.expanded(parent), genome.expanded(parent)
    a["ops.jsonl"] = [o for o in a["ops.jsonl"] if o["id"] != "decomp_halves"]
    b["frozen.json"]["judge"]["stage2"]["se_mult"] = 4
    # Repeated source tasks force definitions. Crossover must not copy refs
    # into a child without rebuilding its definitions.
    for tree in (a, b):
        for op in tree["ops.jsonl"]:
            op["payload"]["src_tasks"] = ["long_provenance_name" * 4]
    adoc, bdoc = genome.pack(parent, a), genome.pack(parent, b)
    assert adoc["defs"] and bdoc["defs"]
    for operator in ("X1", "X3"):
        child, record = crossover.cross(adoc, bdoc, random.Random(0), operator=operator)
        assert record["ops"][0]["op"] == operator and record["arm"] == "cross"
        assert not check.references(child)
        assert validate(child, sample, [adoc, bdoc])["ok"]
        if operator == "X1":
            assert [o["id"] for o in genome.expanded(child)["ops.jsonl"]] == [
                o["id"] for o in b["ops.jsonl"]
            ]
        else:
            assert (
                genome.expanded(child)["frozen.json"]["judge"]
                == b["frozen.json"]["judge"]
            )
    bad = genome.expanded(bdoc)
    bad["ops.jsonl"][0]["born"]["epoch"] += 1
    with pytest.raises(ValueError, match="immutable"):
        crossover.cross(adoc, genome.pack(bdoc, bad), random.Random(0))


def fake_quick(root, *, epochs, threads=4):
    """Write tiny epoch evidence; never enter the hammer search engine."""
    assert epochs == 4 and 1 <= threads <= 4
    metadata = fm.read_json(root / quick.PREPARED)
    assert metadata["cfg"]["L"] == 25000 and metadata["cfg"]["clear_p"]
    assert fm.read_json(root / "truth/train/taskset.json")["P"] == []
    for epoch in range(5):
        row = {
            "epoch": epoch,
            "solved_L": int(epoch > 0),
            "solved_P": 0,
            "solved_H8": 0,
            "solved_H24": 0,
            "logcost_L": 10 - epoch,
            "evals_body": 10000 if epoch == 4 else 100,
            "evals_shadow": 0,
            "evals_meta": 0,
            "evals_foundry": 0,
            "wall_s": 0.001,
            "llm_calls": 0,
            "stall": "ok",
            "lib_size": 1,
            "lib_bits": 1,
            "arm": "rt_sleep",
        }
        directory = root / "epochs" / str(epoch)
        fm.write_json(directory / "status.json", row)
        fm.write_text(
            directory / "curve.csv",
            ",".join(row) + "\n" + ",".join(str(v) for v in row.values()) + "\n",
        )
        fm.write_json(directory / "blocks.json", [{"name": "alpha"}])
        fm.write_jsonl(
            directory / "solutions.jsonl",
            [
                {
                    "task_id": task,
                    "set": "L16",
                    "train_ok": task == "a" and epoch > 0,
                    "test_ok": task == "a" and epoch > 0,
                    "program": ["blk", "alpha"],
                }
                for task in ("a", "b")
            ],
        )
    fm.write_jsonl(
        root / "ledger.jsonl",
        [
            {"epoch": 1, "kind": "incubate"},
            {"epoch": 1, "kind": "promote"},
            {"epoch": 1, "kind": "demote"},
            {"epoch": 1, "kind": "epoch"},
            {"epoch": 2, "kind": "retire"},
        ],
    )
    result = {
        "schema": "think2-quick/1",
        "genome_sha": metadata["genome_sha"],
        "cfg": {**fitness.CFG, "threads": threads},
        "auc_L": 4,
        "cost": 10400,
        "eff": round(4 / 0.0104, 4),
        "wall_s": 0.005,
        "per_task": {
            "a": {"auc": 4, "solved": [1, 1, 1, 1]},
            "b": {"auc": 0, "solved": [0, 0, 0, 0]},
        },
        "guards": {"leak_new": "PASS", "leak_config": "PASS"},
    }
    fm.write_json(root.parent / "quick.json", result)
    return result


@pytest.fixture
def evaluated(sample, monkeypatch):
    calls = []

    def run(root, **kwargs):
        calls.append(root)
        return fake_quick(root, **kwargs)

    monkeypatch.setattr(quick, "run", run)
    path, doc, _, _ = sample
    directory = genome.EVO / "pop/g0/parent"
    genome.write(directory / "tree.json", doc, path.parent / "files")
    fit = fitness.evaluate(
        directory, validate(doc, sample), genome.EVO / "pop/fit_cache.jsonl"
    )
    return directory, fit, calls


def test_activity_conserves_and_uses_event_ownership(sample, evaluated):
    directory, fit, _ = evaluated
    activity = fm.read_json(directory / "quick/credit.json")
    first = activity["activity"]["1"]["activity"]
    assert first["grow"] == 2 and first["judge"] == 3 and first["foundry"] == 1
    assert activity["activity"]["2"]["activity"]["judge"] == 2
    assert activity["conservation"]["pass"] and activity["coverage"]["pass"]
    assert sum(fit["credit_by_subtree"].values()) == pytest.approx(
        0.8 * fit["eff"], abs=1e-4
    )
    assert any(r["amount"] < 0 for r in activity["credit"])
    assert fit["comparison"] == {
        "d_auc_L": 0,
        "sigma": 0,
        "z": None,
        "degenerate": True,
        "significant": False,
    }


def test_cache_clone_never_runs_quick_and_fit_forgery(sample, evaluated):
    directory, original, calls = evaluated
    path, doc, _, _ = sample
    clone = directory.parents[1] / "g1/clone"
    genome.write(clone / "tree.json", doc, path.parent / "files")
    fit = fitness.evaluate(
        clone,
        validate(doc, sample),
        directory.parents[1] / "fit_cache.jsonl",
        parent_dir=directory / "quick",
    )
    assert len(calls) == 1 and fit["cache_hit"] and not fit["quick_ran"]
    assert fit["eff"] == original["eff"] and not fitness.verify_fit(
        clone / "fit.json", doc["genome_sha"]
    )
    assert (
        main(
            [
                "ga-check",
                str(clone / "tree.json"),
                "--parent",
                str(path),
                "--fit",
                str(clone / "fit.json"),
            ]
        )
        == 0
    )
    fit["eff"] += 1
    fm.write_json(clone / "fit.json", fit)
    assert (
        main(
            [
                "ga-check",
                str(clone / "tree.json"),
                "--parent",
                str(path),
                "--fit",
                str(clone / "fit.json"),
            ]
        )
        == 1
    )
    assert any(
        "eff" in e for e in fitness.verify_fit(clone / "fit.json", doc["genome_sha"])
    )


@pytest.mark.parametrize("field", ["eff", "auc", "cfg", "sequence"])
def test_quick_evidence_tampering_is_not_a_cache_hit(sample, evaluated, field):
    directory, fit, _ = evaluated
    measured = fm.read_json(directory / "quick/quick.json")
    if field == "eff":
        measured["eff"] = fit["eff"] = fit["eff"] + 1
    elif field == "auc":
        measured["per_task"]["a"]["auc"] += 1
    elif field == "cfg":
        measured["cfg"]["L"] = 100000
    else:
        measured["per_task"]["a"]["solved"].append(0)
    fm.write_json(directory / "quick/quick.json", measured)
    fm.write_json(directory / "fit.json", fit)
    assert fitness.verify_fit(directory / "fit.json", fit["genome_sha"])
    path, doc, _, _ = sample
    clone = genome.EVO / "pop/g1/forged_cache"
    genome.write(clone / "tree.json", doc, path.parent / "files")
    with pytest.raises(ValueError, match="invalid fit_cache"):
        fitness.evaluate(
            clone, validate(doc, sample), genome.EVO / "pop/fit_cache.jsonl"
        )


def test_generation_cli_and_acceptance_without_search(sample, monkeypatch):
    path, _, root, guide = sample
    monkeypatch.setattr(quick, "run", fake_quick)
    monkeypatch.setattr(
        ledger,
        "_regression",
        lambda: {"pass": True, "pytest_exit": 0, "tests_passed": 1, "errors": []},
    )
    monkeypatch.setattr(ga, "_evo_status", lambda: [])
    before = ledger.snapshot(root)
    out = genome.EVO / "generation"
    assert (
        main(
            [
                "ga",
                "--parent",
                str(path),
                "--pop",
                "8",
                "--gens",
                "1",
                "--out",
                str(out),
                "--seed",
                "0",
                "--ledger",
                str(guide),
            ]
        )
        == 0
    )
    report = fm.read_json(ga.ACCEPT)
    assert report["pass"] and set(report["checks"]) == {f"G{i}" for i in range(1, 8)}
    assert report["checks"]["G3"]["cache_hits"] >= 1
    assert report["checks"]["G7"]["live_files_differ"] == 0
    assert before == ledger.snapshot(root)
    children = sorted((out / "g1").glob("*/parents.json"))
    records = [fm.read_json(p) for p in children]
    assert len(records) == 8
    assert sum(r["arm"] == "cross" for r in records) == 2
    assert sum(r["arm"] == "clone" for r in records) == 1
    assert {r["ops"][0]["op"] for r in records if r["arm"] == "cross"} == {"X1", "X3"}
    select = fm.read_json(out / "g1/select.json")
    assert len(select["selected"]) == 4 and len(select["hall"]) == 5
    assert all(Path(p).is_dir() for p in select["hall"])
    assert all(Path(c["directory"]).is_dir() for c in select["ranked"])
    # A measured live-tree change must turn G7 red.
    candidates = [
        {
            "directory": str(p.parent),
            "genome_sha": fm.read_json(p.parent / "tree.json")["genome_sha"],
        }
        for p in children
    ]
    bad = ga._accept(
        fm.read_json(path),
        candidates,
        before,
        {**before, "injected": "sha"},
        {"pass": True},
        [],
    )
    assert not bad["pass"] and not bad["checks"]["G7"]["pass"]


def test_all_fake_cases_exit_one_and_report_errors(sample):
    assert main(["ga-fake", "--out", str(genome.SCRATCH / "fake")]) == 0
    report = fm.read_json(ga_fake.REPORT)
    assert report["pass"] and report["n_rejected"] == len(ga_fake.CASES) == 8
    assert all(
        c["exit"] == 1 and c["errors"] and c["status"] == "FAIL"
        for c in report["cases"].values()
    )


def test_safety_stop_destination_threads_and_retry_limit(sample, monkeypatch, tmp_path):
    path, doc, _, guide = sample
    for kwargs in ({"pop": 7}, {"gens": 2}, {"threads": 5}):
        with pytest.raises(ValueError):
            ga.run(path, genome.EVO / "bad", guide, **kwargs)
    with pytest.raises(ValueError, match="destination"):
        ga.run(path, tmp_path / "outside", guide)
    monkeypatch.setattr(quick, "run", fake_quick)
    monkeypatch.setattr(mutate, "mutate", lambda *args: (doc, {}))
    with pytest.raises(ValueError, match="exceeded 20 draws"):
        ga.run(path, genome.EVO / "retry", guide)
    failures = fm.read_json(genome.EVO / "retry/generation_failure.json")
    assert len(failures["attempts"]) == 20

    def stopped():
        raise RuntimeError("STOP")

    monkeypatch.setattr(boundary, "check_stop", stopped)
    with pytest.raises(RuntimeError, match="STOP"):
        ga_fake.run(genome.SCRATCH / "stopped")
    assert not (genome.SCRATCH / "stopped").exists()


def test_selection_order_tournaments_and_no_deletion(tmp_path):
    candidates = []
    for index in range(9):
        directory = tmp_path / "candidates" / str(index)
        fm.write_json(directory / "tree.json", {"index": index})
        candidates.append(
            {
                "directory": str(directory),
                "genome_sha": f"{index:012x}",
                "fit": {"eff": index // 3, "auc_L": index % 3},
            }
        )
    a = selection.select(
        candidates, tmp_path / "g1/select.json", tmp_path / "hall", seed=7
    )
    b = selection.select(
        candidates, tmp_path / "g2/select.json", tmp_path / "hall2", seed=7
    )
    assert a["selected"] == b["selected"] and a["tournaments"] == b["tournaments"]
    assert [Path(c["directory"]).name for c in a["elites"]] == ["8", "7"]
    assert len({c["directory"] for c in a["selected"]}) == 4
    assert all(Path(c["directory"]).is_dir() for c in candidates)
