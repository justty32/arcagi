#!/usr/bin/env bash
# Overnight GPU genetic program search (reports/gpu-gp-1109/report.md).
# Launch wrapped: systemd-run --user --scope --unit=arcagi-n3-gp -p MemoryMax=16G nice -n 19 timeout ...
#   native/gpu/gp/overnight.sh [OUT_DIR] [DEADLINE]   (DEADLINE: `date -d` text)
# Passes over every mainline-unsolved training + evaluation task; pass k uses
# seed k and a growing per-task budget, and only revisits tasks no pass has
# solved yet. Always ends by writing reports/gpu-gp-1109/overnight-summary.md,
# also when interrupted (TERM / INT) or when the deadline is reached.
set -u
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT=${1:-$ROOT/reports/gpu-gp-1109/overnight}
DEADLINE=${2:-"2026-11-10 06:00"}
REPORT=${REPORT:-$ROOT/reports/gpu-gp-1109/overnight-summary.md}
BIN=${BIN:-$ROOT/native/bin/gpgp-overnight}
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
        native/gpu/gp/overnight_summary.py --out-dir "$OUT" --report "$REPORT" \
        --n2-dir "$ROOT/reports/native-cuda-1109/overnight" \
        --note "結束原因：$1；截止 $DEADLINE；日誌 \`$LOG\`" >>"$LOG" 2>&1
}
CHILD=
trap '[ -n "$CHILD" ] && kill "$CHILD" 2>/dev/null; summary "收到中斷訊號"; exit 0' TERM INT HUP
remaining() { echo $(( end_epoch - $(date +%s) )); }

# Mainline-unsolved tasks minus those any finished pass solved.
open_tasks() {
    python3 - "$OUT" "${SOLVED[@]}" "$DATA" <<'PY'
import glob, json, os, sys
out, lists, data = sys.argv[1], sys.argv[2:-1], sys.argv[-1]
solved = set()
for l in lists:
    solved |= {x.strip() for x in open(l) if x.strip()}
for f in glob.glob(os.path.join(out, "pass-*.jsonl")):
    for line in open(f):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("solved"):
            solved.add(r["task"])
for split in ("training", "evaluation"):
    for name in sorted(os.listdir(os.path.join(data, split))):
        if name[:-5] not in solved:
            print(os.path.join(data, split, name))
PY
}

k=1
for budget in 20 60 120 240 240 240 240 240 240 240; do
    rem=$(remaining)
    [ "$rem" -le 60 ] && break
    list=$OUT/open-pass-$k.txt
    open_tasks >"$list"
    echo "$(date -Is) start pass-$k ($(wc -l <"$list") tasks, budget ${budget}s, seed $k, ${rem}s left)" >>"$LOG"
    timeout --signal=TERM "$rem" "$BIN" --tasks "$list" --budget "$budget" --seed "$k" \
        --out "$OUT/pass-$k.jsonl" >>"$OUT/gp-stderr.log" 2>&1 &
    CHILD=$!
    wait "$CHILD"
    echo "$(date -Is) end pass-$k rc=$?" >>"$LOG"
    CHILD=
    k=$((k + 1))
done
if [ "$(remaining)" -le 60 ]; then summary "到截止時間"; else summary "各輪跑完"; fi
