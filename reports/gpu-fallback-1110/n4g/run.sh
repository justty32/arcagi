#!/bin/sh
# Usage: run.sh SNAPDIR OUTDIR  -- runs (i) phase-A only and (ii) all sources, both splits, sequentially.
set -e
SNAP=$1; OUT=$2; cd "$(dirname "$0")/../../.."
mkdir -p "$OUT"
A="$SNAP/nc-phase-A.jsonl"
ALL="$A:$(ls "$SNAP"/*.jsonl | grep -v nc-phase-A | tr '\n' ':')"
for cfg in A ALL; do
  eval "SRC=\$$cfg"
  for split in training evaluation; do
    [ -e "$HOME/arcagi-STOP" ] && { echo STOP; exit 1; }
    N4G_SOURCES="$SRC" uv run --no-sync python reports/gpu-fallback-1110/n4g/replay_sources.py \
      --split $split --workers 4 --out "$OUT/$cfg-$split.jsonl" > "$OUT/$cfg-$split.out.txt" 2>&1
  done
done
echo done > "$OUT/DONE"
