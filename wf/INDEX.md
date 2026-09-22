# INDEX — arcagi 專案地圖

arcagi = **嘗試解決 ARC-AGI-1 的 Python 求解器專案**。本檔只描述**頂層**：每列一句話＋連結；目錄內部複雜就放它自己的 README / INDEX。

## Repo 佈局

| 路徑 | 內容 |
|------|------|
| `src/arcagi/` | 求解器原始碼（**規劃中，尚未建立**）；領域劃分見 [workflows/common/code-map.md](workflows/common/code-map.md) |
| `tests/` | pytest 測試，目錄鏡射 `src/arcagi/`（規劃中）|
| `data/ARC-AGI/` | ARC-AGI-1 官方資料集（git submodule，規劃中）：`data/training/` 400 題、`data/evaluation/` 400 題 |
| `notes/` | investigation／digest 產出的筆記（`notes/investigations/`、`notes/digest/`），長出來才建 |
| `workflows/` | 工作流（派發見 [WORKFLOWS.md](WORKFLOWS.md)；共享區 [workflows/common/](workflows/common/README.md)）|
| `.claude/commands/` | slash 指令適配層（可選）。Claude Code 為例：只讀專案根的這層，非侵入式佈局也留在根；沒有 slash 機制的工具忽略本目錄，直接跑 `tools/wf-lint.sh` |
| `tools/` | kernel 工具：`wf-lint.sh`（檢查）、`tabledb.py`（資料檔 CRUD／連結）、`find_big_lists.py`、`fix_moved_links.py`；非侵入式佈局在 `wf/tools/`；資料檔契約見 [workflows/common/data-files.md](workflows/common/data-files.md) |
<!-- wf-insert:INDEX -->

## 頂層文件

| 檔案 | 角色 |
|------|------|
| [WORKFLOWS.md](WORKFLOWS.md) | 派發器：意圖 → 工作流入口 |
| [STRUCTURE.md](STRUCTURE.md) | 結構整理參考（被動）：分層、膨脹即拆、四級成長、archive、工作流形式 |
| [SESSION-LOG.md](SESSION-LOG.md) | 我的 open 進度 |
| [WAIT_USER.md](WAIT_USER.md) | 等使用者親自做 / 驗證的事 |
