#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 || ( $1 != 1000000 && $1 != 10000000 ) ]]; then
    echo "usage: $0 {1000000|10000000} OUTDIR" >&2
    exit 2
fi
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
[[ ! -e "$HOME/arcagi-STOP" ]] || { echo 'Stopped: ~/arcagi-STOP exists' >&2; exit 130; }
if [[ ${ARC_N8B_PROF_SCOPE:-0} != 1 ]]; then
    exec systemd-run --user --scope --unit="arcagi-n8b-prof-$$" -p MemoryMax=16G \
        nice -n 19 env ARC_N8B_PROF_SCOPE=1 bash "$ROOT/reports/cpu-hot-1110/n8b_prof.sh" "$@"
fi
OUTDIR=$(realpath -m -- "$2")
case "$OUTDIR/" in "$ROOT/"*) echo 'Raw outputs must be outside the repo' >&2; exit 2;; esac
mkdir -p -- "$OUTDIR"
[[ ! -e "$OUTDIR/profile.txt" && ! -e "$OUTDIR/DONE" ]] || { echo 'Use a fresh OUTDIR' >&2; exit 2; }
cd -- "$ROOT"
unset ARC_HOT_STATS
export ARC_HOT_PROF="$OUTDIR/profile.txt"
python3 reports/cpu-hot-1110/run_one.py "$1" arcbatch-hot-prof 1 "$OUTDIR"
[[ ! -e "$HOME/arcagi-STOP" ]] || exit 130
cat -- "$OUTDIR/profile.txt"
touch -- "$OUTDIR/DONE"
