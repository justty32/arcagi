# arcagi 知識庫（kb）

arcagi 的分層入口：compact 後讀 resume、派工讀 lead、施工讀 worker、想懂專案讀 project。

arcagi＝用 aos 體系（符號程式）試解 ARC-AGI-1。本庫是 `wf/` 與 `notes/rounds/` 的濃縮層：每節點只放摘要與「完整版見哪個檔」，**wf 原檔才是正本**，衝突以 wf 為準。易變狀態（現役線、時間）不寫進來，只指去看哪個檔。

路徑都相對 repo 根 `/home/lorkhan/repo/arcagi/`。

## 目錄

- `resume`：主 session compact／重開後怎麼接回（讀序、檢查表、狀態在哪）。
- `lead`：派工隊長（分工與模型、交接書必備段、思考設計輪、請教 aos、收線）。
- `worker`：施工隊員（安全邊界、資源限制、codex、commit、回報格式）。
- `project`：專案是什麼、code map、輪次與方向、使用者建議摘要。

## 用法

`{"op":"read","path":"lead"}` 往下讀；`{"op":"find","query":"STOP"}` 跨節點搜。交接書可寫「先 read 知識庫 `worker`」。
