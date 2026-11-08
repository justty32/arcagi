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

## 3. 長積木做法與元優化

**本輪做 G1（主）+ G4（副）；G2、G3 延 r08。**

- **G1 壓縮**（`grow/compress.py`）：每 pass 結束，對所有解出的程式枚舉大小 ≥2 的子樹，兩兩反統一（anti-unification）得最多 2 個槽的模板；分數 = MDL 省量 = `出現次數×大小 − 大小 − k×槽數`，k 預設 2；省量 >0 的取前 m=3 加入 `aos/seedlib/blocks.json`（含推得的型別簽名、來源題、省量）。同時記每個積木被用次數，枚舉順序改為「大小優先、同大小依先驗（log 使用次數）」。庫上限 40，連續 3 pass 未用的退場。
- **G4 演化**（`grow/evolve.py`）：每 pass 拿 100k 節點中的 20% 做變異（子樹替換、同型別節點互換）與交配，適應度 = train 像素對率，只為「近失敗」程式補刀。有隨機源，**固定 3 個 seed 跑三條**。
- **元優化層 1**（`grow/knobs.py`，`data/r07/knobs.json`）：旋鈕只有 6 個——`m`、`k`、`max_holes`、G4 預算比例、枚舉排序（大小優先／先驅加權）、lambda 體深度。`grow/meta.py` 每回合改一個旋鈕跑一條曲線，`AUC_L` 進步才接受；每次嘗試寫一行到 `aos/meta/ledger.jsonl`（`kind=r07, knob, before, after, cost_s`），只記不分紅。
- **層 2**：本輪只做一件事——每個旋鈕記 `tried/accepted`，下一回合用 Thompson 抽樣決定改哪個旋鈕，取代均勻亂選。
- **雜訊**：純枚舉樹跑兩次，`curve.csv` 的 sha 必相同（寫成測試）。G4 三 seed 取平均與全距；旋鈕改動的進步要 **> 三 seed 全距** 才算真進步。
- **防汙染**：`scripts/r07_purity.sh` 一次做完 §1 四條規則；不過不准打 tag。

## 4. 過 train 答錯的收法

只動主線 `src/arcagi/solvers/`，支線檔唯讀呼叫。

- `solvers/guard.py`：三條通用守門，對任何來源（Python、native）的候選一視同仁：(a) **最小支持度**——同一輸出至少被 2 個相異程式產出才首選，否則降級；(b) **未見值守門**——測試輸出含 train 任何輸出都沒出現、且測試輸入也沒有的顏色值，該候選不信；(c) **合成校準**——training 題有 S5 合成 pair 時，候選必須再過 4 個合成 pair，過不了就丟（evaluation 沒合成集，(c) 自動停用，所以 (a)(b) 才是上線的門）。
- `solvers/gated.py`：包一層入口，呼叫 `native.hybrid` 與 `solvers.search` 拿候選清單，再過 guard；原入口不改。
- **驗收數字**（training 400，r06 混合基線 138 對、過 train 答錯 Python 30 + native 27）：擋掉的「過 train 答錯」≥15；誤擋「本來答對」≤3；training 淨對數 ≥138 不得下降。報表 `reports/gate-r07/README.md` 列每題擋／放／改判三欄。

## 5. 三條 opus 線（按路徑切，可寫路徑互不重疊）

| 線 | 可寫路徑 | 驗收（可觀察） |
|---|---|---|
| A 起點樹 | `src/arcagi/seed/`、`tests/seed/`、`scripts/r07_purity.sh` | ① `prims.py` ≤40 原語、禁用字樣 grep 零命中；② `pytest tests/seed` 綠，含非網格測試；③ 16 題×100k 節點、8 workers、`nice -n 19` 下 <90 秒；④ pass 0 報出解了哪 0～2 題；⑤ purity 腳本通過並打 `r07-seed0` tag |
| B 學習循環＋曲線 | `src/arcagi/grow/`、`scripts/r07_taskset.py`、`scripts/r07_curve.py`、`data/r07/`、`reports/curve-r07/`、`aos/seedlib/`、`aos/meta/ledger.jsonl`（追加） | ① taskset.json 兩次生成 sha 相同，8/8、4/4 分佈符合；② 三棵樹各一份 8-pass curve.csv：空樹、空樹+G1+G4、舊樹對照（唯讀呼叫 `solvers.search`，pass 0 應 ≥4）；③ 純枚舉雙跑 sha 相同、G4 三 seed 全距列出；④ 至少 1 個 MDL 省量 >0 的積木進 seedlib；⑤ meta 嘗試 ≥3 回合、ledger 有行；⑥ 報 `AUC_L` 三個數 |
| C 守門 | `src/arcagi/solvers/guard.py`、`solvers/gated.py`、`tests/solvers/test_guard.py`、`scripts/r07_gate_eval.py`、`reports/gate-r07/` | ① 單元測試覆蓋三條門；② training 400 跑完，擋錯 ≥15、誤擋 ≤3、淨 ≥138；③ 報表三欄齊；④ 不改任何支線檔（`git diff --stat` 證明） |

B 依賴 A 的介面 `seed.enumerate(lib, tasks, budget_nodes) -> list[Solution]` 與 `seed.Program` tuple 形式，在 03-設計 先定死，B 先用 stub 跑通循環。

**本輪整體門檻**（缺一不算過）：purity 通過並打 tag；三棵樹曲線齊且 llm_calls 全 0；舊樹 pass 0 在 L16 ≥4 而空樹 ≤2（證明量具分得出樹）；`AUC_L(空+G1+G4) ≥ AUC_L(空)`（允許兩者都很低）；守門三數達標。**不要求** 空樹學會多少題——本輪交的是量具與第一條曲線，不是分數。

**evaluation**：本輪不跑全量（機器被 S3 的 ev-dev1 佔著）。若 C 線做完機器已空，可選跑一次 `gated` 全量 evaluation 作 r08 基線，不計入門檻。

## 6. 延後與新支線

**延到 r08**：G2 re-arc 通用片段搬運（先要 purity 工具把「片段 vs 整支 verifier」判得出來）；G3 殘差診斷（手寫分類器要先算進起點樹成本）；C++ 枚舉器（Python 100k 節點夠本輪用）；層 2 超過 Thompson 抽樣的部分；題組擴到 32+ 與 lambda 體深度 >2；evaluation 全量。

**新支線**：
- **M1 學習曲線量具**——本輪就是 B 線，不另開；r07 結束後把 `scripts/r07_curve.py` 維護交 aos（sonnet 雜活），列入 r08 常駐。
- **M2 樹變異／組合器**——開給 aos，但 **在 B 定好 `knobs.json` 與 seedlib 格式之後**（r08 起），可寫路徑限 `src/arcagi/grow/mutate/`；不得碰 `seed/`。
- **M3 meta 帳**——不開，`aos/meta/ledger.jsonl` 已有，併入 M1。
