#!/bin/sh
# Overnight wax casting (wax-night-1109). Usage:
#   run-overnight.sh <run-name> <model> <method> <workers>
# Runs until 06:00 (soft deadline; hard `timeout` at 06:07), then writes
# reports/wax-night-1109/overnight-summary.md from every overnight/*/calls.jsonl.
set -u
# ~/arcagi-STOP also stops the loop (checked before every call).
cd "$(dirname "$0")/../.." || exit 1
NAME=$1 MODEL=$2 METHOD=$3 WORKERS=$4
ROOT=reports/wax-night-1109/overnight
export WAX_SCRATCH=${WAX_SCRATCH:-/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n1}
END=$(date -d 'tomorrow 06:07' +%s)
[ "$(date +%H)" -lt 6 ] && END=$(date -d 'today 06:07' +%s)
SECS=$((END - $(date +%s)))
echo "start $(date) name=$NAME model=$MODEL method=$METHOD workers=$WORKERS hard_limit=${SECS}s"
timeout --signal=TERM --kill-after=120 "$SECS" \
  systemd-run --user --scope -q --unit="arcagi-n1-on-$NAME" -p MemoryMax=16G nice -n 19 \
  .venv/bin/python -m arcagi.llm.wax overnight --model "$MODEL" --method "$METHOD" \
    --until 06:00 --out-dir "$ROOT/$NAME" --workers "$WORKERS" --threads 3 --name "on-$NAME"
echo "loop exit $? at $(date)"
# Fallback: rebuild the summary even if the loop was killed hard.
systemd-run --user --scope -q --unit="arcagi-n1-sum-$NAME" -p MemoryMax=16G nice -n 19 \
  .venv/bin/python -m arcagi.llm.wax summary-overnight "$ROOT"
echo "summary written $(date)"
