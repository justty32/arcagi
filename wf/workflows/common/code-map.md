# code-map — 程式碼導航 index（哪個檔負責什麼）

[common/README](README.md)｜[INDEX](../../INDEX.md)

碰原始碼前先查這張表，只讀相關領域列出的檔；動完再照維護鏈把表更新回去。寫碼慣例本身在 [conventions](conventions.md)。

## 領域表

| 領域 | 檔案 | 職責 | 測試在哪 |
|------|------|------|---------|
| 任務載入 | `src/arcagi/tasks/*` | 讀 ARC-AGI-1 任務 JSON 成 `Task`／`Grid` 型別，列舉 training／evaluation 集 | `tests/tasks/` |
| 求解器 | `src/arcagi/solvers/*` | 各種解法各一個子模組，共用 `Solver` 介面（輸入 task，輸出預測網格）| `tests/solvers/` |
| 評測 | `src/arcagi/eval/*` | 對整個 split 跑求解器、比對輸出、統計分數 | `tests/eval/` |
| CLI | `src/arcagi/__main__.py` | `solve` / `eval` 子指令 | `tests/test_cli.py` |

上表是**規劃中**的領域劃分，程式碼尚未建立；第一個 feature-dev 落地時照實況改。

## 真相層優先序

各專案可以改自己的優先序，但必須明確。預設：

```text
code/tests > schema/examples/fixtures > code map > docs > generated
```

- 上層與下層衝突時，**以上層為準並修正下層**。
- generated（產生出來的檔、html）永遠不是唯一真相。
- 原始來源與摘要衝突時，以**原始來源**為準。
- code map 是**導航不是規格**；行為以 code/tests 為準。

## 維護鏈：程式碼 > code map > 文檔

**優先級**（衝突或時間不夠時，依序保持一致）：程式碼 > code map > 文檔。
**code map 與程式碼衝突時以程式碼為準，立刻改 code map。**

1. **修改前**：先讀本表找到相關領域，只讀清單裡的檔——不讀無關領域的檔。
2. **修改後**：新增／刪除了原始碼檔案，或某檔職責顯著改變，必須同步更新本表。
3. 原始碼裡**不加**「對應 code map」的註釋（維護成本過高）；反向查找直接 grep 本檔。
4. 迭代期間本表可暫時落後，**commit 前必須對齊**（見 [feature-dev](../feature-dev/README.md)）。
