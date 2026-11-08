S4 題型分類法：ARC-AGI-1 800 題（training＋evaluation）的兩層類別表，標籤檔與每類解題率從這裡進。

← [支線清單](../../notes/rounds/支線.md)｜第一版粗分 [inventory](../inventory/training.html)｜報告 [reports/taxonomy-r04](../../reports/taxonomy-r04/README.md)

## 檔案

- [categories.md](categories.md)：判定順序與版本；類別表本體在 [categories.csv](categories.csv)（兩層、定義、例題）——標類的唯一依據。
- [overrides.csv](overrides.csv)：v1.1 新子類的改標（44 題），合併時覆蓋子 agent 標籤。
- [labels.csv](labels.csv)：800 題 `task_id,category,subcategory`（`wf-table/1` CSV），可直接給 `arcagi compare … --labels docs/taxonomy/labels.csv`（預設讀第二欄 category；`--label-column subcategory` 看子類）。

## 標法

1. `scripts/taxonomy_features.py` 算特徵（尺寸關係、顏色數、物件數、對稱、分隔線、輸出是否為輸入子網格、只加／只刪／只換色）並給粗分。
2. Claude subagent（opus）照 [categories.md](categories.md) 看題目（`scripts/taxonomy_show.py` 印的文字網格，不看 test 答案）定 category／subcategory；特徵粗分只當提示。
3. 每題只給**一個主類**：看「最難、最決定輸出的那一步」，不看前處理。
4. evaluation 只用來標類與報告每類解題率，不拿來調求解器；逐題失敗分析只從 training 未解題抽。
