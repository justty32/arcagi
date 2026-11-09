# think-1 規劃（fable）：給 aos 樹裝一把尺、一道便宜階梯、一座語言橋

> 對應 `01-簡報.md` 的 R1～R6。目標不是多解題，是讓「審查→改進→產積木」這個迴圈變便宜、可量、能借 GPU 符號運算。所有新東西都放在樹的旁邊（`ws/hammer/think1/`）或 arcagi 的 `src/arcagi/think1/`，**不改引擎**，只讀樹的檔、只透過節點 inbox 介入。

## 0. ELI5 結論

活樹現在像一個只有「大手術」一種治療的醫院：要審查一個積木，得整棵樹重跑 5 分鐘；要產一個積木，得請 LLM 寫蠟模（257 筆只有 4 題能用）；而且沒有體重計，所以不知道哪次改進是真的、哪次是雜訊。GPU 那邊有一台每秒能評估上億支程式的機器，卻講另一種語言，門口進不來。

這輪要做三件事，照順序：**(1) 裝尺**——從現有的 `curve.csv`／`ops.jsonl`／`solutions.jsonl` 算出每個積木的「近 N 次成功率、閒置幾輪、佔多少解」計分卡，和整棵樹的 AUC_L＋成本帳，再用小預算的「快撥樹」量兩次得到雜訊 σ，以後任何改進只有 ΔAUC_L > 2σ 才算數。**(2) 裝便宜階梯**——審查 L0（固定程式看證據）、L1（參數掃描）、改進 I0（拿 `near_top` 差一點的程式挖洞補洞，候選直接丟進樹的影子快道免費評分）。**(3) 架橋**——先盤點 DStep 格子步驟和 seed AST 哪些能互譯、用 `gpusearch` 當「這題在 DStep 空間可解嗎」的神諭，再把 seed AST 編成 EvoGP 式定長張量，讓 GPU 遺傳搜尋直接在樹的語言上跑。今晚第一塊只做 (1) 的前半：純 CPU、只讀檔、兩個腳本、一個測試，驗收是數字。

## 1. 架構：think1 側車

```
ws/hammer/think1/                  # 樹旁邊的側車目錄（可寫）
  audit/epoch-<n>.jsonl            # L0 計分卡，一列一 op
  meta/curve-summary.json          # AUC_L、每 epoch 成本、ΔAUC/1e6 evals
  meta/meta.jsonl                  # 改進動作帳（獨立記帳、不隨試驗重置）
  meta/noise.json                  # 雜訊尺：同設定重跑 2 次的 σ
  candidates/epoch-<n>.jsonl       # I0/I1 產出的候選 comb（未入樹）
  bridge/coverage.json             # DStep↔seed AST 互譯盤點
  quick/                           # 快撥樹（frozen 預算縮小的樹副本）
src/arcagi/think1/{audit,meter,neartop,bridge}.py
scripts/think1_audit.py  think1_meter.py  think1_neartop.py  think1_bridge.py
tests/think1/
```

原則：side-car **只讀** `ops.jsonl`、`ledger.jsonl`、`epochs/*/{curve.csv,solutions.jsonl,blocks.json,shadow_blocks.json}`、`frozen.json`；**只寫** `think1/` 與 `nodes/<節點>/inbox/*.json`（走既有 `add-op`／`weight`／`say` 三種 cmd，格式見 `epoch.py:_apply`）。可以 `import arcagi.hammer.formats / body / exec`（唯讀使用，不改）。

## 2. 方案分塊（排序＝施工順序）

### 塊 A【今晚第一塊，2 小時，純 CPU，單一 gpt 施工者】L0 計分卡＋AUC 尺

**做什麼**
1. `scripts/think1_audit.py <tree_root> [--epoch N]`（預設最新 epoch）→ 寫 `think1/audit/epoch-N.jsonl`，一列一 op（21 列），欄位：

| 欄 | 來源 | 定義 |
|---|---|---|
| `id, kind, status, by, born_epoch, mdl_bits` | `ops.jsonl` | 原樣 |
| `age` | born_epoch, N | N − born_epoch |
| `shadow_epochs, new_solves_n, witness_hits` | `evidence` | 原樣（new_solves 取長度） |
| `uses_L, uses_P` | `epochs/*/blocks.json` ＋ `solutions.jsonl` 的 `program` | 該 op id（或其 body 片段）出現在幾題的解裡；找不到對應方式就記 null 並在 `note` 說明 |
| `hit_rate_10` | 最近 ≤10 個 epoch 的 `shadow_blocks.json`／`blocks.json` | 有解題貢獻的 epoch 數 ÷ 觀測 epoch 數；無觀測記 null |
| `idle_epochs` | 同上 | 連續幾個 epoch 沒有任何貢獻 |
| `verdict` | 規則 | 見下 |

