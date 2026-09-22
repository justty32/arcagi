# info-map — 材料導航 index（哪份材料在哪、負責什麼）

[common/README](README.md)｜[INDEX](../../INDEX.md)

碰材料前先查這張表，只讀相關那幾份；動完再照維護鏈把表更新回去。與開發 flavor 的 code map **刻意對稱**：code map 描述程式碼結構，info-map 描述材料結構。碰材料的工作流（[digest](../digest.md) / [learn](../learn.md) / [organize](../organize.md) / [write](../write.md)）共用。

## 材料表

| 材料 | 位置 | 負責什麼 | 衍生產物 |
|------|------|---------|---------|
| ARC-AGI-1 官方資料集 | `https://github.com/fchollet/ARC-AGI`（本地 `data/ARC-AGI/`）| 任務長什麼樣：`data/training/`、`data/evaluation/` 各 400 題 JSON，`apps/` 有人工瀏覽器 | `notes/digest/arc-agi-dataset.md`（長出來才建）|
| Chollet, *On the Measure of Intelligence*（2019）| `https://arxiv.org/abs/1911.01547` | ARC 的設計理念、為什麼這樣評量、核心知識先驗（core knowledge priors）清單 | `notes/digest/on-the-measure-of-intelligence.md`（長出來才建）|

材料目前少到翻一下就找得到，本表只留骨架；agent 開始找不到材料時再補列。

## 維護鏈：材料 > info-map > 衍生產物

**優先級**（衝突或時間不夠時，依序保持一致）：材料 > info-map > 衍生產物（摘要、筆記、文章）。
**info-map 與材料衝突時以材料為準，立刻改 info-map。**

1. **動手前**：先讀本表找到相關材料，只讀清單裡的那幾份——不要整個資料夾翻。
2. **動手後**：新增／刪除了材料，或某份材料的職責顯著改變，必須同步更新本表。
3. 材料檔裡**不加**「對應 info-map」的註記（維護成本過高）；反向查找直接 grep 本檔。
4. 一輪 digest / learn 期間本表可暫時落後，**收尾前必須對齊**。
