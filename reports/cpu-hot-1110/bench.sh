#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 ]]; then
    echo "usage: $0 OUTDIR" >&2
    exit 2
fi
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
[[ ! -e "$HOME/arcagi-STOP" ]] || { echo 'Stopped: ~/arcagi-STOP exists' >&2; exit 130; }
if [[ ${ARC_N8_BENCH_SCOPE:-0} != 1 ]]; then
    exec systemd-run --user --scope --unit="arcagi-n8-bench-$$" -p MemoryMax=16G \
        nice -n 19 env ARC_N8_BENCH_SCOPE=1 bash "$ROOT/reports/cpu-hot-1110/bench.sh" "$1"
fi
OUTDIR=$(realpath -m -- "$1")
mkdir -p -- "$OUTDIR"
if [[ -e "$OUTDIR/wall.txt" || -e "$OUTDIR/DONE" ]]; then
    echo "Use a fresh OUTDIR: $OUTDIR" >&2
    exit 2
fi
cd -- "$ROOT"
unset ARC_HOT_STATS
for B in 1000000 10000000; do
    for rep in 1 2 3; do
        for bin in arcbatch arcbatch-hot-a arcbatch-hot; do
            [[ ! -e "$HOME/arcagi-STOP" ]] || exit 130
            python3 reports/cpu-hot-1110/run_one.py "$B" "$bin" "$rep" "$OUTDIR"
        done
    done
    for rep in 1 2 3; do
        for bin in arcbatch-hot-a arcbatch-hot; do
            [[ ! -e "$HOME/arcagi-STOP" ]] || exit 130
            rc=0
            python3 reports/cpu-hot-1110/cmp.py "$OUTDIR/$B-arcbatch-r1.jsonl" \
                "$OUTDIR/$B-$bin-r$rep.jsonl" >> "$OUTDIR/cmp.txt" || rc=$?
            [[ $rc -le 1 ]] || exit "$rc"
        done
    done
done
[[ ! -e "$HOME/arcagi-STOP" ]] || exit 130
touch -- "$OUTDIR/DONE"
