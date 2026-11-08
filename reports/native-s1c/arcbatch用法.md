← 入口 [native-s1c/README](README.md)

## arcbatch 用法

```
native/bin/arcbatch --tasks LIST [--data-dir DIR] [--task FILE ...] [--configs CONFIGS.jsonl]
                    [--threads 6] [--cache DIR] [--dump] [--spec PATH] [--out RESULTS.jsonl]
```

- `LIST` 每行一題：題檔路徑（相對於清單所在資料夾），或配 `--data-dir` 寫題號。`#` 開頭略過，空白或逗號之後的字略過。題檔要有 test 的 output 才能算 `test_correct`。
- 設定檔每行一個 JSON，欄位都可省略：

| 欄位 | 意思 | 預設 |
|---|---|---|
| `name` | 設定名 | `default` |
| `prims` | 原語白名單（只限制搜尋時列舉哪些；空 list＝全關） | spec 全部 |
| `drop` | 原語黑名單 | 無 |
| `macros` | `{名: [[原語, 參數…], …]}`，加進搜尋；macro 可以引用別的 macro（展開後只能用 C++ 已移植的原語） | 無 |
| `learners` | 開哪些 learner：`colormap`、`colormap_step`（colormap 當中間步）、`object_colormap`、`local_rule`、`x_vrule`；給了就只開列出的 | 全開 |
| `max_nodes` | 節點預算（主預算，可重現） | 2000000 |
| `max_depth` | 最大步數 | 4 |
| `budget` | 秒數上限（保險，正常用不到） | 60 |
| `max_solutions` | 最多收幾個 train 全對的程式 | 200 |
| `gate` | 守門參數：`support_alone`（4）、`support_after`（16）、`max_len_penalized`（4）、`max_steps_before_learner`、`max_table_rows`、`min_votes`；設 0 或 -1 關掉 | 見括號 |

- 主線 r07 的「空樹」在 C++ 端＝`{"prims":[],"learners":[]}`（D-r7-6）。
- 輸出每行一筆（題 × 設定）：`config`、`task_id`、`train_fit`（有 train 全對的程式）、`answered`（守門後還有答案）、`test_correct`（top-1 對）、`oracle_correct`（任何一個候選對）、`n_solutions`、`gated`、`program`、`cost`、`votes`、`nodes`、`nodes_to_first`（第一個 train 全對程式出現時已走的節點數）、`depth`、`out_of_budget`、`seconds`；加 `--dump` 會多一欄 `solutions`（每個候選的程式、cost、votes、對錯）。
- 每個設定最後一行是總結：`summary: true`、`solved`、`train_fit`、`answered`、`wrong`、`oracle`、`nodes`（總節點）、`task_seconds`（逐題秒數加總）、`cache_hits`、`wall_seconds`（整批的牆鐘時間）、`threads`。
- top-1 規則跟 Python `vote.choose` 相同（learner 結尾的權重 0.5；`local_rule`／`x_vrule` 排最後；同 cost 比票數），差別是沒有 formula 的形狀提示。
- 快取：鍵＝binary 內容雜湊＋spec 雜湊＋設定 JSON＋題檔內容，一筆一個檔，可以多個行程共用。
- 結果可重現：節點預算下，1 執行緒和 6 執行緒的輸出逐行一致（秒數除外）。

