#!/usr/bin/env bash
# gpgp-ho measurement (reports/gpu-gp-1109/holdout.md).
#   reports/gpu-gp-1109/ho/run.sh CONFIG   CONFIG = ho (holdout+mdl+min) | mdl (mdl+min, no holdout)
# real-40 at default pop (matches bench/real/gp.jsonl), on40 at pop 524288 (matches overnight pass-1).
set -u
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); cd "$ROOT"
H=reports/gpu-gp-1109/ho C=$1
case $C in
  ho)  F=(--holdout loo --mdl 0.003 --simplify min) ;;
  mdl) F=(--mdl 0.003 --simplify min) ;;
  *) exit 2 ;;
esac
for set in real on40; do
  [ -f ~/arcagi-STOP ] && exit 1
  if [ $set = real ]; then L=reports/gpu-gp-1109/real-40-paths.txt P=(); else L=$H/on40-paths.txt P=(--pop 524288); fi
  native/bin/gpgp-ho --tasks "$L" --budget 20 --seed 1 "${P[@]}" "${F[@]}" --out "$H/$set-$C.jsonl" 2>"$H/$set-$C.err"
  PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR="$ROOT/native/.uv-cache" uv run --no-sync python \
      native/tools/gpu_verify.py "$H/$set-$C.jsonl" >"$H/$set-$C-verify.jsonl" 2>&1
done
echo done >"$H/DONE-$C"
