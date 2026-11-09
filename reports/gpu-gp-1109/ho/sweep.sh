#!/usr/bin/env bash
# n3e: gpgp-ho MDL lambda sweep (reports/gpu-gp-1109/holdout.md "下一步" 1+4).
#   reports/gpu-gp-1109/ho/sweep.sh [OUTDIR]     env: SETS="real on40" LAMS="0 0.003 0.006 0.01" SEEDS="1 2 3" LIMIT=N (smoke)
# Every run: --mdl L --simplify min, no holdout, --budget 20; real-40 default pop, on40 --pop 524288 (as run.sh).
# Order seed > lambda > set, so a TERM cut leaves whole seeds. On exit (normal or TERM) verifies every
# finished jsonl with native/tools/gpu_verify.py and writes OUTDIR/../sweep-summary.md (last line SWEEPDONE).
set -u
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); cd "$ROOT"
H=reports/gpu-gp-1109/ho; O=${1:-$H/sweep}; mkdir -p "$O"
SETS=${SETS:-"real on40"} LAMS=${LAMS:-"0 0.003 0.006 0.01"} SEEDS=${SEEDS:-"1 2 3"} LIMIT=${LIMIT:-0}
SUM=${SUM:-$H/sweep-summary.md}
PID=
finish() {
  trap '' TERM INT
  [ -n "$PID" ] && kill "$PID" 2>/dev/null && wait "$PID" 2>/dev/null
  echo "$(date '+%F %T') finish ($1)" >>"$O/sweep.log"
  for f in "$O"/*.jsonl; do
    case $f in *-verify.jsonl) continue ;; esac
    [ -f "${f%.jsonl}-verify.jsonl" ] && continue
    PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR="$ROOT/native/.uv-cache" timeout 600 uv run --no-sync python \
      native/tools/gpu_verify.py "$f" >"${f%.jsonl}-verify.jsonl" 2>&1
  done
  python3 "$H/sweep_summarize.py" "$O" "$1" >"$SUM" 2>>"$O/sweep.log"
  echo SWEEPDONE >>"$SUM"
  exit 0
}
trap 'finish TERM' TERM INT
for seed in $SEEDS; do for lam in $LAMS; do for set in $SETS; do
  [ -f ~/arcagi-STOP ] && finish STOP
  if [ $set = real ]; then L=reports/gpu-gp-1109/real-40-paths.txt P=(); else L=$H/on40-paths.txt P=(--pop 524288); fi
  if [ "$LIMIT" -gt 0 ]; then head -n "$LIMIT" "$L" >"$O/$set-paths.txt"; L=$O/$set-paths.txt; fi
  B=$O/$set-l$lam-s$seed
  [ -f "$B.done" ] && continue
  echo "$(date '+%F %T') start $set lam=$lam seed=$seed" >>"$O/sweep.log"
  native/bin/gpgp-ho --tasks "$L" --budget 20 --seed "$seed" "${P[@]}" --mdl "$lam" --simplify min \
      --out "$B.jsonl" 2>"$B.err" &
  PID=$!; wait "$PID"; rc=$?; PID=
  echo "$(date '+%F %T') end $set lam=$lam seed=$seed rc=$rc" >>"$O/sweep.log"
  [ $rc -eq 0 ] && touch "$B.done"
done; done; done
finish complete
