# aos/ — arcagi 的 aos 試驗場

把 arcagi 的積木與求解器接成 aos 的「資料夾＝程式」。搜尋仍在 Python 程序內跑（快）；資料夾管身分、狀態與帳。程式在 [src/arcagi/blocks/](../src/arcagi/blocks/__init__.py)，設計見 [r02 設計 §5](../notes/rounds/r02/03-設計.md)。

## 佈局

```
blocks/<name>/_metainfo.json   # name, kind(primitive|learner|macro), doc, params, cost, status(live|covered|retired), counter_uses
blocks/<name>/_entry           # sh：stdin {"grid":..,"params":[..]} → stdout 網格
blocks/<name>/_gradients.jsonl # 梯度信（近失敗），每積木上限 50 行
blocks/<macro>/program.json    # 巨集＝參數已定的 JSON 程式
blocks/pred_<hash>/{_metainfo.json,_rule.json,_entry}   # 產生的謂詞積木（kind=pred）
blocks/_gen/pred_combiner/_metainfo.json             # 產生器節點（kind=generator）
blocks/formula_<hash>/、blocks/extract_<hash>/       # r03 公式型、抽取型積木（_rule.json＝{"kind":"formula"|"extract",...,"body":..}）
blocks/_gen/formula/、blocks/_gen/extract/           # r03 產生器節點（_entry 跑產生器，metainfo 記 gen_seconds）
solver/_entry                  # 一題的 --external 檔案協定 → in-process search
pool/{config.json,wallets.json,ledger.jsonl,epochs/<n>.json}   # 帳
```

## 指令

- 補齊積木資料夾：`uv run python -m arcagi.blocks.sync`（保留既有 status、counter_uses）
- 單一積木：`echo '{"grid":[[1,2]],"params":[]}' | aos-exec --ws aos aos/blocks/flip_lr`
- 求解器：`uv run arcagi eval --split training --limit 20 --external "aos-exec --ws aos aos/solver {input} {output} {trace}"`
- 記帳一個 epoch：`uv run python -m arcagi.blocks.pool --report R.json --epoch N --split S`（同 epoch 同報告重跑＝不動；不同報告或跳號＝拒絕）
- 抽巨集：`uv run python -m arcagi.blocks.library --traces T1.jsonl T2.jsonl [--min-tasks 3] [--dry-run]`
- 產生謂詞積木：`uv run python -m arcagi.blocks.gen_predicates --split training --max-literals 2 [--live-cap 60] [--dry-run]`
- 產生公式／抽取積木：`uv run python -m arcagi.blocks.gen_formula --split training [--dry-run]`、`... gen_extract ...`；或 `aos-exec --ws aos aos/blocks/_gen/formula --dry-run`
- 單一公式／抽取積木：`echo '[[1,0,0],[0,2,2]]' | aos-exec --ws aos aos/blocks/formula_2367bc71` → `2`
- 帳（r03）：`config.json` 的 `essential` 永不建議退休；巨集分紅 50% 按成分下傳；產生器花費＝`gen_seconds`×`generator_rate`；有 `generator` 且連續 0 收入又 covered 的積木會真的改 `retired`；epoch 檔有 `generator_budget`（只記不用）
- 單一謂詞：`echo '{"object":{"is_largest":0,"shape_count":2},"group":[{"shape_count":2},{"shape_count":1}]}' | aos-exec --ws aos aos/blocks/pred_988c1402`（或直接給屬性 dict）→ `true`／`false`
- 搜尋讀的目錄：環境變數 `ARCAGI_BLOCKS`，否則本目錄的 `blocks/`；不存在時行為同 r01。

`--ws aos` 讓 aos-exec 的 stack 落在 `aos/.stack/`（已 gitignore）；不加則落在當前目錄的 `.stack/`。

## 謂詞積木（判斷型，r02 增補）

`_rule.json`＝`{"kind":"pred","in":"object","out":"bool","body":<AST>}`，AST 是 `["eq"|"ne"|"gt"|"lt",屬性,值]`、`["rank",屬性,"max"|"min"]`、`and`／`or`／`not`（求值器 [predicates.py](../src/arcagi/dsl/predicates.py)）。產生器只在 training 評分：分數＝能讓某連通方式下所有 train pair「物件變／不變」與謂詞真假完全一致的題數 − 字面數×0.5；≤0 不落地；同題集留最短、被不更長者題集包含者標 `covered`（純 `eq` 單字面被內建單屬性選擇器蓋住）；live 上限 60，舊的 pred_* 重跑後沒留下的標 `retired`。registry 把 live 謂詞載成物件選擇器 `(conn,"pred",名字)`，每原語最多多 2 個候選。pool：程式參數引用的 `pred_*` 也算靜態引用，其分紅 20%（`generator_cut`）轉給 metainfo 的 `generator` 節點。

## aos 概念對應

| aos | arcagi |
|---|---|
| 資料夾＝程式（`_entry`、`aos-exec`） | 每個積木、求解器各一個資料夾，可單獨叫 |
| `_metainfo.json`（N-68，不認得的 key 忽略） | 積木身分、cost、status、counter_uses；巨集另記 source_tasks |
| node-pool：epoch、20% 留存、80% 按靜態引用分紅、房租、連 3 次 0 建議退休 | 一次全量 eval＝一個 epoch；解出 1 題＝1000；花費＝`trace.metadata.block_calls`/1000×cost；房租 100 |
| 梯度信 `_gradients.jsonl` | 沒解出題的最佳近失敗，投給它引用的積木 |
| 想法 21 covered（不刪） | 巨集解得出的題都已有更便宜的不含巨集程式 → `status=covered`，搜尋不載入 |
| 退休封存 | `status=retired`：搜尋不展開，只由人改（pool 只列 `suggest_retire`） |
