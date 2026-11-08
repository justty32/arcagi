← 入口 [02c-Argon審-規劃](../02c-Argon審-規劃.md)

## (B) 提案：最想改的 4 條高槓桿做法

### 提案 1：快慢道隔離微影子＋補「不擠掉門」＋`tried_env_hashes`（步 4／5）
- **檔案**：[`src/arcagi/hammer/epoch.py`](../../../../src/arcagi/hammer/epoch.py)、[`judge.py`](../../../../src/arcagi/hammer/judge.py)、[`formats.py`](../../../../src/arcagi/hammer/formats.py)
- **步驟**：
  1. 將 `epoch.py` 步驟 ④ 拆為兩道：**C++ 快道**只跑 `live + incubating comb`，由解答 AST 實際呼叫的 `op_id` 精確記 `evidence.new_solves`；**Python 慢道**（`decomp:halves/nest`）只在路由選中 `rt_vsplit` 時，針對**當輪 C++ 未解題子集**跑 `seed.enum.solve`（省去已解題重跑，記憶體與耗時砍半）。`sieve/exclude` 移出每輪大鍋飯，只在 `scan.py` 獨立驗。
  2. 在 `judge.py` 升 `live` 前加**不擠掉門**：必須滿足 `Solved_L(shadow) ⊇ Solved_L(live)` 且共同已解題 `max(nodes_shadow / nodes_live) ≤ 2.0`。
  3. 在 `formats.py` 將算子列改記集合 `tried_env_hashes: list[str]`：淘汰或 H24 回滾時寫入當前 `env_hash`，僅當 `current_env_hash ∉ tried_env_hashes` 才允許從 `dormant` 喚醒，根除回滾死迴圈。

### 提案 2：單蠟模「常數抽槽」＋預設零等待與信箱熱輪詢（步 6）
- **檔案**：[`src/arcagi/hammer/foundry.py`](../../../../src/arcagi/hammer/foundry.py)、[`epoch.py`](../../../../src/arcagi/hammer/epoch.py)
- **步驟与門檻**：
  1. `foundry.ingest()` 在 `seed-sub` 擬合出段程式 `g_i` 後，掃描 AST 中未同時出現在全部 train 輸入盤面的字面 `Color` 與非結構 `Int`（`∉ {-1,0,1,2}`），自動抽成帶型別槽位（`max_holes ≤ 2`），產出不含題目常數的 `comb` 候選，讓單一蠟模即具備跨題遷移力。
  2. 入 `incubating` 門檻改用**段殘差壓縮門**：段輸入輸出差異 `info_bits ≥ 8`、`prog_bits(g_i) ≤ 0.6 × diff_bits` 且 `loo_ok` 全過；升 `live` 仍嚴守裁定 (2)。
  3. `epoch.py` 預設 `foundry_wait_sec=0`（短曲線遇 `stop` 只寫請求檔不阻塞）；唯 `ctl run --daemon` 開啟等待，且等待迴圈每 5 秒同步檢查 `RUN` 與處理 `inbox/`，讓 `ctl stop/pause/add-op` 秒級生效。

### 提案 3：`gate-scan` 離線等效去重＋將 H24 移出內迴圈（步 4／7）
- **檔案**：[`src/arcagi/hammer/scan.py`](../../../../src/arcagi/hammer/scan.py)、[`sieve.py`](../../../../src/arcagi/hammer/sieve.py)、[`metrics.py`](../../../../src/arcagi/hammer/metrics.py)
- **步驟與門檻**：
  1. **快取預篩（落實意見 2）**：`scan.py` 先在歷史 `solutions.jsonl` 與 LOO 快取上離線重放 20 組 `gate_g1` 變體（0 次 `arcbatch`、<0.2 秒），按產出的積木集 `blocks_sha` 分群去重，只對**積木集確實改變**的 ≤4 個代表變體跑 `3 seed × 4 epoch` 短曲線，砍掉 ≥80% 元層算力以守住「元層算力 ≤ 省下 50%」。
  2. **真值隔離**：`scan.py` 與 `sieve.py` **嚴禁讀取 H24／H8**，一律在 `P48` 的 A/B 兩折＋`L16` 上判決（`sieve/exclude` 必須在 A 折提煉、**B 折折外** 0 掉題且總節點降 ≥5% 才准進 `incubating`）；H24 僅留給主迴圈每 epoch 邊界做熔斷。
  3. `metrics.py` 將 `ΔAUC_total` 拆報 `H8`（純盲測）與 `H24`（熔斷集），並隨 `LTO-SCF∪` 強制印出聯集題數 `|U|`。

### 提案 4：改用「可搜尋狀態路由表」救活縱拆＋封死 M2 保送漏洞（步 2／5／9）
- **檔案**：[`src/arcagi/hammer/route.py`](../../../../src/arcagi/hammer/route.py)、[`03-設計.md`](../03-設計.md)
- **步驟與門檻**：
  1. 拔掉 8-epoch UCB 與延遲分潤，`kind:route` 改為純資料狀態表 `{"when_stall":"starve|saturate|ok", "arm":"...", "priority":int}`，交給 `scan.py` 做鄰域替換搜尋（真正滿足意見 6）；同時讓 `rt_vsplit` 呼叫現成 `witness.witness_splits` 為未解 L16 題寫入反向子目標，用 `seed-sub` 求解，不再空轉。
  2. **修訂 `03-設計.md` §1 的 `M2` 硬門檻**：
     - `M2(a)` 限定 **`by ∈ {"sleep", "foundry"}`**（排除 `agent-r08` 手寫 `halves` 保送）；
     - `M2(b)` 要求 `gate`/`sieve` 列在 **P48 B 折折外** 0 掉題且節點降 ≥5% 或多解 ≥1 題；
     - `M2(c)` 要求蠟模產出**含至少 1 個抽象槽位或跨對非平凡變換**的 `comb incubating` 列；
     - `M2(d)` 改為扣除靜態 `halves` 對照後的淨增益 **`AUC_L(hammer) > AUC_L(hammer-static-decomp)`**，或純盲測 `H8` +1 題。
