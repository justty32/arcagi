# 回報格式與換手

最後一則訊息開頭寫終局狀態，一句結論，逐條列驗收；30% context 就寫 progress.md 換手。

- 終局狀態：`DONE`／`PARTIAL`／`BLOCKED`／`NEEDS-USER`／`FAILED`。
- 接一句自足結論，再逐條列驗收結果與交付路徑（絕對路徑）。
- 只給結論＋路徑，不貼原始輸出；讀大檔用 grep／head 或派孫 agent。
- 卡住 >10 分鐘先回 `BLOCKED`，不無聲等待。
- 30% 換手：約 60k tokens 或 40 次工具呼叫 → 停手寫 `<產物夾>/progress.md`（做到哪、數字、下一步、關鍵路徑、在跑的背景單元），commit 已完成部分，回 `PARTIAL`。
- 跨資料夾回報走 inbox：`wf/tools/inbox_send.sh <上游 inbox> <線名> <STATUS> '<結論>' [正文檔]`。

出處：`wf/workflows/TEMPLATE.handoff.md`「完成／阻塞回報」、當夜看板「子 agent context 管理」。
