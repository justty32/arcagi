第七輪規劃稿：逐條定案簡報 §7 的六題，給隊長直接切線用；規劃者 fable 寫。

← [01 簡報](01-簡報.md)｜下一步 [03-設計](03-設計.md)

## 1. 起點樹

**放哪**：程式碼 `src/arcagi/seed/`（原語、型別、程式表示、解譯器、枚舉器）；學到的積木落 `aos/seedlib/`（pass 0 必為空檔 `blocks.json: []`），與 `aos/blocks/`、`aos/pool/` 完全分開。

**程式表示**：運算式樹，不是原語串列。節點 = 巢狀 tuple `(op, *args)`；輸入變數 `("$in",)`；lambda 只有單參數、de Bruijn 命名 `("$0",)`，lambda 體深度 ≤2。型別四種加箭頭：`int`、`bool`、`list[T]`（T 遞迴）、`T→U`；原語帶簽名，枚舉按型別只生合法樹。程式大小用節點數計（pass 0 上限 12），搜尋 = 按大小的型別枚舉 + 在 train 輸入上的觀察等價去重。輸入／輸出型別都是 `list[list[int]]`，解譯器不知道「矩形」、「相鄰」、「0～9」。

**通用 vs ARC 專屬的界線，四條可機器檢查的規則**：

1. **白名單**：`seed/prims.py` 是唯一原語來源，≤40 個，全列出：常數 `0..9`、`-1`；整數 `add sub mul neg mod eq lt max min`；布林 `and or not if`；序列 `len nth head last take drop reverse cons append concat range repeat count sort`；高階 `map filter zipwith fold transpose`。`transpose` 判定通用（Data.List 有、對任意元素型別成立），rot／flip 不給，要靠 `transpose∘reverse` 自己長出來。
2. **禁用字樣**：`src/arcagi/seed/` 與 `aos/seedlib/` 內任何識別字、字串不得含 `grid row col color colour rot flip crop obj shape pixel cell neigh sym bbox fill mask paint stamp`（grep 正規式寫進 `scripts/r07_purity.sh`）。
3. **非網格測試**：`tests/seed/test_prims_generic.py` 對每個原語餵 ragged list、>9 與負整數、空 list，不得報錯也不得特判——任何只對 0～9 矩形才對的原語一律視為 ARC 專屬。
4. **純淨 diff**：打 `r07-seed0` tag 時 `git diff --stat <tag> -- aos/blocks aos/pool` 必空，且 `aos/seedlib/blocks.json` 為 `[]`；`seed/` 不得 import `arcagi.dsl`、`arcagi.objrule`、`arcagi.native`、`vendor.re-arc`（純淨腳本用 grep 擋）。

誠實預期：pass 0 在 16 題上解 **0～2 題**（鏡像、轉置類），這是正常起點。

## 2. 題組與學習曲線

- **學習組 L16 + holdout H8**，全 training，皆有 S5 合成 pair。挑法寫死在 `scripts/r07_taskset.py`，輸出 `data/r07/taskset.json`（含 seed、規則文字、每題 sha）：(a) 唯讀 `docs/taxonomy/labels.csv` 分層，每個標籤桶按 `sha1(task_id+"r07")` 排序取前幾；(b) 防軟柿子：L16 中恰 8 題是 r06 混合入口在 training 解出的、8 題是沒解出的，H8 同比 4/4；(c) 格子 ≤15×15（純算力限制，寫明是偏置）。兩次執行輸出 sha 必相同。
- **holdout 只量不學**：H8 永不進長積木步驟。
- **曲線檔** `reports/curve-r07/<tree>/curve.csv`，每 pass 一列：`pass, solved_L, solved_H, wall_s, nodes, llm_calls, lib_size, lib_bits, mean_prog_nodes`。`llm_calls` 必為 0，非 0 整條曲線作廢。
- **固定預算**：8 個 pass × 每 pass 100k 搜尋節點（節點數跨機器可重現，秒只當附註）。
- **一個主數字**：`AUC_L = Σ_{pass=1..8} solved_L`（0～128）。同分比「到首 4 題所需累計節點」。`solved_H` 單獨報，不進任何選擇規則。

<!-- wf-nav -->
以下章節按語意拆到同名資料夾 `02-規劃-fable/`，原文照搬：
- [3. 長積木做法與元優化；4. 過 train 答錯的收法；5. 三條 opus 線（按路徑切，可寫路徑互不重疊）；6. 延後與新支線](02-規劃-fable/做法分線與延後.md)
