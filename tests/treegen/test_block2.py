"""Block-2 statistics, provenance, registration and isolated quick replicas."""

import hashlib
import os

import pytest

from arcagi.hammer import formats as fm
from arcagi.hammer.check import check_root
from arcagi.treegen import boundary, guards, noise, quick
from arcagi.treegen.cli import main
from arcagi.treegen.export import export_tree


@pytest.fixture
def tree(tmp_path):
    taskset = tmp_path / "taskset.json"
    fm.write_json(
        taskset,
        {
            "learn": ["a", "b", "c"],
            "holdout": ["h8"],
            "holdout24": ["h24"],
            "P48": ["p"],
        },
    )
    root = fm.init_root(tmp_path / "source", taskset)
    return root


@pytest.fixture
def replica(tmp_path, monkeypatch, tree):
    allowed = tmp_path / "allowed"
    monkeypatch.setattr(quick, "SCRATCH", allowed)
    monkeypatch.setattr(guards, "LIVE_ROOT", tree)
    # leak's default root was bound at import time; wrap only that default.
    original = guards.leak
    monkeypatch.setattr(
        guards, "leak", lambda target, **kw: original(target, forbid_root=tree, **kw)
    )
    return allowed / "trial" / "run"


def write_quick(path, solved, cost=100):
    tasks = {
        tid: {"solved": values, "auc": sum(values), "nodes_to_first": []}
        for tid, values in solved.items()
    }
    fm.write_json(
        path / "quick.json",
        {
            "schema": "think2-quick/1",
            "auc_L": sum(row["auc"] for row in tasks.values()),
            "cost": cost,
            "per_task": tasks,
        },
    )
    return path


def test_bootstrap_identical_and_single_task(tmp_path):
    a = write_quick(tmp_path / "a", {"a": [0, 1], "b": [1, 1], "c": [0, 0]})
    b = write_quick(tmp_path / "b", {"a": [0, 1], "b": [1, 1], "c": [0, 0]})
    c = write_quick(tmp_path / "c", {"a": [1, 1], "b": [1, 1], "c": [0, 0]})
    identical = noise.noise([a, b])
    assert identical["sigma_auc_L"] == 0
    assert identical["degenerate"] and identical["deterministic"]
    assert noise.compare(a, b)["z"] is None
    changed = noise.noise([a, b, c])
    assert not changed["deterministic"] and not changed["degenerate"]
    assert changed["sigma_auc_L"] > 0 and changed["sigma_run_auc_L"] > 0
    assert changed["per_task_mismatch"] == 1
    assert changed["determinism_delta"] == {"auc_L": 1, "cost": 0}
    assert changed == noise.noise([a, b, c])
    comparison = noise.compare(a, c)
    assert comparison["delta_auc_L"] == comparison["mean_delta_auc_L"] == 1
    assert comparison["n_tasks_differ"] == 1 and comparison["sigma_auc_L"] > 0
    assert noise.compare(c, a)["delta_auc_L"] == -1


def test_noise_sees_sequences_cost_and_missing_tasks(tmp_path):
    a = write_quick(tmp_path / "a", {"a": [0, 1], "b": [0, 0]})
    b = write_quick(tmp_path / "b", {"a": [1, 0], "b": [0, 0]}, cost=101)
    result = noise.noise([a, b])
    assert result["per_task_mismatch"] == 1 and not result["deterministic"]
    assert result["sigma_auc_L"] == 0 and result["degenerate"]
    assert result["determinism_delta"] == {"auc_L": 0, "cost": 1}
    c = write_quick(tmp_path / "c", {"a": [0, 1]})
    assert noise.compare(a, c)["n_tasks_differ"] == 1
    with pytest.raises(ValueError, match="at least two"):
        noise.noise([a])
    with pytest.raises(ValueError, match="n_boot"):
        noise.noise([a, b], n_boot=0)


def test_noise_cli_exit_and_compare_output(tmp_path, capsys):
    a = write_quick(tmp_path / "a", {"a": [0], "b": [0]})
    b = write_quick(tmp_path / "b", {"a": [1], "b": [0]})
    out = tmp_path / "noise.json"
    assert main(["noise", str(a), str(a), "--out", str(out)]) == 0
    assert main(["noise", str(a), str(b), "--out", str(out)]) == 1
    assert not fm.read_json(out)["deterministic"]
    assert main(["compare", str(a), str(b), "--out", str(out)]) == 0
    assert fm.read_json(out)["n_tasks_differ"] == 1


