"""Think-4 meters use synthetic solutions only; no hammer search is executed."""

import copy
import math

import pytest

from arcagi.hammer import formats as fm
from arcagi.treegen import dumb, meter, meter_suite, quick
from arcagi.treegen.cli import main
from arcagi.treegen.export import export_tree
from arcagi.treegen.meter_stats import B_REF, sign_test
from arcagi.treegen.refs import expand, genome_sha, sha12


@pytest.fixture
def setup(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    monkeypatch.setattr(quick, "SCRATCH", allowed)
    monkeypatch.setattr(meter, "SCRATCH", allowed)
    monkeypatch.setattr(meter, "RUN_BASE", allowed)
    ids = [f"t{n:02}" for n in range(16)]
    taskset = tmp_path / "taskset.json"
    fm.write_json(
        taskset,
        {"learn": ids, "P48": ["p0", "p1"], "holdout": ["h8"], "holdout24": ["h24"]},
    )
    root = fm.init_root(tmp_path / "source", taskset)
    ops = fm.read_jsonl(root / "ops.jsonl")
    ops.extend(
        fm.new_op(
            f"comb_{n}",
            "comb",
            {"name": f"comb_{n}", "body": ["id"], "holes": 0, "src_tasks": ["t00"]},
            "user",
            0,
            status="live",
        )
        for n in range(2)
    )
    fm.write_ops(root, ops)
    export_tree(root, tmp_path / "parent")
    parent = tmp_path / "parent/tree.json"

    def make_run(label, *, src=parent, ntfs=(100, 50, 25), tasks=None):
        path = allowed / label
        chosen = tasks or ids
        meter.prepare_meter(src, path, chosen, L=2000, epochs=len(ntfs) - 1)
        for e, ntf in enumerate(ntfs):
            fm.write_jsonl(
                path / f"root/epochs/{e}/solutions.jsonl",
                [
                    {
                        "task_id": t,
                        "set": "L16",
                        "train_ok": ntf is not None,
                        "test_ok": ntf is not None and j % 2 == 0,
                        "nodes_to_first": ntf,
                        "program": ["id"],
                    }
                    for j, t in enumerate(chosen)
                ],
            )
        fm.write_json(path / "timing.json", {"wall_s": 1.25})
        fm.write_json(path / "meter.json", meter._report(path))
        return path

    return parent, ids, allowed, make_run


def test_hand_bits_gain_transfer_and_fixed_reference(setup):
    _, _, _, make_run = setup
    run = make_run("hand", ntfs=(None, 25_000, 12_500), tasks=["t00"])
    table = meter.bits_table(run / "root", 2)
    assert table["t00"]["b"] == pytest.approx([0, 1, 2])
    scores = meter.score(table)
    assert scores["base_bits"] == 0
    assert scores["gain_bits"] == scores["transfer_bits"] == pytest.approx(3)
    assert scores["new_solves"] == 1
    assert B_REF == 50_000  # L was only 2000; B_ref remains fixed.
    run2 = make_run("subtract", ntfs=(25_000, 12_500, 6250), tasks=["t00"])
    result = meter.score(meter.bits_table(run2 / "root", 2))
    assert result["base_bits"] == pytest.approx(1)
    assert result["gain_bits"] == pytest.approx(3)  # 2+3 minus 2*e0.
    assert result["transfer_bits"] == result["new_solves"] == 0


def test_train_only_cap_and_legacy_auc(setup):
    _, _, _, make_run = setup
    run = make_run("train", ntfs=(100_000, 1, None), tasks=["t00", "t01"])
    path = run / "root/epochs/1/solutions.jsonl"
    rows = fm.read_jsonl(path)
    rows[0].update(train_ok=False, test_ok=True)
    rows[1].update(train_ok=True, test_ok=False)
    fm.write_jsonl(path, rows)
    table = meter.bits_table(run / "root", 2)
    assert table["t00"]["b"] == [0, 0, 0]
    assert table["t01"]["b"] == [0, math.log2(50_000), 0]
    before = meter.score(table)
    for item in table.values():
        item["test_ok"] = [not x for x in item["test_ok"]]
    after = meter.score(table)
    assert {k: v for k, v in before.items() if k != "auc_L"} == {
        k: v for k, v in after.items() if k != "auc_L"
    }


def stat_doc(differences):
    ids = [f"t{i}" for i in range(len(differences))]
    doc = {
        "cfg": {"B_ref": B_REF},
        "task_ids": ids,
        "per_task": {
            tid: {
                "b": [0, value],
                "train_ok": [False, True],
                "test_ok": [False, True],
                "ntf": [None, 1],
            }
            for tid, value in zip(ids, differences, strict=True)
        },
    }
    return doc


def test_sigma_zero_cases_and_minimum_effect():
    a, b = stat_doc([0] * 4), stat_doc([1] * 4)
    identical = meter.compare(a, a)
    assert identical["sigma"] == 0 and identical["z"] is None
    assert not identical["significant"] and not identical["all_equal"]
    shifted = meter.compare(a, b)
    assert shifted["significant"] and shifted["all_equal"]
    assert shifted["z"] is None and shifted["halves"] == [2, 2]
    assert meter.compare(b, a)["delta"] == -4
    assert not meter.compare(stat_doc([0] * 3), stat_doc([1] * 3))["significant"]
    assert not meter.compare(a, stat_doc([0.1] * 4))["significant"]


def test_sigma_formula_and_half_sign_uses_taskset_order():
    a = stat_doc([0] * 16)
    # Four changes pass the z gate and both halves.
    d = [1, 1, 1, 1] + [0] * 12
    result = meter.compare(a, stat_doc(d))
    assert result["sigma"] == pytest.approx(math.sqrt(3))
    assert result["z"] == pytest.approx(4 / math.sqrt(3))
    assert result["significant"]
    one_half = meter.compare(a, stat_doc([1, 0] * 8))
    assert abs(one_half["z"]) >= 2 and not one_half["significant"]
    assert not one_half["halves_same_sign"]
    opposed = meter.compare(stat_doc([0] * 8), stat_doc([10, -1] * 4))
    assert not opposed["halves_same_sign"]
    b = stat_doc([1, 0] * 8)
    b["task_ids"] = a["task_ids"] = list(reversed(a["task_ids"]))
    assert meter.compare(a, b)["halves"] == [0, 8]
    with pytest.raises(ValueError, match="only"):
        meter.compare(a, b, "auc_L")
    b["cfg"] = {"L": 20}
    with pytest.raises(ValueError, match="cfg"):
        meter.compare(a, b)


def test_prepare_strips_all_preserves_parent_and_refuses_collision(setup):
    parent, ids, allowed, _ = setup
    before = parent.read_bytes()
    path = allowed / "collision"
    meta = meter.prepare_meter(parent, path, [ids[0], "p0"], L=2000, epochs=1)
    assert len(meta["stripped_ops"]) == meta["original_comb_count"] == 2
    assert not any(o["kind"] == "comb" for o in fm.read_jsonl(path / "root/ops.jsonl"))
    assert fm.read_json(path / "root/truth/train/taskset.json") == {
        "L16": [ids[0], "p0"],
        "P": [],
    }
    assert parent.read_bytes() == before
    with pytest.raises(FileExistsError):
        meter.prepare_meter(parent, path, ids)
    (allowed / "empty").mkdir()
    with pytest.raises(FileExistsError):
        meter.prepare_meter(parent, allowed / "empty", ids)
    with pytest.raises(ValueError, match="destination"):
        meter.prepare_meter(parent, allowed.parent / "outside", ids)
    with pytest.raises(ValueError, match="taskset"):
        meter.prepare_meter(parent, allowed / "bad", [ids[0], ids[0]])


@pytest.mark.parametrize(
    "field", ["b", "ntf", "train_ok", "test_ok", "scores", "sha", "gates"]
)
def test_verify_recomputes_and_rejects_tampering(setup, field):
    _, _, _, make_run = setup
    run = make_run(field)
    assert meter.verify(run)["pass"]
    doc = fm.read_json(run / "meter.json")
    if field == "scores":
        doc["scores"]["gain_bits"] += 1
    elif field == "sha":
        doc["genome_sha"] = "fake"
    elif field == "gates":
        doc["gates"]["promotes"] += 1
    else:
        value = doc["per_task"]["t00"][field][0]
        doc["per_task"]["t00"][field][0] = (
            not value if isinstance(value, bool) else value + 1
        )
    fm.write_json(run / "meter.json", doc)
    assert not meter.verify(run)["pass"]


@pytest.mark.parametrize("kind", ["missing", "duplicate", "wrong_set", "invalid_ntf"])
def test_raw_solutions_fail_closed(setup, kind):
    _, _, _, make_run = setup
    run = make_run(kind)
    path = run / "root/epochs/0/solutions.jsonl"
    rows = fm.read_jsonl(path)
    if kind == "missing":
        rows.pop()
    elif kind == "duplicate":
        rows[0] = rows[1]
    elif kind == "wrong_set":
        rows[0]["set"] = "P"
    else:
        rows[0]["nodes_to_first"] = 0
    fm.write_jsonl(path, rows)
    assert not meter.verify(run)["pass"]


def test_select_train_strata_order_and_targeted_fallback():
    report = stat_doc([0] * 26)
    report.update(schema="think4-meter/1", genome_sha="p")
    for j, item in enumerate(report["per_task"].values()):
        if j < 6:  # learned
            item.update(b=[0, 2], train_ok=[False, True], ntf=[None, 12500])
        elif j < 12:  # sped
            item.update(b=[2, 3], train_ok=[True, True], ntf=[12500, 6250])
        elif j < 16:  # edge
            item.update(b=[2, 2], train_ok=[True, True], ntf=[12500, 12500])
        elif j < 24:  # never
            item.update(b=[0, 0], train_ok=[False, False], ntf=[None, None])
        else:
            item.update(b=[10, 10], train_ok=[True, True], ntf=[10, 10])
    selected = meter.select_taskset(report)
    assert selected["learning_tasks"] == 12 and not selected["needs_targeted"]
    assert len(selected["task_ids"]) == 20 and selected["within_target"]
    assert selected["task_ids"][-4:] == sorted(selected["groups"]["never"])[:4]
    assert selected["taskset_sha"] == sha12(selected["task_ids"])
    changed = copy.deepcopy(report)
    for item in changed["per_task"].values():
        item["test_ok"] = [True, True]
    assert meter.select_taskset(changed) == selected
    for item in changed["per_task"].values():
        item.update(b=[0, 0], train_ok=[False, False], ntf=[None, None])
    fallback = meter.select_taskset(changed)
    assert fallback["needs_targeted"] and fallback["diagnosis"] == "剝光後看不到學習"


def test_dumb_recipes_change_hash_and_use_effective_controls(setup):
    parent, _, allowed, _ = setup
    before = parent.read_bytes()
    for recipe in dumb.RECIPES:
        out = allowed / "genomes" / recipe / "tree.json"
        doc = dumb.make(parent, recipe, out)
        assert doc["genome_sha"] == genome_sha(doc["defs"], doc["tree"])
        assert doc["genome_sha"] != fm.read_json(parent)["genome_sha"]
        tree = expand(doc["tree"], doc["defs"])
        if recipe in dumb.RECIPES[:3]:
            assert tree["nodes"]["judge"]["_metainfo.json"]["status"] == "paused"
        if recipe in dumb.RECIPES[:2]:
            assert all(
                tree["nodes"][n]["_metainfo.json"]["status"] == "paused"
                for n in ("grow", "foundry")
            )
        if recipe == "no-decomp":
            assert sum(o["kind"] == "decomp" for o in tree["ops.jsonl"]) == 1
        with pytest.raises(ValueError, match="exists"):
            dumb.make(parent, recipe, out)
    assert parent.read_bytes() == before


def make_suite(setup, labels=meter_suite.T4B_LABELS):
    parent, _, allowed, make_run = setup
    dirs = {name: make_run(name) for name in ("parent-1", "parent-2")}
    for recipe in dumb.RECIPES:
        if recipe not in labels:
            continue
        source = allowed / "genomes" / recipe / "tree.json"
        dumb.make(parent, recipe, source)
        dirs[recipe] = make_run(
            recipe,
            src=source,
            ntfs=(100, 100, 100)
            if recipe in (*dumb.RECIPES[:3], "no-learn-all")
            else (100, 50, 25),
        )
    manifest = allowed / "batch.json"
    fm.write_json(
        manifest, {"runs": [{"label": k, "run_dir": str(v)} for k, v in dirs.items()]}
    )
    return dirs, manifest, allowed


def test_accept_and_three_actual_fake_verifications(setup):
    dirs, manifest, allowed = make_suite(setup)
    before = (dirs["no-learn"] / "meter.json").read_bytes()
    out = allowed / "accept.json"
    result = meter_suite.accept(manifest, out, fake=True)
    assert result["pass"], result["errors"]
    assert set(result["checks"]["fake"]["checks"]) == {
        "per_task",
        "same_sha",
        "test_as_train",
    }
    assert all(r["rejected"] for r in result["checks"]["fake"]["checks"].values())
    same_sha = result["checks"]["fake"]["checks"]["same_sha"]
    assert same_sha["verify"]["pass"] and not same_sha["identity_ok"]
    assert (dirs["no-learn"] / "meter.json").read_bytes() == before
    assert not meter_suite.accept(manifest, out)["pass"]


def test_accept_rejects_same_parent_dumb_and_nonindependent_runs(setup):
    dirs, manifest, allowed = make_suite(setup)
    data = fm.read_json(manifest)
    data["runs"][1]["run_dir"] = str(dirs["parent-1"])
    fm.write_json(manifest, data)
    assert not meter_suite.accept(manifest, allowed / "fail.json", fake=True)["pass"]
    data["runs"][1]["run_dir"] = str(dirs["parent-2"])
    fm.write_json(manifest, data)
    assert not meter_suite._identity(
        fm.read_json(dirs["parent-1"] / "meter.json"),
        fm.read_json(dirs["parent-1"] / "meter.json"),
        "no-learn",
    )


def test_cli_limits_and_accept_exit(setup, capsys):
    _, _, allowed, _ = setup
    with pytest.raises(SystemExit) as exc:
        main(["meter-batch", "x", "--taskset", "x", "--out", "x", "--jobs", "5"])
    assert exc.value.code == 2
    with pytest.raises(ValueError, match="jobs"):
        meter_suite.batch("x", "x", "x", jobs=5)
    dirs, manifest, _ = make_suite(setup)
    assert (
        main(
            [
                "meter-accept",
                str(manifest),
                "--out",
                str(allowed / "accept.json"),
                "--fake",
            ]
        )
        == 0
    )
    broken = fm.read_json(dirs["null"] / "meter.json")
    broken["genome_sha"] = "forged"
    fm.write_json(dirs["null"] / "meter.json", broken)
    assert (
        main(
            [
                "meter-accept",
                str(manifest),
                "--out",
                str(allowed / "accept.json"),
                "--fake",
            ]
        )
        == 1
    )


def test_targeted_stripping_uses_program_references_not_src_tasks(setup):
    parent, ids, allowed, _ = setup
    probe = allowed / "probe"
    fm.write_jsonl(
        probe / "epochs/0/solutions.jsonl",
        [{"task_id": ids[0], "train_ok": True, "program": ["comb_1"]}],
    )
    assert meter._stripped(fm.read_json(parent), [ids[0]], "targeted", probe) == [
        "comb_1"
    ]


def test_leak_protects_quarantined_p_but_allows_selected_p(setup):
    _, _, _, make_run = setup
    run = make_run("selected-p", tasks=["t00", "p0"])
    assert meter.verify(run)["pass"]
    ops = fm.read_jsonl(run / "root/ops.jsonl")
    op = fm.new_op("foreign", "comb", {"body": ["id"], "src_tasks": ["p1"]}, "user", 0)
    fm.write_ops(run / "root", [*ops, op])
    fm.write_json(run / "meter.json", meter._report(run))
    assert not meter.verify(run)["pass"]


@pytest.fixture(autouse=True)
def prohibit_hammer_search(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("meter unit tests must never run hammer search")

    monkeypatch.setattr(meter.epoch, "run_tree", forbidden)


def test_batch_runs_all_seven_jobs_with_at_most_four_workers(setup, monkeypatch):
    import threading
    import time

    parent, ids, allowed, make_run = setup
    taskset = allowed / "selected.json"
    fm.write_json(taskset, {"task_ids": ids})
    active, peak = 0, 0
    lock = threading.Lock()

    def synthetic_worker(job, taskset, cfg, log):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        try:
            time.sleep(0.01)
            path = make_run(job["run_dir"], src=job["tree_json"])
            return {**job, "returncode": 0, "verify": meter.verify(path)}
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(meter_suite, "_worker", synthetic_worker)
    report = meter_suite.batch(
        parent, taskset, allowed / "batch.json", jobs=4, base_dir=allowed
    )
    assert report["pass"] and 1 <= peak <= 4
    assert report["jobs"] == 4 and report["threads"] == 1
    assert {r["label"] for r in report["runs"]} == {
        *meter_suite.T4B_LABELS,
    }
    assert len({r["run_dir"] for r in report["runs"]}) == 7


def test_subprocess_worker_forces_one_thread(setup, monkeypatch):
    import subprocess

    parent, _, allowed, make_run = setup
    run = make_run("worker")
    captured = {}

    class FakeProcess:
        returncode = 0

        def __init__(self, argv, **kwargs):
            captured.update(argv=argv, **kwargs)

        def poll(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", FakeProcess)
    result = meter_suite._worker(
        {"label": "parent", "tree_json": str(parent), "run_dir": str(run)},
        allowed / "taskset.json",
        {"L": 2000, "E": 2, "strip": "all"},
        allowed / "worker.log",
    )
    assert result["verify"]["pass"]
    assert captured["argv"][-2:] == ["--threads", "1"]
    assert all(
        captured["env"][k] == "1"
        for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
    )


@pytest.mark.parametrize("target", ["frozen", "node", "root"])
def test_verify_catches_changed_replica_controls(setup, target):
    _, _, _, make_run = setup
    run = make_run(target)
    if target == "frozen":
        path = run / "root/frozen.json"
        doc = fm.read_json(path)
        doc["budgets"]["shadow_slow"] += 1
    elif target == "node":
        path = run / "root/nodes/judge/_metainfo.json"
        doc = fm.read_json(path)
        doc["status"] = "paused"
    else:
        path = run / "root/_metainfo.json"
        doc = fm.read_json(path)
        doc["meter_freeze_uses"] = True
    fm.write_json(path, doc)
    assert not meter.verify(run)["pass"]


def test_dumb_rejects_noop_even_with_different_storage_representation(setup):
    parent, _, allowed, _ = setup
    first = dumb.make(parent, "no-decomp", allowed / "first/tree.json")
    # Expand refs so re-interning could change the SHA without changing content.
    raw = {**first, "defs": {}, "tree": expand(first["tree"], first["defs"])}
    raw["genome_sha"] = genome_sha(raw["defs"], raw["tree"])
    source = allowed / "first/noncanonical.json"
    fm.write_json(source, raw)
    with pytest.raises(ValueError, match="changed nothing"):
        dumb.make(source, "no-decomp", allowed / "noop/tree.json")


def test_no_learn_all_is_no_learn_plus_hashed_freeze_flag(setup):
    parent, _, allowed, _ = setup
    no_learn = dumb.make(parent, "no-learn", allowed / "nl/tree.json")
    all_off = dumb.make(parent, "no-learn-all", allowed / "nla/tree.json")
    tree = expand(all_off["tree"], all_off["defs"])
    assert tree["_metainfo.json"].pop("meter_freeze_uses") is True
    assert tree == expand(no_learn["tree"], no_learn["defs"])
    assert (
        len(
            {
                fm.read_json(parent)["genome_sha"],
                no_learn["genome_sha"],
                all_off["genome_sha"],
            }
        )
        == 3
    )


@pytest.mark.parametrize("recipe", [None, "no-learn", "no-learn-all"])
def test_run_callback_freezes_only_uses_when_marked(setup, monkeypatch, recipe):
    parent, ids, allowed, _ = setup
    if recipe:
        source = allowed / "control/tree.json"
        dumb.make(parent, recipe, source)
    else:
        source = parent
    directory = allowed / "callback"
    meter.prepare_meter(source, directory, ids, epochs=2)
    frozen = recipe == "no-learn-all"
    seen = []

    def synthetic_epochs(root, tree, *, epochs, threads, holdout, log):
        assert tree == "hammer" and threads == 1 and holdout is False
        state_path = root / "live/state.json"
        for e in range(epochs + 1):
            if e:
                assert fm.read_json(state_path)["uses"] == (
                    {} if frozen else {"reverse": e}
                )
            state = {"uses": {"reverse": e + 1}, "prev": {"epoch": e}, "batch": [e]}
            fm.write_json(state_path, state)
            fm.write_jsonl(
                root / f"epochs/{e}/solutions.jsonl",
                [
                    {
                        "task_id": t,
                        "set": "L16",
                        "train_ok": True,
                        "test_ok": False,
                        "nodes_to_first": 100,
                    }
                    for t in ids
                ],
            )
            log(f"epoch {e}")
            expected = {**state, "uses": {} if frozen else state["uses"]}
            assert fm.read_json(state_path) == expected
            seen.append(e)

    monkeypatch.setattr(meter.epoch, "run_tree", synthetic_epochs)
    result = meter.run(directory)
    assert seen == [0, 1, 2]
    assert result["gates"].get("freeze_uses", False) is frozen
    assert fm.read_json(directory / "meter.json") == result
    assert meter.verify(directory)["pass"]


@pytest.mark.parametrize(
    "d,n,k,n_pos,p,delta,halves,same_sign",
    [
        ([0] * 5, 0, 0, 0, 1, 0, [0, 0], False),
        ([-1] * 5, 5, 5, 0, 1 / 32, -5, [-3, -2], True),
        ([1] * 5, 5, 0, 5, 1, 5, [3, 2], True),
        ([-2, 0, 1, -1, 0], 3, 2, 1, 1 / 2, -2, [-1, -1], True),
        ([-1, 1, -1, 1], 4, 2, 2, 11 / 16, 0, [-2, 2], False),
    ],
)
def test_sign_test_hand_calculation(d, n, k, n_pos, p, delta, halves, same_sign):
    result = sign_test(stat_doc([0] * len(d)), stat_doc(d), "gain_bits")
    assert (result["n"], result["k"], result["n_pos"]) == (n, k, n_pos)
    assert result["p_neg"] == p
    assert result["delta"] == delta and result["halves"] == halves
    assert result["halves_same_sign"] is same_sign


def test_sign_test_base_metric_order_and_validation():
    a, b = stat_doc([0] * 5), stat_doc([-1] * 5)
    for item in b["per_task"].values():
        item["b"] = [-1, -1]
    assert sign_test(a, b, "base_bits")["p_neg"] == 1 / 32
    assert sign_test(a, b)["n"] == 0
    b["task_ids"].reverse()
    with pytest.raises(ValueError, match="ordered tasksets"):
        sign_test(a, b)
    b["task_ids"].reverse()
    b["cfg"]["L"] = 40000
    with pytest.raises(ValueError, match="cfg"):
        sign_test(a, b)
    with pytest.raises(ValueError, match="only"):
        sign_test(a, a, "auc_L")


def test_batch_subset_creates_only_requested_controls(setup, monkeypatch):
    parent, ids, allowed, make_run = setup
    taskset = allowed / "selected.json"
    fm.write_json(taskset, {"task_ids": ids})

    def synthetic_worker(job, taskset, cfg, log):
        path = make_run(job["run_dir"], src=job["tree_json"])
        return {**job, "returncode": 0, "verify": meter.verify(path)}

    monkeypatch.setattr(meter_suite, "_worker", synthetic_worker)
    result = meter_suite.batch(
        parent,
        taskset,
        allowed / "subset.json",
        base_dir=allowed,
        labels=meter_suite.T4C_LABELS,
    )
    assert result["pass"]
    assert [r["label"] for r in result["runs"]] == list(meter_suite.T4C_LABELS)
    suite = next(allowed.glob("suite_*"))
    assert {p.name for p in (suite / "genomes").iterdir()} == {
        "no-learn-all",
        "no-learn",
        "null",
    }


@pytest.mark.parametrize("labels", [[], ["null", "null"], ["unknown"], [""]])
def test_batch_rejects_invalid_labels_before_writing(setup, labels):
    _, _, allowed, _ = setup
    with pytest.raises(ValueError, match="labels"):
        meter_suite.batch("missing", "missing", allowed / "batch.json", labels=labels)
    assert not (allowed / "batch.json").exists()


def test_t4c_accept_with_actual_fake_verifications(setup):
    _, manifest, allowed = make_suite(setup, meter_suite.T4C_LABELS)
    result = meter_suite.accept(
        manifest, allowed / "accept.json", criterion="t4c", fake=True
    )
    assert result["pass"], result["errors"]
    assert result["checks"]["control_clean"]
    assert result["sign_tests"]["no-learn-all"]["p_neg"] == 1 / 2**16
    assert all(r["rejected"] for r in result["checks"]["fake"]["checks"].values())


@pytest.fixture
def t4c_reports(setup, monkeypatch):
    _, _, allowed, _ = setup
    docs, directories = {}, {}
    for label in meter_suite.T4C_LABELS:
        doc = stat_doc([0 if label == "no-learn-all" else 1] * 16)
        doc.update(
            schema="think4-meter/1",
            genome_sha="parent" if label.startswith("parent-") else label,
            gates={"promotes": 0, "new_ops": 0},
        )
        if not label.startswith("parent-"):
            doc["dumb"] = {"parent_sha": "parent", "recipe": label}
        if label == "no-learn-all":
            doc["gates"]["freeze_uses"] = True
        docs[label], directories[label] = doc, allowed / label
    manifest = allowed / "batch.json"
    fm.write_json(
        manifest,
        {"runs": [{"label": k, "run_dir": str(p)} for k, p in directories.items()]},
    )
    monkeypatch.setattr(meter_suite.meter, "verify", lambda p: {"pass": True})
    monkeypatch.setattr(meter_suite, "fake_checks", lambda *args: {"pass": True})

    def accept():
        for label, doc in docs.items():
            doc["scores"] = meter.score(doc["per_task"])
            fm.write_json(directories[label] / "meter.json", doc)
        return meter_suite.accept(
            manifest, allowed / "accept.json", fake=True, criterion="t4c"
        )

    return docs, accept


def set_gains(doc, values):
    for item, value in zip(doc["per_task"].values(), values, strict=True):
        item["b"] = [0, value]


def test_t4c_reports_old_control_without_using_its_score_as_gate(t4c_reports):
    docs, accept = t4c_reports
    set_gains(docs["no-learn"], [50] * 16)
    result = accept()
    assert result["pass"], result["errors"]
    old = result["report_only"]["no-learn"]
    assert old["sign_test"]["delta"] == 49 * 16
    assert old["compare"]["gain_bits"]["significant"]
    ordering = result["report_only"]["no-learn-all_vs_no-learn"]["sign_test"]
    assert ordering["delta"] == -50 * 16


@pytest.mark.parametrize("gains", [[100] + [1] * 15, [0.125] * 16])
def test_t4c_learning_uses_sign_test_and_includes_minimum_effect(t4c_reports, gains):
    docs, accept = t4c_reports
    for label in ("parent-1", "parent-2", "null"):
        set_gains(docs[label], gains)
    result = accept()
    assert result["pass"], result["errors"]
    if gains[0] == 100:
        assert not result["comparisons"]["no-learn-all"]["gain_bits"]["significant"]
    else:
        assert result["sign_tests"]["no-learn-all"]["delta"] == -2


@pytest.mark.parametrize(
    "case",
    [
        "control_clean",
        "p_value",
        "effect",
        "halves",
        "repeat",
        "null_sign",
        "null_z",
        "identity",
        "freeze_uses",
    ],
)
def test_t4c_accept_rejects_failed_gates(t4c_reports, case):
    docs, accept = t4c_reports
    expected_gate = case
    if case == "control_clean":
        set_gains(docs["no-learn-all"], [1 / 16] * 16)
    elif case in ("p_value", "effect", "halves"):
        values = {
            "p_value": [1] * 4 + [0] * 12,
            "effect": [0.1] * 16,
            "halves": [1, 0] * 8,
        }[case]
        for label in ("parent-1", "parent-2", "null"):
            set_gains(docs[label], values)
        expected_gate = "learning_drop"
    elif case == "repeat":
        docs["parent-2"]["per_task"]["t0"]["b"][0] = 0.5
    elif case == "null_sign":
        set_gains(docs["null"], [0.999] * 5 + [1] * 11)
        expected_gate = "null"
    elif case == "null_z":
        set_gains(docs["null"], [11, 11, 0, 0] * 4)
        expected_gate = "null"
    elif case == "identity":
        docs["no-learn-all"]["genome_sha"] = "parent"
    else:
        docs["no-learn-all"]["gates"]["freeze_uses"] = False
        expected_gate = "recipes"
    result = accept()
    assert not result["pass"]
    check = result["checks"][expected_gate]
    if case == "identity":
        assert not all(check.values())
    elif expected_gate == "recipes":
        assert check["no-learn-all"]["inert"]
    else:
        assert not check
    if case == "control_clean":
        assert any("對照不乾淨" in error for error in result["errors"])
    if case == "null_sign":
        assert not result["comparisons"]["null"]["gain_bits"]["significant"]
    if case == "null_z":
        assert result["sign_tests"]["null"]["p_neg"] > 0.05


def test_t4c_null_zero_delta_exception(t4c_reports):
    docs, accept = t4c_reports
    set_gains(docs["null"], [0] * 10 + [11] + [1] * 5)
    result = accept()
    assert result["pass"], result["errors"]
    assert result["sign_tests"]["null"]["delta"] == 0
    assert result["sign_tests"]["null"]["p_neg"] <= 0.05


def test_t4c_keeps_verify_and_fake_gates(t4c_reports, monkeypatch):
    _, accept = t4c_reports
    monkeypatch.setattr(meter_suite.meter, "verify", lambda p: {"pass": False})
    assert not accept()["pass"]
    monkeypatch.setattr(meter_suite.meter, "verify", lambda p: {"pass": True})
    monkeypatch.setattr(meter_suite, "fake_checks", lambda *args: {"pass": False})
    assert not accept()["pass"]


@pytest.mark.parametrize("case", ["missing", "extra", "shared_directory"])
def test_t4c_requires_five_independent_runs(t4c_reports, setup, case):
    _, accept = t4c_reports
    _, _, allowed, _ = setup
    path = allowed / "batch.json"
    manifest = fm.read_json(path)
    if case == "missing":
        manifest["runs"].pop()
    elif case == "extra":
        manifest["runs"].append({"label": "gate-dormant", "run_dir": str(allowed)})
    else:
        manifest["runs"][1]["run_dir"] = manifest["runs"][0]["run_dir"]
    fm.write_json(path, manifest)
    result = accept()
    assert not result["pass"]
    assert any("5 independent run directories" in error for error in result["errors"])


def test_cli_passes_labels_and_criterion(setup, monkeypatch):
    parent, _, allowed, _ = setup
    captured = {}

    def batch(*args, **kwargs):
        captured.update(kwargs)
        return {"pass": True}

    def accept(*args, **kwargs):
        captured.update(kwargs)
        return {"pass": True}

    monkeypatch.setattr(meter_suite, "batch", batch)
    monkeypatch.setattr(meter_suite, "accept", accept)
    assert (
        main(
            [
                "meter-batch",
                str(parent),
                "--taskset",
                "x",
                "--out",
                "x",
                "--labels",
                "parent-1,no-learn-all,null",
            ]
        )
        == 0
    )
    assert captured["labels"] == ["parent-1", "no-learn-all", "null"]
    assert main(["meter-accept", "x", "--out", "x", "--criterion", "t4c"]) == 0
    assert captured["criterion"] == "t4c"
    assert main(["meter-accept", "x", "--out", "x"]) == 0
    assert captured["criterion"] == "t4b"
    assert (
        main(
            [
                "dumb",
                str(parent),
                "--recipe",
                "no-learn-all",
                "--out",
                str(allowed / "cli/tree.json"),
            ]
        )
        == 0
    )
