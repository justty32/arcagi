# 開場讀序

compact 後依序讀 SESSION-LOG、當夜看板、規矩，再收 inbox。

1. `grep -c '^- \[' wf/SESSION-LOG.md wf/WAIT_USER.md`；非 0 才開該檔。
2. `wf/tools/inbox_read.sh`；有信先讀（`wf/inbox/` 頂層）。
3. 當夜看板：SESSION-LOG 會指；11-09 夜是 `notes/rounds/gpu-night-1109/README.md`（標題「compact 後先讀這裡」）。
4. 授權與安全邊界：`notes/rounds/總表/規矩.md`「11-09 夜跑授權」。
5. 使用者偏好：`wf/workflows/common/user.md`；aos 補充習慣 `wf/workflows/common/user-aos習慣速查.md`。
6. 冷啟動（沒有當夜看板）：`notes/rounds/README.md`（交棒總表）。

出處：`AGENTS.md`「開場與入口」、`wf/workflows/team-model.md`「context 管理」。
