"""Usage: ARCAGI_SYNTH=$PWD/data_synth uv run --no-sync python reports/gpu-fallback-1110/headcheck.py 400 <dir>
(<dir>/gated_head.py = `git show 15b2aa0:src/arcagi/solvers/gated.py`; ARCAGI_SYNTH must be set because the
copy outside src/ resolves ROOT wrongly.) Off-mode bit-identity: run HEAD gated.main and new gated.main (env unset) on N stored traces, compare output+trace bytes."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
ROOT = Path("/home/lorkhan/repo/arcagi")
S = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent  # dir with pre-change gated_head.py
os.environ.pop("ARCAGI_GPU_FALLBACK", None)
from arcagi.solvers import gated as new
spec = importlib.util.spec_from_file_location("arcagi.solvers.gated_head", S / "gated_head.py",
                                              submodule_search_locations=None)
old = importlib.util.module_from_spec(spec); old.__package__ = "arcagi.solvers"; spec.loader.exec_module(old)
DATA = ROOT / "data/ARC-AGI/data"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
diff = same = 0
for split, f in (("training", "artifacts/gated-r07/training-traces.jsonl"), ("evaluation", "artifacts/gated-r08/evaluation-traces.jsonl")):
    for line in (ROOT / f).read_text().splitlines()[:n]:
        rec = json.loads(line); tid = rec["task_id"]
        task = json.loads((DATA / split / f"{tid}.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp); req = t / "req.json"; req.write_text(json.dumps({"task_id": tid, "task": task}))
            def runner(_r, out, tr, trace=rec["trace"]):
                if trace: Path(tr).write_text(json.dumps(trace))
            outs = []
            for m in (old, new):
                o, tr = t / f"o{m.__name__}", t / f"t{m.__name__}"
                m.main([str(req), str(o), str(tr)], runner=runner)
                outs.append((o.read_bytes(), tr.read_bytes() if tr.exists() else b""))
            if outs[0] == outs[1]: same += 1
            else: diff += 1; print("DIFF", split, tid)
print(f"same={same} diff={diff}")
