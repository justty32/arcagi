# decisions — 決策記錄（為什麼選 A 不選 B）

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

留下「為什麼」：git log 找得回改了什麼，找不回**為什麼放棄方案 C**。

**何時用**：在兩個以上可行方案裡選一個，且日後可能被問「當初為什麼」。
**何時不用**：只有一條路，或隨時可回頭的小事。決策過程要結構化評估 → knowledge 包的 decide 工作流，結論再落到這裡。

## Done when

- [decisions.json](decisions.json) 新增一列（**新的放最前**；讀寫照 [data-files](common/data-files.md)），且 `rejected_alternatives`、`premise` 兩欄非空。

## 記錄

已抽到 [decisions.json](decisions.json)（13 列，`wf-table/1`；2026-11-08 表超過 1 KB 依鐵律 3 抽出；2026-11-10 加 5 列晨報裁決）。欄位：

- `date`：決定日期。
- `decision`：定了什麼。
- `rejected_alternatives`：未選方案與原因。
- `premise`：前提（變了就重看）。