def test_leak_config_pools_and_base_ops(tree, tmp_path):
    old = fm.new_op(
        "old", "comb", {"body": [], "src_tasks": ["p", "h8", "a"]}, "user", 0
    )
    old["evidence"]["new_solves"] = ["h24"]
    fm.write_ops(tree, [old])
    result = guards.leak(tree, forbid_root=tree, base_ops={"old"})
    assert result["status"] == result["config"] == "FAIL"
    assert "epoch.py:252" in result["config_reason"]
    assert len(result["violations"]) == 3
    assert {v["pool"] for v in result["violations"]} == {"P", "H8", "H24"}
    assert result["tainted_ops"] == ["old"]
    assert result["inherited"] == result["violations"] and result["new"] == []
    assert result["leak_new"] == "PASS"
    base = tmp_path / "base.jsonl"
    fm.write_jsonl(base, [old])
    new = fm.new_op("new", "comb", {"body": [], "src_tasks": ["p"]}, "user", 1)
    fm.write_ops(tree, [old, new])
    assert guards.leak(tree, forbid_root=tree, base_ops=base)["leak_new"] == "FAIL"


def test_leak_uses_external_pool_and_genome_sidecar(tree, tmp_path):
    exported = tmp_path / "genome"
    op = fm.new_op("evidence", "comb", {"body": []}, "user", 0)
    op["evidence"]["new_solves"] = ["p"]
    fm.write_ops(tree, [op])
    export_tree(tree, exported)
    result = guards.leak(exported / "tree.json", forbid_root=tree)
    assert result["violations"][0]["field"] == "evidence.new_solves"
    assert (
        main(
            [
                "guard-leak",
                str(exported / "tree.json"),
                "--state",
                str(exported / "state.json"),
                "--forbid-root",
                str(tree),
            ]
        )
        == 1
    )
    other = tmp_path / "other"
    fm.write_json(other / "truth/train/taskset.json", {"P": []})
    fm.write_json(other / "truth/cal/ids.json", {"H8": [], "H24": []})
    fm.write_ops(other, [op])
    assert guards.leak(other, forbid_root=tree)["leak_new"] == "FAIL"
    fm.write_ops(other, [])
    assert guards.leak(other, forbid_root=tree)["status"] == "PASS"
    assert main(["guard-leak", str(other), "--forbid-root", str(tree)]) == 0


def test_threshold_registration_line_keys_and_purposes(tmp_path):
    scan = tmp_path / "src"
    file = scan / "fake.py"
    file.parent.mkdir()
    text = "if pixel_acc > 0.9: promote(op)"
    file.write_text(text + "\n")
    registry = tmp_path / "registry.json"
    assert guards.thresholds([scan], registry)["status"] == "FAIL"
    draft = guards.thresholds([scan], registry, init=True)
    assert draft["invalid"] and draft["status"] == "FAIL"
    document = fm.read_json(registry)
    entry = document["entries"][0]
    relative = os.path.relpath(file, guards.REPO)
    assert entry["key"] == hashlib.sha1(f"{relative}\n{text}".encode()).hexdigest()[:12]
    entry.update(purpose="rank", why="Test registration; not a semantic classifier.")
    fm.write_json(registry, document)
    assert guards.thresholds([scan], registry)["status"] == "PASS"
    file.write_text("# move line\n" + text + "\n")
    assert guards.thresholds([scan], registry)["status"] == "PASS"
    file.write_text(text + "\nnear_score = 0\n")
    assert len(guards.thresholds([scan], registry)["unregistered"]) == 1
    file.write_text(text + "\n")
    for purpose in ("accept", "promote", "retire", "unknown"):
        entry["purpose"] = purpose
        fm.write_json(registry, document)
        assert guards.thresholds([scan], registry)["status"] == "FAIL"
    # Removed source lines are warnings even if their old use was forbidden.
    entry["purpose"] = "promote"
    fm.write_json(registry, document)
    file.write_text("# removed\n")
    result = guards.thresholds([scan], registry)
    assert result["stale"] and result["status"] == "PASS"


