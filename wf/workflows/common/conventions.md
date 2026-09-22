# conventions — 程式碼慣例（碰原始碼的工作流共用）

[common/README](README.md)｜[INDEX](../../INDEX.md)

碰原始碼的工作流（feature-dev / refactor / investigation）共用這套規矩：**寫碼時要遵守什麼**。哪個檔負責什麼領域、測試在哪 → [code-map](code-map.md)；真相層優先序也在 [code-map](code-map.md)。結構整理原則 → [STRUCTURE](../../STRUCTURE.md)。

## 慣例

| 項目 | 規矩 |
|------|------|
| 檔案拆分 | 按領域拆 module（`src/arcagi/<領域>/`，領域見 [code-map](code-map.md)）；單檔超過 300 行就照 STRUCTURE 檢視 |
| 命名 | PEP 8：模組／函式 `snake_case`、類別 `PascalCase`、常數 `UPPER_SNAKE`；`ruff check` 的 `N` 規則把關 |
| 註解語言 | 程式碼註解與 docstring 英文、文件繁中 |
| breaking change | 改公開函式簽名前 `grep -rn` 所有呼叫處，同一 commit 一起改 |
| 型別 / schema 同步 | 公開函式都有型別註記；任務 JSON 沿用 ARC-AGI-1 官方格式（`train`/`test` 各為 `{input, output}` 網格清單，值 0–9），不自訂格式 |
| 相依 | 新增套件前先問（見 [user](user.md)）；版本鎖進 `uv.lock` |
| 求解器改動 | 附評測集分數變化（改前／改後各解出幾題）；分數下降要在 commit 訊息說明原因 |
