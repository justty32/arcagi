# SESSION-LOG — 進度（只列 open）

[INDEX](INDEX.md)｜等使用者的另記 [WAIT_USER](WAIT_USER.md)

**寫入時機**：
1. **開始**多步驟工作前先寫一行 open（不是做完才寫）；硬中斷時本檔才有「進行中」。
2. **每次 commit 後**更新或刪除該行。
3. 條目格式：`- [工作流] 一句 open 狀態 → 下一步 / 連結`；完成即刪，歷史交給 git log，決策落到 [workflows/decisions.md](workflows/decisions.md)。

> 膨脹就拆：過大就開 `session_logs/` 按工作流拆檔＋index（照 [STRUCTURE](STRUCTURE.md)）。

## 最新進度

- [inbox/dispatch] 主 agent 依 aos 轉達的 REQUEST（wf/inbox 頂層 1121/1122/1123/1124/1125/1127/1130）做準備＋照 aos 輪次試解；**交棒總表** → [notes/rounds/README.md](../notes/rounds/README.md)
- [rounds] r08 已收（commit c80c6ac；練習池 32 題主樹 AUC_L 32 無增量、foot32 學到 8 積木但 L16 降、gated eval 56/400）；r09 開輪（18:33 錘子設計圖 v3 定稿，使用者「都按照推薦吧」），已派 r09 隊長 → notes/rounds/r09/ → notes/rounds/README.md

## 各工作流 session-log

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

