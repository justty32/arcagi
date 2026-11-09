#!/usr/bin/env bash
# Overnight GPU brute-force run (reports/native-cuda-1109/prototype.md).
# Launch wrapped: systemd-run --user --scope --unit=arcagi-n2-<name> -p MemoryMax=16G nice -n 19 ...
#   native/gpu/overnight.sh [OUT_DIR] [DEADLINE]   (DEADLINE: `date -d` text)
# Phase A: every training + evaluation task, depth <= 5 (dedup 3).
# Phase B: tasks without a train solution in A and unsolved by the mainline,
#          depth <= 6 (dedup 4). Phase C: same tasks, depth 7, until deadline.
# Always ends by writing reports/native-cuda-1109/overnight-summary.md, also
# when interrupted (TERM / INT) or when a phase hits the deadline.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:-$ROOT/reports/native-cuda-1109/overnight}
DEADLINE=${2:-"2026-11-10 06:00"}
REPORT=${REPORT:-$ROOT/reports/native-cuda-1109/overnight-summary.md}
BIN=${BIN:-$ROOT/native/bin/gpusearch}
DATA=$ROOT/data/ARC-AGI/data
SOLVED=("$ROOT/reports/native-cuda-1109/mainline-solved-training-gated-r07.txt"
        "$ROOT/reports/native-cuda-1109/mainline-solved-evaluation-gated-r08.txt")
end_epoch=$(date -d "$DEADLINE" +%s)
mkdir -p "$OUT"
LOG=$OUT/run.log
cd "$ROOT"

summarised=0
summary() {
    [ "$summarised" = 1 ] && return
    summarised=1
    echo "$(date -Is) summary ($1)" >>"$LOG"
    PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR="$ROOT/native/.uv-cache" timeout 300 uv run --no-sync python \
        native/tools/gpu_overnight_summary.py --out-dir "$OUT" --report "$REPORT" \
        --solved "${SOLVED[0]}" --solved "${SOLVED[1]}" \
        --note "結束原因：$1；截止 $DEADLINE；日誌 \`$LOG\`" >>"$LOG" 2>&1
}
CHILD=
trap '[ -n "$CHILD" ] && kill "$CHILD" 2>/dev/null; summary "收到中斷訊號"; exit 0' TERM INT HUP

remaining() { echo $(( end_epoch - $(date +%s) )); }
phase() {  # name list args...
    local name=$1 list=$2; shift 2
    local rem; rem=$(remaining)
    if [ "$rem" -le 30 ]; then echo "$(date -Is) skip $name (deadline)" >>"$LOG"; return 1; fi
    echo "$(date -Is) start $name ($(wc -l <"$list") tasks, ${rem}s left): $*" >>"$LOG"
    timeout --signal=TERM "$rem" "$BIN" --tasks "$list" --mode gpu --stop-first --samples 5 "$@" \
        --out "$OUT/$name.jsonl" >>"$LOG" 2>&1 &
    CHILD=$!
    wait "$CHILD"
    local rc=$?
    CHILD=
    echo "$(date -Is) end $name rc=$rc" >>"$LOG"
    [ "$rc" = 0 ]
}
# Tasks with no train solution in the given phase files, minus mainline-solved.
open_tasks() {
    python3 - "$@" 2>>"$LOG" <<'EOF'
import json, sys
files, lists = sys.argv[1:-2], sys.argv[-2:]
solved = set()
for l in lists:
    solved |= {x.strip() for x in open(l) if x.strip()}
seen, out = set(), []
for f in files:
    for line in open(f):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "gpu" not in r or r["task"] in seen:
            continue
        seen.add(r["task"])
        if "best" not in r and r["task"] not in solved:
            out.append(r["task"])
for t in out:
    print(t)
EOF
}

ALL=$OUT/all.txt
{ ls "$DATA/training"/*.json; ls "$DATA/evaluation"/*.json; } >"$ALL"
phase phase-A "$ALL" --depth 5 --dedup 3 --budget 120 || true

OPEN=$OUT/open-after-A.txt
open_tasks "$OUT/phase-A.jsonl" "${SOLVED[@]}" | while read -r t; do
    if [ -f "$DATA/training/$t.json" ]; then echo "$DATA/training/$t.json"; else echo "$DATA/evaluation/$t.json"; fi
done >"$OPEN"
phase phase-B "$OPEN" --depth 6 --dedup 4 --prefix-cap 3000000 --budget 600 || true

OPEN2=$OUT/open-after-B.txt
open_tasks "$OUT/phase-B.jsonl" "${SOLVED[@]}" | while read -r t; do
    if [ -f "$DATA/training/$t.json" ]; then echo "$DATA/training/$t.json"; else echo "$DATA/evaluation/$t.json"; fi
done >"$OPEN2"
phase phase-C "$OPEN2" --depth 7 --dedup 4 --prefix-cap 3000000 --budget 900 || true

if [ "$(remaining)" -le 30 ]; then summary "到截止時間"; else summary "三階段跑完"; fi
