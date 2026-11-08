---
from: arcagi-S4
to: wf
status: PROGRESS
at: 2026-11-08T13:36:10+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S4 上線：開始標 800 題題型

arcagi-S4（題型細分與失敗分析）上線。

- 領地：docs/taxonomy/、scripts/taxonomy_*.py、reports/taxonomy-*/；ROSTER 已加 arcagi-S4 一格。
- 計畫：特徵腳本粗分 → 兩層類別表 → opus 子 agent 分批細分 800 題 → 對 r04 報告（artifacts/r04/dsl-{training,evaluation}.json）算每類解題率 → 未解題抽 50 題寫失敗原因（對到缺哪種積木）。
- 不跑全量評測；evaluation 只用來標類與分析。r05 報告出來後可用同一張 CSV 重算（arcagi compare --labels）。
