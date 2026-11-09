#!/bin/bash
# R1 probe runs: bash reports/r1-probe-1110/run.sh OUTDIR  (make -C native r1 first)
# training first 100 (m0 train100.txt), seed, decomp on, 4 threads; base = bin/arcbatch,
# id = bin/arcbatch-r1 with no costs (must equal base), r1 = bin/arcbatch-r1 with costs.txt.
R=/home/lorkhan/repo/arcagi; O=$1; mkdir -p $O; cd $R
T=reports/m0-baseline-1110/train100.txt
run() {  # name budget bin [costs]
  [ -e ~/arcagi-STOP ] && exit 1
  echo "{\"name\":\"base\",\"budget\":$2,\"decomp\":true}" > $O/cfg-$2.jsonl
  local t0=$(date +%s.%N)
  ARC_R1_COSTS=$4 $3 --mode seed --tasks $T --configs $O/cfg-$2.jsonl --threads 4 --out $O/$1-$2.jsonl 2> $O/$1-$2.err
  echo "$1 $2 $(echo "$(date +%s.%N) - $t0" | bc)" >> $O/wall.txt
}
run id 1000000 native/bin/arcbatch-r1
for B in 1000000 10000000; do
  run base $B native/bin/arcbatch
  run r1 $B native/bin/arcbatch-r1 $R/reports/r1-probe-1110/costs.txt
done
echo done > $O/DONE
