#!/bin/sh
# Usage: snapshot.sh SNAPDIR -- copy every replay-compatible GPU output into SNAPDIR (read-only on sources),
# dropping a truncated last line if a writer is mid-line. Synth (-L5/6/7), *-verify, profile files are skipped.
set -e
S=$1; cd "$(dirname "$0")/../../.."; mkdir -p "$S"; date -Is > "$S/SNAPSHOT_TIME"
cp reports/native-cuda-1109/overnight/phase-A.jsonl "$S/nc-phase-A.jsonl"
cp reports/native-cuda-1109/overnight/phase-B.jsonl "$S/nc-phase-B.jsonl"
cp reports/native-cuda-1109/filler/train-open-d6.jsonl "$S/nc-filler-train-d6.jsonl"
cp reports/native-cuda-1109/filler/eval-open-d6.jsonl "$S/nc-filler-eval-d6.jsonl"
cp reports/gpu-gp-1109/overnight/pass-1.jsonl "$S/gp-pass-1.jsonl"
for f in on40-orig on40-ho on40-mdl real-ho real-mdl; do cp reports/gpu-gp-1109/ho/$f.jsonl "$S/gp-ho-$f.jsonl"; done
for f in reports/gpu-gp-1109/ho/sweep/*.jsonl; do case "$f" in *-verify.jsonl) continue;; esac; cp "$f" "$S/gp-sweep-$(basename "$f")"; done
for f in gp random exhaustive; do cp reports/gpu-gp-1109/bench/real/$f.jsonl "$S/gp-bench-real-$f.jsonl"; done
python3 - "$S" <<'PY'
import json, glob, sys
for f in glob.glob(sys.argv[1] + "/*.jsonl"):
    good = []
    for line in open(f):
        try:
            good.append(json.loads(line))
        except ValueError:
            pass
    open(f, "w").write("".join(json.dumps(r) + "\n" for r in good))
PY
