← 入口 [03-設計](../03-設計.md)

## 4. Argon 審 r09 規劃（02c）的採納：施工契約以本節為準，與 02 衝突時本節優先

| 提案 | 採納 | 寫進契約的內容 |
|---|---|---|
| 1 快慢道＋不擠掉門＋`tried_env_hashes` | **全採**（D-r9-20） | `epoch.py` 影子跑拆兩道：**快道**（arcbatch）跑 live＋incubating `comb`，從解的 AST 實際用到的 `blk` 名精確記 `evidence.new_solves`；**慢道**（Python）只在 route 選到 `rt_vsplit` 時，對當輪快道未解的 L16＋P 題跑 `decomp` 列（halves／nest）。`sieve/exclude` 不進每輪影子，只在 `scan.py` 驗。`judge.py` 升 live 前加**不擠掉門**：`Solved_L(shadow) ⊇ Solved_L(live)`，且共同已解題 `max(nodes_to_first_shadow / nodes_to_first_live) ≤ 2.0`。`ops.jsonl` 列加 `tried_env_hashes: list[str]`：轉 dormant（含回滾）時寫入當下 `env_hash`；只有 `env_hash ∉ tried_env_hashes` 才准從 dormant 回孵化 |
| 2 單蠟模常數抽槽＋零等待 | **全採**（D-r9-21） | `foundry.ingest()` 擬合出段程式 `g_i` 後，把不在全部 train 輸入出現的字面整數、以及 ∉{−1,0,1,2} 的整數抽成槽位（`max_holes ≤2`，用 `grow.sig.infer_sig` 推簽名）；入孵化門改為段殘差壓縮門：段的 `info_bits ≥8`、`prog_bits(g_i) ≤ 0.6 × diff_bits`、`loo_ok` 全過；升 live 仍照裁定 (2)。`foundry_wait_sec` 預設 0（短曲線、LTO 折、scan 遇 stop 只寫請求檔不等）；只有 `ctl run --daemon` 等待，且等待迴圈每 5 秒查 `RUN` 與處理各節點 `inbox/` |
| 3 scan 離線去重＋H 集隔離 | **全採**（D-r9-22） | `scan.py` 先在已落盤的 `solutions.jsonl`／LOO 結果上離線重放 gate 變體（0 次 arcbatch），按產出的積木集 `blocks_sha` 分群，只對積木集確實改變的 ≤4 個代表變體跑 3 seed × 4 epoch 短曲線。**`scan.py`、`sieve.py` 不讀 H8／H24**（程式層面：不載入 holdout 題號），判決只用 L16＋P48 的 A／B 兩折（`sha1(task_id+"r09AB")`）：A 折選、B 折折外 0 掉題且節點降 ≥5%（或多解 ≥1）才進 incubating。H24 只在主迴圈 epoch 邊界做熔斷（裁定 5）。`metrics.py` 的 ΔAUC_total 拆報 H8（純盲測）與 H24（熔斷集），LTO-SCF∪ 印 `|U|` |
| 4 route 狀態表＋M2 封漏 | **全採**（D-r9-23、24） | 拔掉 UCB 與 `parent_route` 分潤（D-r9-7 作廢）。`kind:route` 列＝`{"when_stall":"ok\|starve\|saturate","arm","priority":int}`，每 epoch 依 stall 狀態取 priority 最高的 arm；route 表本身是 `scan.py` 的一種搜尋對象（鄰域＝改 priority 或換 arm）。`rt_vsplit` 接 `seed.witness.witness_splits`：對未解 L16 題寫反向子目標進 `_witness.jsonl`，交 `seed-sub` 求解。鑄模仍只由 stop 觸發（不在 route 表）。**M2 改為下表**，取代 02 §9 的 M2 |

**M2 方向對（四中二，D-r9-24 取代 02 §9 M2；本節 commit 即寫死）**

| 項 | 判準 |
|---|---|
| (a) | ≥1 條 incubating 列被樹自己的判準升 live，`evidence.new_solves` 非空，且 **`by ∈ {"sleep","foundry"}`**（手寫的 `agent-r08` halves／nest 不算） |
| (b) | ≥1 條 `gate`／`sieve`／`route` 列被 layer-2 接受，且在 **P48 B 折折外** 0 掉題並節點降 ≥5% 或多解 ≥1 題 |
| (c) | ≥1 個真蠟模（非回放測試）產出 **含 ≥1 個抽象槽位、或跨對非平凡變換**（段在各對的輸入≠輸出、且非常數輸出）的 `comb incubating` 列 |
| (d) | `AUC_L(hammer) > AUC_L(hammer-static)`，或 H8 末 epoch 比 epoch 0 多 ≥1 題。`hammer-static`＝同設定、halves／nest 從 epoch 0 就 live、ops 引擎凍結的對照 |

- 對照樹因此是三條：`dec-g1`（M0 相容）、`hammer-frozen`（引擎凍結、不含 halves／nest＝不學）、`hammer-static`（引擎凍結、halves／nest live＝手寫拆法的天花板）。
- 未採的部分：無。Argon §2 指的「nodes/ 只有 7 個寫死的階段資料夾」本輪只部分處理：新的 `comb`／`decomp` 列在 `ws/hammer/ops/<id>/` 各有一個可 `cat` 的資料夾（`_metainfo.json`＋最近證據），但不各自成為獨立執行的節點（D-r9-25，r10 再拆）。