def test_threshold_cli_and_extra_scan_root(tmp_path):
    scan = tmp_path / "src"
    scan.mkdir()
    (scan / "one.py").write_text("near_best = 1\n")
    registry = tmp_path / "registry.json"
    args = ["guard-thr", "--scan", str(scan), "--registry", str(registry)]
    assert main([*args, "--init"]) == 1
    document = fm.read_json(registry)
    document["entries"][0].update(purpose="diag", why="Diagnostic only.")
    fm.write_json(registry, document)
    assert main(args) == 0
    extra = tmp_path / "extra"
    extra.mkdir()
    (extra / "two.py").write_text("if pixel_acc > 0.9: promote(op)\n")
    assert (
        main(
            ["guard-thr", "--scan", str(scan), str(extra), "--registry", str(registry)]
        )
        == 1
    )


def test_legacy_cli_export_import_diff_roundtrip(tree, tmp_path):
    exported = tmp_path / "legacy-export"
    assert main(["export", str(tree), "--out", str(exported)]) == 0
    imported = tmp_path / "legacy-import"
    assert (
        main(
            [
                "import",
                str(exported / "tree.json"),
                "--dest",
                str(imported),
                "--state",
                str(exported / "state.json"),
            ]
        )
        == 0
    )
    assert main(["diff", str(exported / "tree.json"), str(exported / "tree.json")]) == 0
    accept = tmp_path / "roundtrip.json"
    assert (
        main(
            [
                "roundtrip",
                str(tree),
                "--out",
                str(tmp_path / "roundtrip"),
                "--accept",
                str(accept),
            ]
        )
        == 0
    )
    assert fm.read_json(accept)["pass"]


def test_prepare_genome_and_state_root_copy(tree, replica, tmp_path):
    op = fm.new_op("comb", "comb", {"body": []}, "user", 0)
    op["ttl"] = 1
    fm.write_ops(tree, [op])
    for runtime in (
        "live/state.json",
        "epochs/9/status.json",
        "tmp/x.json",
        "foundry/x.json",
        "think1/x.json",
    ):
        fm.write_json(tree / runtime, {"runtime": True})
    (tree / "RUN").touch()
    exported = tmp_path / "genome"
    genome = export_tree(tree, exported)
    metadata = quick.prepare(exported / "tree.json", replica, L=2000, epochs=1)
    assert metadata["check_root_errors"] == 0
    assert not metadata["state"]
    assert fm.read_json(replica / "frozen.json")["budgets"]["L"] == 2000
    assert fm.read_json(replica / "frozen.json")["budgets"]["epochs"] == 1
    assert metadata["cfg"]["genome_budgets"] == fm.load_frozen(tree)["budgets"]
    assert fm.read_json(replica.parent / "quarantine_P.json") == ["p"]
    assert fm.read_json(replica / "truth/train/taskset.json")["P"] == []
    assert (replica / "ledger.jsonl").read_bytes() == b""
    assert fm.load_ops(replica)[0]["ttl"] == fm.TTL
    assert fm.load_ops(tree)[0]["ttl"] == 1
    assert fm.read_json(tree / "truth/train/taskset.json")["P"] == ["p"]
    kept = replica.parent / "kept"
    saved = quick.prepare(
        exported / "tree.json", kept, state=exported / "state.json", L=2000, epochs=1
    )
    assert saved["state"] and fm.load_ops(kept)[0]["ttl"] == 1
    copied = replica.parent / "copied"
    raw = quick.prepare(tree, copied, L=2000, epochs=1, clear_p=False)
    assert raw["genome_sha"] == genome["genome_sha"]
    assert (copied / "ops.jsonl").read_bytes() == (tree / "ops.jsonl").read_bytes()
    assert raw["state"] and not raw["cfg"]["clear_p"]
    assert fm.read_json(copied / "truth/train/taskset.json")["P"] == ["p"]
    assert check_root(copied) == []
    for name in ("epochs", "live", "tmp", "think1", "foundry", "RUN"):
        assert not (copied / name).exists()


def test_prepare_refuses_unsafe_and_nonempty_destinations(tree, replica, tmp_path):
    with pytest.raises(ValueError, match="destination"):
        quick.prepare(tree, tmp_path / "elsewhere", L=2000, epochs=1)
    replica.mkdir(parents=True)
    (replica / "keep").write_text("keep")
    with pytest.raises(ValueError, match="empty"):
        quick.prepare(tree, replica, L=2000, epochs=1)
    assert (replica / "keep").read_text() == "keep"
    link = replica.parent / "link"
    link.symlink_to(tree, target_is_directory=True)
    with pytest.raises(ValueError, match="destination"):
        quick.prepare(tree, link, L=2000, epochs=1)
    with pytest.raises(ValueError, match="positive"):
        quick.prepare(tree, replica.parent / "bad", L=0, epochs=1)


