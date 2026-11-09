# 02b Argon 審（Gemini 4 Argon (High)，agy 1.5.3 --mode plan，23:11～23:14，第 1 次即成功；全文貼入提示：01-簡報＋02-規劃-fable）

## (A) 審查（邏輯漏洞、量法錯誤、門檻不合理、與簡報事實不符、第一塊可行性）

### 一、嚴重度【高】：直接導致驗收失敗、資料洩漏或量尺失效的致命問題

1. **【邏輯漏洞／塊 C & D2】拿 P 池（驗證池）題目造積木再送回影子快道，構成嚴重資料洩漏（Data Leakage）**
   - **問題**：規劃稿塊 C 取「`solutions.jsonl` 裡约 10 L16＋**33 P 題**」的 `near_top` 挖洞補洞產出 comb；塊 D2 對「樹未解的 **L16＋P 題**」跑 `gpusearch` 翻譯成 comb，然後都用 `add-op` 送進樹的影子快道。
   - **對照簡報**：簡報 §2.3 寫明「② gate feed 只用 train 的 LOO＋MDL」、「④ 影子快道：live＋incubating comb 跑 L16＋P」，且 `judge` 依賴影子快道在 P 題上的 `new_solves` 決定升級；§2.2 M1 強調「三池止漏」、§4 強調「驗證真值不餵升降、不餵梯度」。若直接看 P 題的 `near_top` 或 P 題的 DStep 解去定製 comb，再丟回影子快道考 P 題，必然虛增 `new_solves` 騙過 `judge`。**所有候選生成（I0 / D2）必須嚴格限制只看 L16，絕不可碰 P 題。**

2. **【邏輯漏洞 & 驗收不可驗／塊 A】`verdict` 判定規則存在優先序衝突與條件空洞，必違反「21 列全非空」與「gate/route 得 `unmeasured`」兩項驗收**
   - **衝突 1（優先序反置）**：`ops.jsonl` 中 21 列有 `live 11, dormant 10`（含 `gate 1, route 6`）。處於 `status=live` 的 `gate_g1` 與 `route` 列因無解題貢獻，其 `uses=0`、`idle_epochs=8 (>=5)`。若照規劃稿順序先判 `retire-candidate`（`status=live and idle_epochs>=5 and uses=0`），`gate_g1` 與 live `route` 會全部變成 `retire-candidate` 而非 `unmeasured`，直接使驗收條件「`gate_g1` 與 6 條 route 列得到 `unmeasured`」失敗。
   - **衝突 2（大量死角無定義）**：
     - 10 條 `status=dormant` 的算子中，只要有任何一條 `age < 6` 或 `new_solves_n > 0`（或屬於 `decomp`），在規劃稿的 6 條規則裡**沒有任何分支可匹配**，`verdict` 必為 `null`。
     - `status=live` 但 `uses=0, hit_rate_10 < 0.3` 且 `idle_epochs ∈ {0, 1}` 的算子，同樣無分支可匹配。
     - `uses_L/uses_P` 若如規劃稿所言「對不上填 null」，則依賴同一份 `blocks.json` 的 `hit_rate_10` 與 `idle_epochs` 也會一併失效（或全算為 0），導致所有 `comb` 的 `verdict` 失真或變 `null`。

3. **【量法錯誤 & 門檻不合理／塊 B & E】快撥樹砍到 L=25,000 × 4 epochs 會讓造詞與升級迴圈「失明」，且「同設定跑 2 次量 $\sigma$」在決定論引擎下統計失效**
   - **預算門檻過低（失明）**：簡報 §2.3 指出現況 L 預算 100,000 時，`solutions.jsonl` 每題 `nodes` **約 9.7 萬**，8 個 epoch 才長出 3 個積木（R2 造詞乾涸）。把 L 預算砍到 25,000（1/4），原本 2.5 萬～10 萬節點才解出的題全滅，睡眠造詞失去語料來源；且一個 comb 從「epoch $t$ 睡眠孵化 → $t+1$ 影子快道＋judge 升級 → $t+2$ 主跑生效」至少要跨 3 個 epoch，只跑 4 個 epoch 根本走不完學習與淘汰週期。拿這種快撥樹在塊 E 掃 `gate` 參數（如 `retire_after`、`lib_cap`），所有參數變化都會測出 $\Delta\text{AUC\_L} = 0$ 而被誤判為 `dead-param`。
   - **雜訊量法錯誤**：純 CPU 符號枚舉（`llm_calls=0`）若無 race condition，同設定跑 2 次的差必為 $\Delta = 0 \implies \sigma_{\text{auc\_L}} = 0$。一旦 $\sigma = 0$，規劃稿的 `significant = |ΔAUC_L| > 2σ` 就退化成「差 1 題即顯著」；反之若有非決定性，樣本數 $n=2$（自由度 $df=1$）用 $|\Delta|/\sqrt{2}$ 估標準差，95% 信賴區間乘數是 $t_{0.975,1} = 12.71$ 而非 $2$。真正該量的是**不同題目子集（bootstrap）或微小預算擾動下的方差**，而非同設定盲跑兩次。

