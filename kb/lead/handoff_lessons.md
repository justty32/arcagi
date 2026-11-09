# 換手教訓（11-09 夜跑）

子 agent 常在「等背景工作」時 context 已過線；交接書要寫「開完長跑就寫 progress 交棒」，門檻用工具呼叫數估。

- 現象：11-09 夜多條子 agent 線 context 衝到 110k～130k 才換手（規定約 60k）。多半卡在開完長跑後輪詢、讀輸出等結果。
- 交接書寫死：**開完長跑（systemd 背景單元）就寫 `progress.md` 交棒、回 `PARTIAL`，不在 context 裡等**。progress 寫單元名、輸出路徑、怎麼判斷跑完、下一步。
- 收結果另開新 agent：只帶 `progress.md` 與產物路徑，不帶對話。
- 門檻用**工具呼叫數 ≤40** 估，比 token 好數；到 30 次就開始收尾。
- 讀大檔、長輸出用 grep／head 或派孫 agent，只帶結論回來。
- 11-10 補：即使寫死，T4b／T4c 仍在 ~60k 時「等 codex 跑完」而續到 93k～106k。真正會等的是 codex 實作（不是 systemd 長跑）。對策：隊長收到「waiting on background work」且 tokens >60k 時，立刻 SendMessage 叫它寫 progress 交棒；隊長自己用 `until [ -e <DONE> ] || ! systemctl --user is-active -q <unit>; do sleep 30; done` 背景等，跑完再派新 agent 判讀。
- 長跑要能被隊長等：progress 必寫 DONE 檔路徑與 unit 名；判讀指令寫成一行 python 能直接貼。

出處：當夜看板 `notes/rounds/gpu-night-1109/README.md`「子 agent context 管理」節與 W1 線列；換手必備段見 `handoff`。