def fake_epochs(root, tree_name, *, epochs, backend, threads, holdout, log):
    assert tree_name == "hammer" and backend == "native" and holdout
    assert threads <= 4
    (root / "RUN").touch()
    for n in range(epochs + 1):
        ed = root / "epochs" / str(n)
        row = {
            "epoch": n,
            "solved_L": 1 if n else 3,
            "solved_P": 0,
            "solved_H8": 0,
            "solved_H24": 0,
            "logcost_L": 10 - n,
            "evals_body": 100,
            "evals_shadow": 0,
            "evals_meta": 0,
            "evals_foundry": 0,
            "wall_s": 0,
            "stall": "ok",
            "llm_calls": 0,
            "lib_size": 0,
            "lib_bits": 0,
            "arm": "rt_sleep",
        }
        fm.write_json(ed / "status.json", row)
        fm.write_text(
            ed / "curve.csv",
            ",".join(row) + "\n" + ",".join(str(v) for v in row.values()) + "\n",
        )
        fm.write_jsonl(
            ed / "solutions.jsonl",
            [
                {
                    "task_id": t,
                    "set": "L16",
                    "test_ok": t == "a" or n == 0,
                    "nodes_to_first": 1 if t == "a" else None,
                }
                for t in ("a", "b", "c")
            ],
        )
        log(f"epoch {n}")


def test_quick_run_aggregation_and_cli(tree, replica, monkeypatch):
    monkeypatch.setattr(quick.epoch, "run_tree", fake_epochs)
    args = [
        "quick",
        "--from-root",
        str(tree),
        "--dest",
        str(replica),
        "--L",
        "2000",
        "--epochs",
        "2",
    ]
    assert main(args) == 0
    result = fm.read_json(replica.parent / "quick.json")
    assert result["auc_L"] == sum(t["auc"] for t in result["per_task"].values()) == 2
    assert result["per_task"]["a"]["solved"] == [1, 1]
    assert result["per_task"]["b"]["nodes_to_first"] == [None, None]
    assert len(result["per_epoch"]) == 3 and result["solved_L_final"] == 1
    assert result["guards"] == {"leak_config": "PASS", "leak_new": "PASS"}
    with pytest.raises(ValueError, match="threads"):
        quick.run(replica, epochs=2, threads=5)
    assert main([*args, "--threads", "5"]) == 1


def test_quick_asserts_auc_and_tracks_new_ops(tree, replica, monkeypatch):
    quick.prepare(tree, replica, L=2000, epochs=1)

    def run_with_new(*args, **kwargs):
        fake_epochs(*args, **kwargs)
        fm.append_ops(
            replica,
            [fm.new_op("new", "comb", {"body": [], "src_tasks": ["p"]}, "user", 1)],
        )

    monkeypatch.setattr(quick.epoch, "run_tree", run_with_new)
    result = quick.run(replica, epochs=1)
    assert result["new_ops"] == ["new"] and result["guards"]["leak_new"] == "FAIL"
    original = quick._summarize
    monkeypatch.setattr(
        quick, "_summarize", lambda root: {**original(root), "auc_L": 99}
    )
    monkeypatch.setattr(quick.epoch, "run_tree", fake_epochs)
    with pytest.raises(AssertionError):
        quick.run(replica, epochs=1)


@pytest.mark.parametrize("when", ["before", "epoch"])
def test_stop_removes_only_replica_run(tree, replica, monkeypatch, tmp_path, when):
    quick.prepare(tree, replica, L=2000, epochs=1)
    (tree / "RUN").touch()
    (replica / "RUN").touch()
    stopped = when == "before"

    def check():
        if stopped:
            raise RuntimeError("STOP")

    def stop_at_epoch(root, *args, **kwargs):
        nonlocal stopped
        stopped = True
        kwargs["log"]("epoch 0")
        pytest.fail("STOP did not stop the next epoch")

    monkeypatch.setattr(boundary, "check_stop", check)
    monkeypatch.setattr(quick.epoch, "run_tree", stop_at_epoch)
    with pytest.raises(RuntimeError, match="STOP"):
        quick.run(replica, epochs=1)
    assert not (replica / "RUN").exists() and (tree / "RUN").exists()