4. **【概念與門檻錯誤／塊 C】用「格子相符率提升 $\ge 0.10$」抽填洞子樹當 comb，會製造大量刷色垃圾與非法懸空 AST**
   - **門檻不合理**：ARC 題目只要把輸出整張圖塗成背景色（或高頻色），pixel/cell 相符率輕易提升 30%～80%，但語意全錯（簡報 §2.2 M2/M3 特別強調用商空間投影與防誘餌錯解，而非 pixel 匹配）。用 `match_after - match_before >= 0.10` 抽 comb 會把大量常數塗色子樹送進孵化池。
   - **語法漏洞**：在 `near_top` 深度 $\le 3$ 挖洞填出的子樹，若位於 `["lam", 1, ...]` 內部並引用了綁定變數 `["$0"]`，直接把填法子樹抽出來當獨立 comb 會產生**未綁定變數（unbound `$0`）**；若不含 `$in` 則是常數。這與簡報 §3 ★ 點名的 **Stitch**（跨題自頂向下合成帶洞抽象、算 MDL 壓縮效用上界）完全背道而馳。

---

### 二、嚴重度【中】：與簡報事實不符、算力估算失準、設計脫節

5. **【與簡報事實不符／塊 A】`ops.jsonl` 欄位名與 `epochs/0..8/` 結構對不上**
   - **欄位名不符**：簡報 §2.3 明列 `ops.jsonl` 欄位是 `born`，規劃稿塊 A 卻寫從 `ops.jsonl` 原樣讀取 `born_epoch`。
   - **epoch 數量與 `curve.csv` 結構**：簡報 §2.3 寫明目錄為 `epochs/0..8/{curve.csv,...}`（含 epoch 0 共 9 個目錄，且每個目錄下都有一份累積的 `curve.csv`）。規劃稿塊 A 寫「`auc_L = Σ_epochs solved_L`（8 epoch 滿分 128；現況應算出 40）」，若施工者把 `epochs/0..8/` 全部走訪相加會重複計算，若把 epoch 0 與 1..8 共 9 列相加則滿分是 144 而非 128，算出的 `auc_L` 將不會等於 40（簡報 M2(d) 的 40 是 8 個計分 epoch 的和）。

6. **【與簡報事實不符 & 時間估算失準／塊 B & C】忽略 Python 慢道成本與 외부 AST 評估開銷**
   - **塊 B 時間估算**：簡報 §2.1 指出「halves 只有 Python 版，上線後整棵樹慢 8 倍，8 個 epoch 要 5 分鐘（epoch 8 wall 78.8 秒，`stall=stop`、arm=`rt_vsplit`）」。慢是因為觸發了 `rt_vsplit` 的 Python 慢道，而非單純 L 預算大；此外，規劃稿說把 `ws/hammer/` 複製成 `quick/` 並「ops 全部回到空樹起點」，卻沒交待如何重置 `ops/<id>/`（14 個物化目錄）與 `foundry/`，不如直接借簡報 §4 的「空基準 git tag 重置」。
   - **塊 C 時間估算**：43 題 × 8 個洞 × 5,000 候選 ＝ **172 萬次**完整 AST 評估（每題多個 train pairs）。在沒有 C++/GPU 批次評估、純靠 4 個 Python worker 呼叫 `body/exec` 逐一重跑整棵 AST 並算 cell 匹配率的情況下，「10 分鐘內跑完」極度不切實際。

