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

- [rounds/gpu-night-1109] 夜跑已收尾（11-10 06:1x）：N1／N2／N3 長跑 06:00 寫完彙總、filler 06:06 結束、N4g 06:00 重放做完；**晨報定稿** [notes/rounds/gpu-night-1109/晨報.md](../notes/rounds/gpu-night-1109/晨報.md)（待你裁 5 題、待 push 清單 163 commit 無大檔）；只本機 commit 沒 push → 等使用者起床裁題、決定 push；aos daemon 與 watchdog 仍在跑。看板 [README](../notes/rounds/gpu-night-1109/README.md)。

## 各工作流 session-log

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

