# experiments — 跑分實驗紀錄（假設 → 指令 → 數字 → 結論）

[WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)｜實驗工具教學 [docs/experiments](../../../docs/experiments/README.md)

拿**一個明確假設**去跑求解器（training／evaluation／合成題），留下別的 agent 與日後的自己查得回的紀錄：跑了什麼、數字多少、跟誰比、結論是什麼。`artifacts/` 被 `.gitignore` 排除，**數字不抄進紀錄就等於沒跑過**。

**何時用**：「跑個實驗看會怎樣」「這個求解器想法在 evaluation 上幾題」「比較 A／B 兩種方法」；求解器改動要記改前／改後題數；子 agent 交回一批跑分要收進來。
**何時不用**：只驗證程式沒壞 → [testing](../testing.md)；只讀碼回答一個窄問題 → [investigation](../investigation.md)；想法還在「要不要做」 → [planning](../planning.md)。

## Done when

- [ledger.json](ledger.json) 多一列（`wf-table/1`，讀寫照 [data-files](../common/data-files.md)），`result`、`baseline`、`verdict` 三欄非空。
- 有細節要留的（失敗分析、逐題觀察、參數掃描）：`records/<YYYY-MM-DD>-<slug>.md` 存在且照下方骨架，ledger 該列 `record_path` 指向它；一句話講得完的不必開檔。

## 流程

1. **先寫假設**：一句可被數字推翻的話，並指定**比較基準**（同 split、同題目集、同逾時的上一個最佳或 identity）。
2. **跑**：單一求解器用 `uv run arcagi eval …`，多方法／多參數用 `uv run arcagi experiment <設定> --output artifacts/<slug>`（指令與輸出格式見 [testing](../testing.md)、[docs/experiments](../../../docs/experiments/README.md)）。輸出目錄不可重用。
3. **讀數字**：`tasks_correct／tasks_total`、`errors`，重複試驗看逐次成功率；**逾時與錯誤留在分母**，不可自總數移除。合成題分數與官方 split 分開記，不宣稱私有測試分數。
4. **記**：ledger 加一列，細節多才開 record 檔。只寫數字支持的結論；否定結果一樣要記，免得別的 agent 重跑。
5. **結論影響方向時**：值得做下去的想法搬進 [planning](../planning.md) roadmap；要使用者拍板的進 [WAIT_USER](../../WAIT_USER.md)。

**資源**：完整 evaluation（400 題、每題獨立程序）吃滿 CPU，**同一時間只跑一份全量評測**；多個子 agent 並行時由派工者指定誰能跑全量、其他人用 `--task`／tag 篩小集合（見 [dispatch](../dispatch/README.md)）。

## ledger 欄位

| 欄 | 內容 |
|----|------|
| `id` | `<YYYY-MM-DD>-<slug>`，與 record 檔名、`artifacts/<slug>` 對得上 |
| `date` | 跑的日期 |
| `hypothesis` | 一句假設 |
| `solver` | plugin（`module:function`）或實驗設定檔路徑，加 commit 短 hash |
| `split` | `training`／`evaluation`／合成資料與 manifest |
| `result` | `correct/total, errors=N`（重複試驗加平均成功率）|
| `baseline` | 比較對象與它的數字 |
| `verdict` | 是／否／不確定＋一句 |
| `record_path` | record 檔相對路徑（沒有就空）|

## record 骨架

```markdown
# <id>：<一句假設>

[experiments](../README.md)

- 指令：`<完整指令>`；commit `<hash>`；設定檔 `<路徑>`
- 結果：<數字>；基準：<數字>
- 結論：<是／否／不確定，一句>
- 觀察：<解出／新失敗的題目 id、錯誤類型、耗時異常>
- 下一步：<值得試的、或明說不再追>
```

## 交接

- 求解器改動 commit 訊息附分數變化（[feature-dev](../feature-dev/README.md)）。
- 由子 agent 跑的：交接書寫死「回報 ledger 一列的內容」，派工者核數字後再寫入（[dispatch](../dispatch/README.md)）。
