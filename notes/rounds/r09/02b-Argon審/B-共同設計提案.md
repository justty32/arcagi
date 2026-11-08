← 入口 [02b-Argon審](../02b-Argon審.md)

## (B) Argon 共同設計提案：補齊最後四塊拼圖

### 1. 四個新機制與類比
* **類比一：淘金震動篩（QuickSpec 代數等價篩 `kind:sieve`——落實意見 2＋6 進化審查）**
  * 睡眠期用 5 張 $4\times 4$ 隨機探針網格對原語庫跑觀測等價，暴力挖出吸收律與對合律（如 `rot90(rot270(x)) ≡ x`、`keep_c(c, keep_c(c,x)) ≡ keep_c(c,x)`），寫入 `ops.jsonl` 的 `kind:sieve`。`enum.py` **展開 AST 時零評估直接剪掉 70%～90% 等價冗餘分支**，保證 0 掉題且直接拉高 LTO-SCF。
* **類比二：斷裂面顯影（Fracture Isolation——解開失蠟死鎖與意見 3 漸進固化）**
  * 鑄模廠改在 `stop` 時**按殘差指紋聚類一次鑄 3 題同型蠟模**，並強制 LLM 輸出 `step(tag, grid)` 檢查點序列（禁寫單體像素迴圈，驗過全部訓練對）。
  * `enum.py` 逐段擬合時，已擬合段直接收編；**擬合失敗的單步轉移 $(S_i \mapsto S_{i+1})$ 自動切為「斷裂面微任務」寫入 `_witness.jsonl`**，讓無菌室繼續縱拆，不必整題一步登天。
* **類比三：商空間投影會師（Quotient Lens——免手寫逆推器）**
  * 廢除手寫 6 個逆推器，改設 3 個通用同態投影：`proj_shape`、`proj_palette`、`proj_fg_mask`（二值前景骨架）。任何算子（含新 `comb`）誕生時自動在探針上標記投影不變性；縱拆改為**先在二值骨架商空間搜出幾何對齊前半 $H$，再固定 $H$ 搜填色後半 $G$**，把幾何×顏色的乘積搜尋拆成相加。
* **類比四：金髮女孩鍛造（Goldilocks Forge）＋延遲分潤路由**
  * 橋接鍛造加「非退化門（輸出熵 $\ge 4$ bits 且跨對非常數）」；對手權重改取**能力邊界方差 $\hat{p}(1-\hat{p}) + |\Delta\hat{p}|$**，自動避開 $p=0$ 無解死題與 $p=1$ 淺題，專攻瀕臨突破區。
  * UCB 為見證與孵化列記 `parent_route`，下游兌現解題時**回溯分潤 50% 位元**給上游路由，根治縱拆餓死。

### 2. 具體資料格式與活樹落地
* **`ops.jsonl` 擴充 `sieve`、自動投影簽名與溯源分潤**：
  ```json
  {"id":"op_12","kind":"sieve|comb|rewrite|decomp|route","status":"live",
   "forbid_ast":"(mirror_h (mirror_h ?x))","canon":"?x",
   "proj_sig":{"keep_shape":true,"keep_fg_mask":true},"parent_route":"rt_sleep"}
  ```
* **`_witness.jsonl` 改記「約束資訊量 `info_bits`」**：只計非 `null` 格相對背景熵縮減量（低於 8 bits 不准入庫防假命中）。
* **雙視圖活樹（落實意見 7）**：五檔維持權威準確，引擎每 pass 原子投影 `ws/hammer/live/{parks,stalls}/_status.json` 與串流 `events.jsonl`，使用者隨時 `cd` 進去跑 `_view.sh` 都看得到即時脈動。

### 3. 量法補丁與五道方向題拍板
* **兩條量法修正**：
  1. **聯集截斷遷移倍率 $\text{LTO-SCF}_{\cup}$**：在聯集 $U = \text{Solved}_{\text{base}} \cup \text{Solved}_{+R_A}$ 上將未解題以超時上限 $B_{\max}$ 代入算幾何平均，且要求 Bootstrap 90% 下界 $\ge 1.3$，保護能解新難題的 `comb`。
  2. **全成本含鑄模曲線＋位元淨利門**：`TotalEvals` 必含「鑄模廠枚舉數＋LLM 折算評估稅（如 $10^5$/call）」，且跨題總省下搜尋位元 $\sum \Delta\log_2(\text{evals})$ 必須大於 `frozen.json#/priors` 新增位元。
* **五道方向題建議**：
  1. **鑄模時機**：只在 `stall=stop` 按殘差聚類一次鑄 **3 題**，並移出常規 UCB 臂。
  2. **入庫證據**：要，但**只認「真題新解」或「雙側 `pipe:[H,G]` 端到端對齊過關」**，單側見證命中絕不放行。
  3. **aos 第二輪**：推遲至 r09 收輪後。
  4. **守門搜尋**：併入 `ops.jsonl` 的 `kind:sieve` 統一實作，不另起爐灶。
  5. **H24 硬底線**：保留，但允許「舊列標 `dormant`＋新列轉 `live`」**成對原子提交**以跨越局部鞍點。
