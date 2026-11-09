#!/usr/bin/env bash
# Wait for the N3 comparison benches, then append their tables to report.md.
set -u
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); cd "$ROOT"
while systemctl --user is-active -q arcagi-n3-bench-real.scope || systemctl --user is-active -q arcagi-n3-bench-synth.scope; do sleep 30; done
R=reports/gpu-gp-1109/report.md
{
  echo "## 結果（自動製表 $(date '+%m-%d %H:%M')；指令見下）"
  echo
  echo "real-40＝主線未解題 training／evaluation 各 20（每題 20 秒）；synth-L*＝植入長度 L、深度<4 無解的合成題（每題 15 秒）。'C++ 解出'＝train 一致；真正答對看 Python test 欄。"
  echo
  python3 native/gpu/gp/bench_table.py reports/gpu-gp-1109/bench/real reports/gpu-gp-1109/bench/synth-L5 reports/gpu-gp-1109/bench/synth-L6 reports/gpu-gp-1109/bench/synth-L7
  echo "## 指令"
  echo
  echo '```'
  echo 'make -C native gpugp'
  echo 'native/bin/gpgp --synth reports/gpu-gp-1109/synth/L$L --tasks reports/gpu-gp-1109/synth-sources.txt --synth-len $L --min-depth 4 --seed $L   # L=5,6,7'
  echo 'native/gpu/gp/bench.sh reports/gpu-gp-1109/real-40-paths.txt reports/gpu-gp-1109/bench/real 20'
  echo 'native/gpu/gp/bench.sh reports/gpu-gp-1109/synth/L$L-paths.txt reports/gpu-gp-1109/bench/synth-L$L 15 reports/gpu-gp-1109/synth/L$L'
  echo 'python3 native/gpu/gp/bench_table.py reports/gpu-gp-1109/bench/*'
  echo '```'
  echo
  echo "程式碼 commit：ab66b40（gpgp 原始碼）、a463e69（overnight GP_ARGS）、cfd176a（bench_table）。"
} >"$R.results"
python3 - "$R" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace("<!-- RESULTS -->", open(p + ".results").read())
open(p, "w").write(s)
PY
echo filled >reports/gpu-gp-1109/bench/FILLED
