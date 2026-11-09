#!/usr/bin/env bash
# GP vs exhaustive at the same per-task GPU time budget (reports/gpu-gp-1109/report.md).
#   native/gpu/gp/bench.sh LIST OUT_DIR BUDGET_SEC [DATA_DIR_FOR_VERIFY]
# Runs, one after another on the same task list: gpgp (GP), gpgp --random
# (same sampler without selection) and gpusearch dedup-4 depth <= 8
# --stop-first (N2 exhaustive). Then re-verifies every program with Python.
set -u
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
LIST=$1 OUT=$2 B=$3 VDATA=${4:-}
mkdir -p "$OUT"; cd "$ROOT"
[ -f ~/arcagi-STOP ] && exit 1
native/bin/gpgp --tasks "$LIST" --budget "$B" --seed 1 --out "$OUT/gp.jsonl" 2>"$OUT/gp.err"
native/bin/gpgp --tasks "$LIST" --budget "$B" --seed 1 --random --out "$OUT/random.jsonl" 2>"$OUT/random.err"
native/bin/gpusearch --tasks "$LIST" --mode gpu --dedup 4 --prefix-cap 3000000 --depth 8 --stop-first \
    --budget "$B" --out "$OUT/exhaustive.jsonl" 2>"$OUT/exhaustive.err"
V=(); [ -n "$VDATA" ] && V=(--data "$VDATA")
for m in gp random exhaustive; do
    PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR="$ROOT/native/.uv-cache" uv run --no-sync python \
        native/tools/gpu_verify.py "$OUT/$m.jsonl" "${V[@]}" >"$OUT/$m-verify.jsonl" 2>&1
done
echo done >"$OUT/DONE"