7. **【與簡報事實不符／塊 D1 & D2】誤解 `gpusearch` 的動態字母表與輸出格式，且把「單題完整解」誤當成「通用 comb」**
   - **D1 不必爬 C++ 標頭檔**：簡報 §2.4 已寫明 N2 的字母表是**每題動態生成（59～125 個步驟，含該題專屬單對 colormap）**，基礎 op 種類簡報已全數列出；且 `gpusearch` 的輸出 JSON **已經直接包含「最低成本的 arcagi JSON 程式（colormap 已填入）」**。花 2 小時去 parse `native/gpu/space.hpp` 既多餘又拿不到每題動態參數。
   - **D2 混淆「題目解」與「算子積木」**：`gpusearch` 找到的是某題從輸入到輸出的完整步驟序列（含特定顏色映射）。直接整條翻譯成 seed AST 丟進 `ops.jsonl` 當 comb，是把「單題特化解」塞進算子庫，無法跨題重用；應抽取多題 DStep 解的**共同步驟子序列**（並把顏色/倍率參數化為 λ 洞）才能成為 comb。

8. **【邏輯漏洞／塊 D3】EvoGP 定長張量編碼未處理 seed AST 的 `lam` 綁定與高階型別**
   - 簡報 §2.3 的 seed AST 含高階函數與 λ（如 `["map", ["lam", 1, ...], ["$in"]]`），而 EvoGP（簡報 §3）針對無作用域的單一型別運算樹。若只編碼 `(node_type, node_value, subtree_size)` 而不編碼每個節點的**型別簽章（type signature）與 de Bruijn 索引作用域深度（scope depth）**，GPU 遺傳搜尋做子樹交換時會產出 >95% 的非法程式。

---

### 三、嚴重度【低】：執行細節與環境狀態落差

9. **【與簡報事實不符／塊 C & §5】活樹已停在 epoch 8，光寫 `inbox` 不會自動觸發下一 epoch**
   - 簡報 §2.3 顯示 `frozen.json` 設定 `epochs: 8`，且樹已跑完 `epochs/0..8/` 停在 `stall=stop`。塊 C 寫入 `nodes/grow/inbox/` 後，若不調高 `epochs` 上限並手動觸發單步 epoch，根本不會有「下一 epoch 的 `n_incubating >= 1`」可供驗收。此外，需先從唯讀的 `epoch.py:_apply` 確認 `add-op` 究竟該投遞給哪個節點的 inbox。

---

### 四、第一塊（塊 A：今晚 2 小時、單一 gpt 施工者、純 CPU）可行性與驗收總評

- **做不做得完？** **做得完（約 1～1.5 小時）**。純讀檔、算指標、寫兩個 CLI 腳本與迷你 fixture 測試，對單一 gpt 施工者而言工作量完全在 2 小時內。
- **驗收是否可驗？** **照原稿必卡死，修正 3 處規格後即可 100% 自動驗收**：
  1. 修正欄位名：`ops.jsonl` 讀 `born`（若無則 fallback 為 0）。
  2. 修正 `verdict` 為**嚴格優先序（if-elif-else 階梯）並補齊 `else` 分支**：
     - P1：`status == "incubating"` $\to$ `"incubating"`
     - P2：`kind in {"gate", "route", "sieve"}` 且 `evidence` 三欄全 0 $\to$ `"unmeasured"`
     - P3：`status == "dormant"` $\to$ 若 `age >= 6 and new_solves_n == 0` 為 `"dormant-stale"`，**否則為 `"dormant-active"`**（補齊死角）
     - P4：`status == "live"` $\to$ 若 `uses >= 1 or hit_rate_10 >= 0.3`（或當 `blocks.json` 對不上時改看 `new_solves_n >= 1`）為 `"keep"`；elif `idle_epochs >= 5` 為 `"retire-candidate"`；**否則為 `"watch"`**（涵蓋 `idle_epochs ∈ [0,4]`，消滅死角）。
  3. 明確指定 `think1_meter.py` 讀取 `epochs/8/curve.csv`（最新完成 epoch 的單一曲線檔），並核對 epoch 1..8（或對齊 `hammer/metrics.py`）使 `auc_L` 確切等於簡報的 `40`。

---

## (B) 提案與方向題表態

### 一、我會怎麼改或補（5 條）

1. **補齊塊 A 的判定完備性與 `ledger.jsonl` 證據源**：
   將塊 A 的 `verdict` 改為上述 P1～P4 完備互斥階梯；若 `blocks.json` 與 `ops.jsonl` 的 `id` 對不上，直接同時解析 `ledger.jsonl`（34 行，記有 promote/demote/incubate 事件）與 `ops.jsonl` 的 `evidence.new_solves`，確保 `hit_rate` 與 `idle_epochs` 都有真實數據，不留全 `null` 空殼。
