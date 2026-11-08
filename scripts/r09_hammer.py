"""r09 hammer trees -> reports/curve-r09/<tree>/ (or a scratch --root).

  dec-g1         r08 dec-g1 through hammer.body (M0: curve_sha 7aebb3c73f28)
  hammer         main tree: ops engine on, halves/nest incubating
  hammer-frozen  ops engine frozen, no halves/nest (no learning)
  hammer-static  ops engine frozen, halves/nest live from epoch 0

    nice -n 19 systemd-run --user --scope -q -p MemoryMax=16G \
        uv run python scripts/r09_hammer.py --tree dec-g1
"""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from arcagi.grow import curve as gc
from arcagi.hammer import epoch

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "curve-r09"
TREES = ["dec-g1", "hammer", "hammer-frozen", "hammer-static"]
SCRATCH = Path(tempfile.gettempdir()) / "hammer-scratch"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, choices=TREES)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--backend", default="native", choices=["native", "python"])
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--taskset", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.threads > 8:
        sys.exit("threads <= 8")
    t0 = time.perf_counter()
    if a.tree == "dec-g1":
        out = a.out or REPORTS / "dec-g1"
        root = a.root or SCRATCH / "dec-g1"
        rows = epoch.run_compat(out, root, a.backend, threads=a.threads)
        print(json.dumps({"tree": "dec-g1", "backend": a.backend,
                          "AUC_L": gc.auc_l(rows),
                          "curve_sha": gc.curve_sha(out / "curve.csv")[:12],
                          "wall_s": round(time.perf_counter() - t0, 1)}))
        return
    root = a.root or SCRATCH / a.tree
    rows = epoch.run_tree(root, a.tree, a.epochs, taskset=a.taskset,
                          backend=a.backend, threads=a.threads)
    out = a.out or REPORTS / a.tree
    epoch.export(root, out)
    print(json.dumps({"tree": a.tree, "root": str(root),
                      "AUC_L": sum(r["solved_L"] for r in rows if r["epoch"] >= 1),
                      "wall_s": round(time.perf_counter() - t0, 1)}))


if __name__ == "__main__":
    main()
