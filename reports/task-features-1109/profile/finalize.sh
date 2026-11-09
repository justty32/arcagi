#!/bin/sh
# Waits for both N4 profile scopes, then rebuilds features.csv (no commit).
cd /home/lorkhan/repo/arcagi
while systemctl --user is-active -q arcagi-n4-prof-training.scope || systemctl --user is-active -q arcagi-n4-prof-evaluation.scope; do sleep 60; done
python3 native/tools/profile_features.py reports/task-features-1109/profile/training-d5.jsonl reports/task-features-1109/profile/evaluation-d5.jsonl \
  --out reports/task-features-1109/features.csv --solved reports/native-cuda-1109/mainline-solved-*.txt
touch reports/task-features-1109/profile/FINALIZED