verdict 規則（數字寫死在 `audit.py` 頂端的 dict，方便之後 L1 掃描它）：
- `keep`：status=live 且（uses_L+uses_P ≥ 1 或 hit_rate_10 ≥ 0.3）
- `watch`：status=live 且 idle_epochs ∈ [2,4]
- `retire-candidate`：status=live 且 idle_epochs ≥ 5 且 uses=0
- `dormant-stale`：status=dormant 且 age ≥ 6 且 new_solves_n=0
- `unmeasured`：kind ∈ {gate, route, sieve} 且沒有任何證據欄非零 → 這就是 R3 說的「參數多半沒作用卻沒人發現」的標籤；塊 B 的 L1 掃描只處理這一類
- `incubating`：status=incubating 原樣

2. `scripts/think1_meter.py <tree_root>` → 寫 `think1/meta/curve-summary.json`：
   - `auc_L = Σ_epochs solved_L`（8 epoch 滿分 128；現況應算出 40）、`auc_P`、`auc_H24`
   - `cost = Σ(evals_body+evals_shadow+evals_meta+evals_foundry)`、`wall_s_total`、`llm_calls`
   - `eff = auc_L / (cost/1e6)`（每百萬 evals 換到的 AUC_L）
   - `lib_bits_final, lib_size_final, stall_final`
   - 另附 `--compare A.json B.json`：印 ΔAUC_L、Δcost、Δeff，並讀 `think1/meta/noise.json`（沒有就當 σ 未知、印警告），判 `significant = |ΔAUC_L| > 2σ`
3. `tests/think1/test_audit.py`、`test_meter.py`：用 `tests/think1/fixtures/` 內**手刻**的迷你樹（3 個 op、3 個 epoch 的 curve.csv/blocks.json，自己造，不複製真資料）驗證規則與 AUC 計算；再加一個 `@pytest.mark.skipif(not Path(ws).exists())` 的煙霧測試對真樹跑一次，只檢查列數與欄位齊全。

**不做什麼**：不跑樹、不呼叫 GPU、不寫 inbox、不碰 `src/arcagi/hammer/`。CPU 只有讀檔與 JSON 處理，秒級完成。

**驗收量法（全部可自動）**
- `think1/audit/epoch-8.jsonl` 恰 21 列，`verdict` 全非空；`gate_g1` 與 6 條 route 列得到 `unmeasured`（這是對簡報 R3 證據的可核預測：evidence 全零）；至少 1 條 dormant comb 得到 `dormant-stale`。
- `curve-summary.json` 的 `auc_L == 40`、`llm_calls == 0`、`cost` 等於 curve.csv 四個 evals 欄的和（手算一次核對）。
- `uv run pytest tests/think1 -q` 全綠，且 `uv run python -m arcagi.hammer.check ws/hammer` 仍過（證明側車沒弄髒樹）。
- 兩個腳本在真樹上各 < 5 秒。
- 若 `uses_L/uses_P` 真的對不上（blocks.json 的格式與 op id 無法對應），允許填 null，但 `note` 要寫清楚對應缺口，這本身就是給塊 B 的輸入。

### 塊 B【明天上午，CPU，約 3 小時】快撥樹與雜訊尺

- 把 `ws/hammer/` 複製成 `ws/hammer/think1/quick/`（排除 `epochs/ live/ tmp/ ledger.jsonl`，ops 全部回到空樹起點），`frozen.json` 改 L 預算 25000、P0 10000、epochs 4；目標單次 ≤ 40 秒（現在 8 epoch 約 5 分鐘，1/4 預算×一半 epoch）。
- 同設定跑 2 次 → `meta/noise.json`：`sigma_auc_L`、`sigma_cost`。門檻：σ_auc_L ≤ 2 才可當尺；超過就要先找非決定性來源（threads、dict 順序）。
- 從此「改一處、量一次」的回合從 5 分鐘降到 40 秒，R5 的迭代速度用側車繞過，不必改引擎。
- `meta/meta.jsonl` 開始記帳：每個改進動作一列 `{ts, action, tool, cpu_s, evals, gpu_s, llm_calls, delta_auc_L, significant}`，不隨試驗重置。