2. **把塊 B 的「快撥樹＋跑 2 次量 $\sigma$」改為「黃金子集快撥（L16 抽 8 題 × L 預算 50k × 6 epochs）＋Bootstrap 雜訊尺」**：
   不砍每題搜尋深度到失明（保留 50k 預算讓需要深搜與造詞的題能解出），改靠「固定抽 L16 的 8 題代表集（含已解與 near_top 題）」來縮短單輪時間；雜訊尺改用 `meter.py` 在題目維度做 **Bootstrap 重抽樣 1,000 次**算出 $\sigma_{\text{auc\_L}}$（0 秒完成、統計嚴謹），加上固定 random/hash seed 驗證決定論。
3. **把塊 C 的「暴力填洞看 pixel match」換成簡報點名的「Stitch 式跨題 AST 壓縮造詞（只看 L16）」**：
   嚴禁碰 P 題！讀取 **L16** 的 `solutions.jsonl`（已解 `program` ＋ 未解但高分的 `near_top`），直接用自頂向下 anti-unification（Stitch 演算法簡化版，純 CPU 幾秒鐘跑完）抽取跨 $\ge 2$ 題重複出現、帶 1～2 個 λ 洞且 `mdl_bits` 淨省 $\ge 5$ bits 的子樹作為 comb 候選，徹底避開 172 萬次 `exec` 與刷色垃圾積木。
4. **把塊 D1/D2 改為「直接解析 `gpusearch` 輸出的 arcagi JSON 程式，抽跨題步驟子序列」**：
   省去 parse `space.hpp` 的虛功；直接在 **L16 未解題**上跑 `gpusearch`（512 MiB），讀取其輸出的 arcagi JSON 程式，將每步 op 分類為「已有 seed 對應」與「缺口原語（如 `crop_bbox`、`fill_enclosed`、`gravity`）」。缺口原語按出現頻率排序產出 `bridge/gaps.jsonl` 交給 r10 補 C++/seed 原語，直接解決簡報 §2.1 第一卡點「32 個原語可表達性不足」。
5. **在塊 D3 的 EvoGP 張量編碼中加入 `ret_type` 與 `scope_depth` 兩個欄位**：
   將每個節點從 3 元組擴為 `(node_type, node_value, subtree_size, ret_type, scope_depth)`，規定 GPU 交叉／變異時只能交換 `ret_type` 相同且 `scope_depth` 相容的子樹，保證 100% 語法與型別合法。

---

### 二、對 5 題方向題的表態

- **Q1 語言橋走哪邊？（推薦：先翻譯 D1/D2，再編碼 D3，不新增 op kind）**
  - **同意**：在不允許改動 `src/arcagi/hammer/` 引擎的前提下，先將 `gpusearch` 解翻譯為 seed AST 並盤點高頻缺口原語，是唯一能立刻借到 GPU 算力且不破壞樹內算子可組合性的做法。
- **Q2 量尺用快撥樹還是全樹？（推薦：快撥樹當日常尺，全樹每日一次當真值）**
  - **同意（但須修正快撥樹參數）**：日常迭代必須壓到 1 分鐘內才能支撐元優化迴圈，但快撥樹必須保留至少 50k 節點預算與 6 個 epochs（改靠縮小題目子集省時間），否則無法觀測造詞與升級效果。
- **Q3 候選積木要不要直接進樹？（推薦：進，但只走 `add-op` incubating、每 epoch $\le 8$ 條）**
  - **同意（但來源限 L16）**：直接走 `incubating` 能免費複用影子快道與 `judge` 的 LOO/MDL 把關而不必重造輪子，惟候選生成嚴禁使用 P 池題目以免洩漏驗證真值。
- **Q4 雜訊尺要花多少？（推薦：同設定跑 2 次，$\sigma$ 用 $|\Delta|/\sqrt{2}$ 估）**
  - **反對**：在無 LLM 的決定論 CPU 枚舉下同設定跑 2 次只會得到 $\Delta=0$（$\sigma=0$），且 $n=2$（$df=1$）在統計上根本不支援 $2\sigma$ 門檻，應改為「跑 2 次驗決定論（要求 $\Delta=0$）＋ 對題目做 Bootstrap 重抽樣估計題間變異 $\sigma$」。
- **Q5 神經排序器何時開始？（推薦：延後到有 $\ge 200$ 支 train_ok 程式之後，本週只做 SyMANTIC 式無神經先驗）**
  - **同意**：目前正樣本極度稀缺且 N2/N3 正在佔用 GPU（顯存限 $\le 2\text{GB}$），先用低成本的資訊論／L0 稀疏特徵選擇（SyMANTIC 式）引導搜尋，完全符合使用者「低廉審查與改進階梯」的元優化方向。
