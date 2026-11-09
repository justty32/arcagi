#!/bin/bash
# M0 rerun: bash reports/m0-baseline-1110/run.sh OUTDIR  (builds with `make -C native m0prof` first)
# training first 100 (sorted filenames), decomp on, 4 threads, budgets 1e6 and 1e7, one run each.
R=/home/lorkhan/repo/arcagi; O=${1:-$R/reports/m0-baseline-1110/raw}; mkdir -p $O
cp $R/reports/m0-baseline-1110/train100.txt $O/train100.txt
for B in 1000000 10000000; do
  [ -e ~/arcagi-STOP ] && exit 1
  echo "{\"name\":\"base\",\"budget\":$B,\"decomp\":true}" > $O/cfg-$B.jsonl
  (cd $R && native/bin/m0prof --mode seed --tasks $O/train100.txt --configs $O/cfg-$B.jsonl --threads 4 --out $O/m0-$B.jsonl) 2> $O/m0-$B.err
done