### 塊 C【明天下午，CPU ≤4 worker，約 4 小時】I0 改進器：near_top 挖洞補洞（R2、R4）

- 輸入：最新 epoch `solutions.jsonl` 裡 `train_ok=false` 且 `near_top` 非 `["$in"]` 的題（epoch 8 約 10 L16＋33 P 題；`["$in"]` 的題代表搜尋連邊都沒摸到，跳過）。
- 對每個 near_top AST，列舉「挖一個子樹成洞」的位置（深度 ≤3，最多 8 個洞），每個洞用 32 原語＋現有 live comb 枚舉深度 ≤2 的填法（每洞 ≤ 5,000 候選，用 `arcagi.hammer.body/exec` 的 seed 評估器）；評分＝train pair 格子相符率（cells 匹配比例），記最佳改善。
- 輸出 `think1/candidates/epoch-N.jsonl`：`{task_id, hole_path, fill, ast, match_before, match_after, train_ok, mdl_bits}`，並把 `train_ok=true` 或 `match_after − match_before ≥ 0.10` 的填法子樹抽成 comb 候選（`sig` 用 `formats.new_op` 推，`by: "think1-neartop"`）。
- `--submit --cap 8`：每個 epoch 最多 8 條寫 `nodes/grow/inbox/<ts>.json`（cmd `add-op`，不帶 live → incubating），讓既有影子快道免費評分；judge 照原規則升級。這是「不經 LLM 產積木」的第一條通道。
- 驗收：43 題中 ≥ 5 題 match_after 比 near_top 提高 ≥ 10 個百分點；≥ 1 題 train_ok 翻正；整體 ≤ 10 分鐘（4 worker）；送入樹後下一 epoch 的 `n_incubating ≥ 1` 且 `evals_shadow` 上升、H24 不退。

### 塊 D【本週，CPU 先，GPU 後】語言橋（R1）

- D1 盤點（CPU，2 小時）：`think1_bridge.py --inventory` 讀 `native/gpu/space.hpp`（唯讀）列出 DStep 字母表，對每個 op 標：`seed-exact`（seed 32 原語能寫，如 D4 的 `reverse`/`transpose` 組合）、`seed-comb`（要一個 comb 才能寫，如 `tile`）、`none`（物件類、`fill_enclosed`）。寫 `bridge/coverage.json`，數字目標：先知道覆蓋率是多少（預估 30～50%）。
- D2 神諭（GPU 閒時，顯存 512 MiB）：對樹未解的 L16＋P 題跑 `native/bin/gpusearch --depth 3 --mode gpu --samples 20 --out think1/bridge/oracle-<date>.jsonl`。有 DStep 解且 D1 覆蓋全部步驟的題 → 機械翻譯成 seed AST comb 候選，走塊 C 的 `--submit`。有解但翻不過去的步驟 → 累積成「缺口清單」`bridge/gaps.jsonl`，這才是鑄模爐該收的請求（取代 LLM 蠟模的「猜步驟」）。
- D3 編碼（本週後半）：seed AST 的 EvoGP 線性前綴編碼 `(node_type:uint8, node_value:int16, subtree_size:uint8) × MAX_NODES=32`，存 `.npy`；先寫 CPU 參考實作與 round-trip 測試（AST→張量→AST 100% 還原、`ops.jsonl` 12 條 comb 全過），GPU kernel 留給 N2／N3 線那邊接。

### 塊 E【r10 範圍】L1 審查、I1 替換改進、小神經排序器

- L1：對 `verdict=unmeasured` 的 gate 參數在快撥樹上做單參數 ±50% 掃描（每參數 3 點×40 秒），ΔAUC_L 在 ±2σ 內的參數標 `dead-param`，寫回 `audit/params-<date>.json`；累積 2 輪仍 dead 就建議（由使用者）移除。
- I1：「只做特定替換」的改進器——規則表（例如 `["reverse",["reverse",x]]→x`、常數折疊）直接化簡 comb body，用 mdl_bits 下降 ≥ 2 bits 為採用門檻。
- 神經排序器（EvoNUDGE／GridCoder 式）：等塊 C＋D2 累積 ≥ 200 支 train_ok 程式再訓練，否則資料不足；先用 SyMANTIC 式「展開特徵→L0 稀疏選擇」做無神經的先驗。

