#!/usr/bin/env bash
# N9b sweep: gated mainline on the 188 budget-abstain training tasks, varying ARCAGI_HYBRID_DEADLINE.
# usage: n9b_sweep.sh OUTDIR TASKSDIR ; configs "deadline:harness_timeout:gated_timeout(empty=default)"
set -u
OUT=$1; TASKS=$2; cd /home/lorkhan/repo/arcagi; mkdir -p "$OUT"
CUTOFF=$(date -d 'today 05:38' +%s)
for cfg in 19:45: 40:65: 55:80: 120:150:130; do
  IFS=: read D HT GT <<<"$cfg"
  [ -e ~/arcagi-STOP ] && { echo "STOP file" >>"$OUT/sweep.log"; break; }
  now=$(date +%s); est=$(( 188 * D * 115 / 100 / 6 + 120 ))
  if (( now + est > CUTOFF )); then echo "skip d$D: est ${est}s exceeds cutoff" >>"$OUT/sweep.log"; continue; fi
  ENVS="ARCAGI_HYBRID_DEADLINE=$D"; [ -n "$GT" ] && ENVS="$ENVS ARCAGI_GATED_TIMEOUT=$GT"
  [ "$D" = 19 ] && ENVS=""   # baseline: env unset = default behaviour
  echo "$(date -Is) start d$D envs=[$ENVS]" >>"$OUT/sweep.log"
  t0=$(date +%s)
  timeout $(( CUTOFF - now )) env $ENVS .venv/bin/arcagi eval --tasks-dir "$TASKS" --name "n9b-d$D" \
    --external '.venv/bin/python -m arcagi.solvers.gated {input} {output} {trace}' \
    --timeout "$HT" --workers 6 --artifacts "$OUT/d$D-runs" \
    --output "$OUT/d$D.json" --traces "$OUT/d$D-traces.jsonl" >"$OUT/d$D.log" 2>&1
  echo "$(date -Is) end d$D rc=$? wall=$(( $(date +%s) - t0 ))s" >>"$OUT/sweep.log"
done
touch "$OUT/DONE"
