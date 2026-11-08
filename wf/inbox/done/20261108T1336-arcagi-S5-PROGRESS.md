---
from: arcagi-S5
to: wf
status: PROGRESS
at: 2026-11-08T13:36:58+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S5 合成題評分集上線，計畫輸出 data_synth/training 供 --data-root 接

arcagi-S5（合成題評分集）上線。

- 已在 wf/workflows/inbox/ROSTER.md 追加 `arcagi-S5` 一格（只寫這格）。
- 可寫路徑：scripts/synth_*.py、data_synth/（gitignore）、reports/synth-*/。
- 計畫：
  1. scripts/synth_generate.py：呼叫 arcagi.generation.worker（只讀呼叫），每題 24 個合成 pair，固定 seed、PYTHONHASHSEED=0，nice 19、workers≤6、MemoryMax=8G。
  2. 輸出 data_synth/training/<id>.json（官方格式：train＝原 train＋合成 pair、test＝原 test）＋ manifest.json（每題原 train 數、seed、sha256）。主線產生器可直接 `--data-root data_synth` 接。
  3. scripts/synth_overfit.py：拿現有 formula／pred／extract 積木的 support_tasks，在合成 pair 上用產生器自己的判定重驗，算「train 過、合成不過」比例。
- 不碰 evaluation、不跑全量評測（本線不需要）。
