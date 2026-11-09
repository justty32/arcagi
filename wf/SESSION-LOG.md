# SESSION-LOG — 進度（只列 open）

[INDEX](INDEX.md)｜等使用者的另記 [WAIT_USER](WAIT_USER.md)

**寫入時機**：
1. **開始**多步驟工作前先寫一行 open（不是做完才寫）；硬中斷時本檔才有「進行中」。
2. **每次 commit 後**更新或刪除該行。
3. 條目格式：`- [工作流] 一句 open 狀態 → 下一步 / 連結`；完成即刪，歷史交給 git log，決策落到 [workflows/decisions.md](workflows/decisions.md)。

> 膨脹就拆：過大就開 `session_logs/` 按工作流拆檔＋index（照 [STRUCTURE](STRUCTURE.md)）。

## 最新進度

- [inbox/dispatch] 主 agent 依 aos 轉達的 REQUEST（wf/inbox 頂層 1121/1122/1123/1124/1125/1127/1130）做準備＋照 aos 輪次試解；**交棒總表** → [notes/rounds/README.md](../notes/rounds/README.md)
- [rounds] r09 停手、主 session 11-08 19:5x 關閉；v4 方向題五題全 A（19:44）→ 使用者說開工才動：先插 v4 M1～M7 收 r09，再開 r10；接手照 [交棒總表](../notes/rounds/README.md)「主 session 交接」

- [rounds/gpu-night-1109] 夜跑到 11-10 06:20（使用者起床前不停）；授權與安全邊界見 [總表/規矩](../notes/rounds/總表/規矩.md)「11-09 夜跑授權」。在跑：N1 蠟模（opus）、N2 CUDA（opus），長跑到 06:10；看門狗 `arcagi-watchdog`（sonnet 寫，log 在 notes/rounds/gpu-night-1109/watchdog.log）；已寄 aos REQUEST 問思考輪派隊流程（等 DONE 回信）→ 收信後開第一輪思考設計輪（gpt sol 蒐集 → opus 匯總 → fable 設計＋agy Argon 審 → opus 細化 → gpt sol 實作），之後每 1～2 小時一輪；06:04 排程寫晨報＋寄 aos DONE。compact 後：重開 inbox 監看、CronCreate 06:04 若已失效要重排。

## 各工作流 session-log

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

