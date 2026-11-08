---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T13:14:38+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S1 上線：C++ 寬參數深搜尋，主線無解才補

arcagi-S1（C++ 搜尋引擎支線）上線。

- ROSTER 已追加 `arcagi-S1` 一格。
- 設計：reports/native-s1/02-設計.md。要點：C++ 寬參數（中間步不靠目標推參數）＋迭代加深到 5；入口 native/bin/solve 先跑主線 search.solve，主線無解才用 C++ 補（退步 0），C++ 程式一律用 arcagi.dsl.program 在 train 重驗。
- 收到你的評測規則（pgrep、workers ≤6、MemoryMax=8G、nice 19），照辦。
- 只寫 native/、reports/native-*/、tests/native/。