## 3. 與反省題對照

| 反省題 | 方案塊 | 一句話 |
|---|---|---|
| R1 兩套語言 | D | 先盤點覆蓋率，再用 gpusearch 當神諭、缺口進鑄模，最後 EvoGP 編碼讓 GPU 直接跑 seed AST |
| R2 造詞乾涸 | C | near_top 是現成的「差一點」材料，挖洞補洞不靠已解題 |
| R3 沒有便宜階梯 | A、E | L0 固定程式讀證據、L1 參數掃描、I1 特定替換 |
| R4 靠 LLM 蠟模 | C、D2 | 兩條不經 LLM 的通道：挖洞補洞、DStep 翻譯；LLM 只收「缺口」 |
| R5 執行成本 | B | 不改引擎，用快撥樹把回合從 5 分鐘縮到 40 秒 |
| R6 沒有尺 | A、B | AUC_L＋成本帳＋2σ 雜訊門檻＋獨立 meta 帳 |

## 4. 方向題（最多 5 題）

**Q1 語言橋走哪邊？** 推薦：**先翻譯（D1/D2），再編碼（D3）**，不新增 op kind。
- 選翻譯：今晚不動引擎、立刻能用 gpusearch 的解；代價是覆蓋率可能只有三四成，物件類步驟翻不過去。
- 選新增「格子步驟程式」op kind：覆蓋 100% 的 GPU 解，但要改 `hammer/formats` 與 exec（r10 才能動），且樹裡會有兩種不能互相組合的積木。

**Q2 量尺用快撥樹還是全樹？** 推薦：**快撥樹（B）當日常尺，全樹每日一次當真值**。
- 選快撥樹：40 秒一回合、能量雜訊；代價是小預算可能看不到需要 100k 節點才解的題，ΔAUC 偏保守。
- 選全樹：數字就是正式數字；代價是 5 分鐘一回合、一天做不了幾次比較，雜訊尺也量不起。

**Q3 候選積木要不要直接進樹？** 推薦：**進，但只走 `add-op` incubating、每 epoch ≤ 8 條**，讓影子快道與 judge 把關。
- 選直接進：免費用到既有評估與升級規則，證據累在 `evidence` 欄；代價是候選多了會撐大 `evals_shadow`（現在已和 body 一樣大），所以要設 cap。
- 選只留在 `think1/candidates/`：樹保持乾淨；代價是要自己再寫一套評估與升級，等於重造 judge。

**Q4 雜訊尺要花多少？** 推薦：**同設定跑 2 次（不是 1 次、也不是 5 次）**，σ 用兩次差的 |Δ|/√2 估。
- 選 2 次：成本 80 秒，夠分辨「改進 ≥ 3 題」等級的訊號；代價是 σ 估得粗。
- 選 0 次：省時間；代價是 R6 原封不動，所有比較仍是手工判讀。

**Q5 神經排序器何時開始？** 推薦：**延後到有 ≥ 200 支 train_ok 程式（塊 C＋D2 累積）之後**，本週只做無神經的 SyMANTIC 式先驗。
- 選延後：不花 GPU 訓練時數在資料不足的模型上，避開 EvoNUDGE 的 8 GPU×24h 成本；代價是「符號＋神經混合」這條使用者點名的線本週看不到產出。
- 選現在開始：可以先用 GridCoder 式「位置×DStep 機率表」在 overnight 的 phase-A 解上訓練；代價是只服務 DStep 空間，與 R1 的橋還沒接通，泛化有限。

## 5. 施工者注意（給今晚的 gpt）

- 只寫 `ws/hammer/think1/`、`src/arcagi/think1/`、`tests/think1/`、`scripts/think1_*`；`src/arcagi/think1/__init__.py` 要有。
- 讀樹只用 `pathlib`＋`json`＋`csv`；要用 `arcagi.hammer.formats` 只能 import，不能改。
- 閾值全部放在模組頂端一個 `RULES` dict，並在計分卡每列附 `rules_version: "a1"`，之後 L1 掃描規則時才對得上。
- 真樹是活的（daemon 可能在跑）：讀 `epochs/<n>/` 前先確認 `status.json` 存在，否則退一個 epoch。
- 完工回報貼三個數：`auc_L`、`unmeasured` 列數、pytest 通過數；再貼 `uses_*` 對應是否成功。
