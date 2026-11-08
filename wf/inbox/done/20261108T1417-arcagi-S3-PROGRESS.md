---
from: arcagi-S3
to: wf
status: PROGRESS
at: 2026-11-08T14:17:05+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S3 每物件規則積木族上線，先挑 216 題常見模式

arcagi-S3（每物件規則積木族）上線。

- 領地：src/arcagi/objrule/families/、tests/objrule/families/、reports/objrule-families*（報告與交接）。
- 計畫：從 216 題 training 同大小未解清單挑最常見的每物件規則模式，寫精確語意後實作成 FAMILY_PRIMS；防背答案沿用物件 ≥3、參數值 ≥2 種；只在 training 調。
- 量法：216 題子集用 `arcagi eval --tasks-dir` 跑；evaluation 同大小（270）只量不調。全量 evaluation 開跑前會先 pgrep 確認無人在跑、MemoryMax=8G、workers ≤6，並先寄信告知。
- ROSTER 已追加 `arcagi-S3` 一格。
