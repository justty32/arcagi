# 交接書必備段

照模板寫；安全邊界、30% 換手、git 衛生、今晚不 push 四段必帶並要求原樣下傳。

模板：`wf/workflows/TEMPLATE.handoff.md`（交接書是唯一契約，沒寫＝沒授權）。必備：

1. **先讀規矩**：可改成「先 read 知識庫 `worker`」＋該工作流入口檔。
2. **唯一目標**一個；驗收條數寫死，寫「就這 N 條」。
3. **安全邊界**（原樣下傳孫 agent）：可寫路徑、不 sudo、不裝套件、專案內不 rm、不讀 `~/.ssh`／金鑰、`~/arcagi-STOP` 存在就停。全文見 `notes/rounds/總表/規矩.md`「安全邊界」。
4. **30% 換手**：context 約 30%（約 60k tokens 或 40 次工具呼叫）就停手寫 `progress.md`（做到哪、數字、下一步、關鍵路徑、在跑的背景單元），回 `PARTIAL`；開完長跑就交棒，見 `handoff_lessons`。
5. **git 衛生**：族群、各代候選、原始大輸出放 gitignore 夾或 scratchpad，只 commit 彙總與沉澱下來的節點。
6. **今晚只 commit 不 push、不 pull**（使用者 11-09 23:4x，覆蓋「可隨意 push」）。
7. **交棒點**：哪個里程碑後換手寫死。
8. 回報開頭 `DONE`／`PARTIAL`／`BLOCKED`／`FAILED`。

出處：當夜看板「子 agent context 管理」「分工」、`notes/rounds/總表/規矩.md`。
