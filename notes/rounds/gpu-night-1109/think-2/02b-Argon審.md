我是審稿人 Argon。以下直接針對 `02-規劃-fable.md` 對照 `01-簡報.md` 進行審查與提案。

---

## (A) 審查：事實錯誤、邏輯漏洞、必敗驗收、洩漏風險與成本低估

### 一、塊 1（樹⇄JSON 往返與一致判準）

1. **【高｜必敗驗收＋邏輯漏洞】L2 行為一致判準存在「狀態欄剝離悖論」與套套邏輯風險**
   - **問題**：塊 1 將 `ops.jsonl` 的執行期狀態欄（`evidence, ttl, env_hash, blamed_by, tried_env_hashes`）剝離至 `state.json`，方向題 3 明確說「import 回來的 `evidence` 是空的，快撥從乾淨狀態起跑」。但塊 1 驗收卻要求：「對 `tree2/` 跑塊 2 快撥一次……與**原樹快撥**相同（`Δ=0`）」。
     - 若「原樹快撥」是指拿活樹 `ws/hammer/` 直接複製（保留 `ops.jsonl` 內已累積 8 輪的 `ttl`、`evidence`、`tried_env_hashes`）去跑快撥，而 `tree2/` 用 `new_op` 預設空狀態起跑，兩者的算子淘汰（`ttl`）、升級（`evidence`）與跳過集合（`tried_env_hashes`）完全不同，**L2 跑 6 輪的行為必不相同（`Δ ≠ 0`）**。
     - 若「原樹快撥」是指拿塊 1 匯出的 `tree.json` 丟進 `think2_quick.py`，跟 `tree2.json` 丟進 `think2_quick.py` 比——既然 L1 已驗 `tree.json` 與 `tree2.json` 的 `n_diff == 0`，拿兩份一模一樣的 JSON 跑同一個決定論腳本，**只測到了快撥腳本自身的決定論，完全沒測到「原樹目錄 ⇄ import 目錄」的往返行為一致**。
   - **修正**：L2 驗收必須拆成兩步：(1) **保態往返對照**：`orig_tree`（僅清空 `epochs/live/tmp/ledger`，保留 `ops.jsonl` 既有狀態）vs `tree2_with_state`（import 時掛載 `state.json` 回填狀態欄），兩者直接由 `ctl` 跑快撥，驗 `solved_L` 與 `logcost_L` 的 `Δ = 0`；(2) **淨態起跑基準**：確認保態往返 `Δ = 0` 後，才用無 `state.json` 的淨態 `tree.json` 作為塊 4 演化的起點。

2. **【高｜必敗驗收＋行為改變】`ops.jsonl` 強制依 `id` 排序會破壞 L0 與 L2**
   - **問題**：塊 1 規定 `"ops.jsonl": [{…定義欄…}] # 依 id 排序`，且驗收聲稱「L0 不同檔數回報（預期只有 `ops/<id>/` 投影與 key 順序無差，因 hammer 本身就 `sort_keys`）」。這是**事實錯誤**：`formats.py` 的 JSONL `sort_keys=True` 只排「單行 JSON 物件內的 key 順序」，**不排「跨行的算子列順序」**（原樹 `ops.jsonl` 是依誕生／追加順序排列）。強制依 `id` 排序不僅會讓 `ops.jsonl` 的 L0 SHA1 改變，更會改變同優先權算子的載入與枚舉先後順序（tie-breaking），在固定預算上限 `L` 下直接改變搜尋軌跡，導致 L2 `Δ ≠ 0`。
   - **修正**：`tree.json` 內的 `ops.jsonl` 陣列**必須保留原檔列順序**（陣列索引即順序）；只在 `diff.py` 提供 `--ignore-op-order` 選項供跨個體比較。

3. **【中｜規範缺失】`refs.py` 內容定址去重缺乏正規化順序，且與塊 4 的 X2 交配矛盾**
   - **問題**：
     1. 「長度 ≥ 64 bytes 且出現 ≥ 2 次搬到 `defs[sha12]`」未定義巢狀順序。若母子樹 $P$ 含子樹 $C$，且 $P$ 出現 2 次、$C$ 出現 3 次，先抽 $C$ 還是先抽 $P$ 會得到不同的 `defs` 與 `genome_sha`。
     2. 塊 4 的 X2 交配寫道：「整個 `nodes/<k>` 子樹互換（必經 `$ref`，共用自動被記下）」。但在單一棵樹內，`nodes/solve`、`nodes/gate` 等 7 個節點的 `_metainfo.json` 各有不同 `name` 與 `entry`，在單樹內出現次數皆為 1（`< 2`），**根本不會被 `refs.py` 抽進 `defs`**，X2 無從「必經 `$ref`」。
   - **修正**：(1) 規定 `refs.py` 採嚴格 **bottom-up（post-order）** 雜湊：先將子節點替換為 `{"$ref": ...}` 後，再計算父節點的 canonical 字串與 `sha12`；(2) 將「結構性積木槽位」（如 `nodes/<k>`、`ops.jsonl` 內單一 op 的 `payload`）設為**強制進 `defs`**（不論出現幾次），既解決 X2 交配引用問題，又避免把無意義的頂層目錄結構亂抽一通。

4. **【低｜規格遺漏】`ops/<id>/_metainfo.json` 投影重建規則未定義**
   - **問題**：簡報 §2 指出 21 列算子中只有 14 個 `comb／decomp` 有 `ops/<id>/_metainfo.json` 子夾。塊 1 說「import 時由 `ops.jsonl` 重建」，卻沒給篩選條件與欄位映射表，sol 施工必猜錯。
   - **修正**：在 `boundary.py` 寫明投影重建函數：僅當 `op["kind"] in {"comb", "decomp"}` 時建立 `ops/<id>/_metainfo.json`，並從活樹現有 14 個檔案抽出一對一欄位模板寫死。

---

### 二、塊 2（守門程式：『驗證池造積木』與『格子相符率當門檻』）

5. **【高｜洩漏未擋住＋必敗驗收】守門一（偷看考卷）只查靜態欄位、不攔執行期管線，且塊 4 剔除邏輯不成立**
   - **問題**：
     1. **驗收必敗風險**：守門一檢查 `op.payload.src_tasks` 或 `born.src` 與禁池交集，以及 `evidence.new_solves`。但第一，塊 1 已將 `evidence` 剝離出 `tree.json`，對 `tree.json` 跑守門一時根本讀不到 `evidence.new_solves`；第二，簡報 §2 列出 `ops.jsonl` 欄位時，未保證現有 21 列算子皆有 `payload.src_tasks` 欄位。若活樹現有算子未記載題號來源，守門一對活樹將印出 `violations = 0`，導致塊 2「對活樹印 FAIL 且 violations ≥ 1」驗收失敗。
     2. **真洩漏完全沒擋住**：方向題 1 決定「不改 `epoch._main_run`」。這意味著塊 2 與塊 4 跑快撥時，`epoch._main_run` 依然用 `gate_ids = L16 ∪ P` 把 P 池題目餵給 `feed` → `sleep_ops` 抽新 comb，並讓 `judge` 用 P 池的 `new_solves` 把候選算子升級為 `live`！
     3. **事後剔除無效**：方向題 1 稱「用守門一的 `tainted_ops` 把虛高的 `new_solves` 剔除後再算 `eff`」。這是**邏輯錯誤**：`think1_meter.py` 的 `auc_L` 與 `eff` 是從 `epochs/*/curve.csv` 的 `solved_L`（L16 解題數面積）算出來的，不是加總 `ops.jsonl` 的 `new_solves`。一旦某個靠 P 池造出或升級的 `tainted_op` 在第 3 輪幫忙解出了 L16 的題目，該成績已寫入 `curve.csv`，事後標記 `tainted_ops` 根本無法從歷史曲線中扣除其對 L16 的連鎖貢獻！且塊 4 `check` 是在跑快撥**前**對 `tree.json` 跑守門一（此時尚未跑出新算子，必 PASS），跑快撥**中**卻照常偷看 P 池。
   - **修正**：
     1. **物理斷流（不改活樹也能做到）**：`think2_quick.py` 在將基因體 import 到快撥暫存目錄 `/ws/evo/quick/.../tree/` 時，直接將該暫存樹的 `truth/cal`（或 P 池題號清單）在快撥樹設定中清空／替換為空集，或由 `think2_quick.py` 注入環境變數／wrapper 覆寫 `gate_ids = L16`。因為這只改 `/ws/evo/quick/` 下的複製樹，**完全不碰活樹 `ws/hammer/` 既有檔案**，卻能 100% 物理阻斷快撥在 P 池上造積木與升級。
     2. **守門一同時檢查設定與執行期**：除了查 `ops.jsonl`（若讀取 `tree_root` 則連同 `epochs/*/blocks.json`、`nodes/*/_witness.jsonl` 一起查題號），還必須檢查樹的執行設定是否將 `P / H8 / H24` 納入 `gate` 或 `foundry` 輸入池；只要設定允許流入即印 FAIL。

6. **【中｜作弊逃逸風險】守門二（相符率不准當門檻）僅靠名稱 grep 與 `<file>:<func>` 粒度，極易被繞過**
   - **問題**：
     1. **同函式夾帶**：`thresholds.json` 以 `<file>:<func>` 登錄。若 `solvers/search.py:near_miss` 已登錄為 `rank/ok`，後續在同一個函式內新增一行 `if pixel_acc > 0.85: accept()`，因 `<file>:<func>` 已在白名單內，守門二會直接放行。
     2. **別名與間接門檻**：不寫 `pixel_acc` 而寫 `(grid == target).mean()` 或讀 `_gradients.jsonl` 的 `score`（簡報 §2 指出該 `score` 正是由 `pixel_acc` 產生）來決定淘汰/晉升，grep 完全抓不到。
   - **修正**：
     1. `thresholds.json` 必須綁定**精確行號雜湊（`line_sha1`）與出現次數（`count`）**，且用 Python `ast` 模組掃描：凡是相符率變數出現在 `ast.Compare`（`>`, `>=`, `<`, `<=`, `==`）或 `if / while` 條件式中，預設一律判 `purpose=threshold (FAIL)`，不准僅以 `<file>:<func>` 放行。
     2. 將 `_gradients.jsonl` 的讀取端也納入守門二追蹤範圍。

---

### 三、塊 3（開放 JSON 成本帳與分層分功勞）

7. **【高｜必敗驗收＋事實錯誤】`price(cost, rates)` 與 `think1_meter` 的 `cost` 量綱完全不同，不可能相差 ≤ 1%**
   - **問題**：塊 3 設定 `rates.json` 為 `{"llm.tokens": 0.001, "wall_s": 0.1}`（借自簡報 §3 的 aos 節點池定稿），卻在驗收要求：「`price(cost, rates)` 對 epoch 總和與 `think1_meter` 的 `cost` 相差 ≤ 1%（舊欄換算到新帳不掉數）」。
     - 查簡報 §2：hammer 現有的成本欄是 `evals_body, evals_shadow, evals_meta, evals_foundry, llm_calls, wall_s, logcost_L, lib_bits`（外加 `evals.llm_tax`），**根本沒有 `llm.tokens` 欄位**！
     - 更重要的是，`think1_meter.py` 算的 `cost` 是 hammer 既有評估成本（基於 `evals_*` 次數與 `llm_tax`），而 `0.001 * tokens + 0.1 * wall_s` 是以秒與 token 計價的「錢」。兩者物理單位、數值規模差了數個數量級，驗收**必敗**。
   - **修正**：區分兩組 rate profile：(1) `rates_legacy.json`：將 `evals.body`, `evals.shadow`, `evals.meta`, `evals.foundry`, `evals.llm_tax` 設為 `think1_meter.py` 對應權重（通常為 1.0），`wall_s` 設 0，用這組驗證「舊欄換算到新帳與 `think1_meter` 相差 ≤ 1%（實應為 0%）」；(2) `rates_aos.json`：設定 `wall_s: 0.1, llm.calls: <折算值>, evals.body: 1e-4` 作為新統一貨幣帳。

8. **【高｜數學漏洞＋必敗驗收】分功勞（`credit.jsonl`）違反階層守恆、誤用累積欄位、且 100% 覆蓋率驗收必敗**
   - **問題**：
     1. **階層守恆公式錯誤**：塊 3 說「沿『樹→節點→op／子樹』分下去」，但公式卻寫「留 20% 給頂層；80% 先按 `evidence.new_solves` 歸 op，無歸屬部分按 `weight` 分給節點；守恆：`Σ(to≠root) + root = 頂層 amount`」。若把節點（中層）與 op（底層）混在同一個 `Σ(to≠root)` 裡：一旦某輪有 `new_solves`，80% 全直奔底層 op，中層 `nodes/*` 分到 0，導致塊 4 `fit.json` 的 `"credit_by_subtree": {"nodes/solve": ...}` 完全拿不到功勞！若先經過 `nodes/*` 再轉發給 `ops/*`，則所有 `to≠root` 的列加總會重複計算兩層（變成 160%）。
     2. **誤把終態當單輪差值**：`ops.jsonl` 的 `evidence.new_solves` 是跑完 8 輪後的累計值，不是第 $t$ 輪的單輪新增解題。離線算 epochs 1..8 時，不能直接讀 `ops.jsonl` 的 `evidence`。
     3. **負 `d_eff` 常態化與覆蓋率必敗**：當某輪未解出新題但消耗了成本，`eff = auc_L / cost` 的單輪差 `d_eff` 為負；若該輪無 `new_solves` 也無 `blamed_by`，那些既沒新解題也沒被 blame 的 live op 根本分不到任何一列 credit，**「live op 覆蓋率 100%」驗收必敗**。
   - **修正**：
     1. 改為**嚴格兩層流守恆（Kirchhoff 定律）**：
        - 第一層（`root → nodes/*`）：`root` 留 20%，80% 依各節點當輪活躍度／權重分給 7 個 `nodes/*`（守恆式 1：`root_keep + Σ credit(root→node) = d_amount`）。
        - 第二層（`node → ops/*`）：每個持有算子的節點（如 `solve/route/gate`）自留 20%，將其餘 80% 分給其轄下所有 `live` 算子——有當輪新增解題（比對 `epochs/t/solutions.jsonl` 與 `t-1`）者拿大頭（如 70%），其餘所有 `live` 算子平分或依權重分底薪／房租（10%）。這同時保證**每一層嚴格守恆**、`nodes/solve` 有真實累計功勞、且**所有 live op 覆蓋率必然 100%**。

---

### 四、塊 2 & 塊 4（整棵樹當遺傳搜尋個體：適應度可信度與負擔、運算子設計）

9. **【高｜邏輯衝突】塊 2 快撥強制覆寫 `frozen.budgets`，直接廢掉塊 4 的 M1 突變**
   - **問題**：塊 4 的突變 M1 主打抖動 `frozen.budgets.*`（連 `parents.json` 範例都是改 `/tree/frozen.json/budgets/L`）。但塊 2 的 `think2_quick.py` 卻規定：「import 基因體 → **覆寫 `frozen.budgets`／`taskset` 子集** → 用 `ctl` 跑 N epoch」。基因體剛突變好的 `budgets.L`，進快撥評估時立刻被 `--L 50000` 覆寫洗掉，M1 突變淪為空轉（No-op）！反之，若不覆寫總預算而讓子代把 `L` 突變放大，子代靠多花時間多解題且會撐爆快撥 wall time。
   - **修正**：快撥必須鎖定**總外框預算**（如總評估上限 `L_total = 50000` 不可由個體突變），而 M1 只准突變**預算在各階段／各節點間的內部配比**（例如 `gate` vs `body` vs `shadow` 的比例、`frozen.judge.*` 門檻、算子 `priority`）。

10. **【高｜演化退化】單親起點（方向題 5）＋ 1 代（`--gens 1`）下，M4 與 X1~X3 運算子幾乎全數退化為無效操作**
    - **問題**：方向題 5 決定只用 hammer 單親起點，塊 4 只跑 `--pop 8 --gens 1`：
      - **X1 / X2 / X3（交配）**：在單親起點的第 1 代，母本只有 hammer 自己（頂多先做一次突變再交配，但 `think2_ga.py` 未說明是否先突變再交配）。即便先突變再交配，M1~M4 都沒碰 `nodes/<k>`，所以所有個體的 `nodes/<k>` 完全相同，**X2（`nodes/<k>` 互換）100% 產生與母代無異的複製人**！
      - **M4（從族群 comb 庫挑 `sig` 相同者替換 `body`）**：單親 hammer 裡僅有的 14 個 comb/decomp 原本就共存於同一棵樹中；把算子 A 的 body 換成同棵樹已有的算子 B 的 body，等於刪掉 A 並複製一個冗餘的 B，只會降低能力。
      - **M2（live↔dormant）、M3（刪算子）**：在只有少數有效算子的樹上隨機刪除或休眠算子，期望適應度變化必為負。
    - **修正**：(1) 若堅持單親起點，第 1 代應先由 M1/M2/M5 產生 $\mu$ 個突變體，再對不同突變體做 X1/X3 合成（將管線定為 `Parent → Mutate → Crossover → Check`）；(2) M4 的 comb 庫不應只從「當前單親」抽，應允許從 `ws/hammer/epochs/0..8/` 歷史曾出現過但未留存的候選算子，或 `aos/seedlib` 的算子清單（只抽單純 op JSON，不需為整棵 seedlib 寫 `boundary_profile`）作為外源基因庫。

11. **【中｜成本低估＋統計失靈】快撥 `wall ≤ 180 s` 嚴重低估，且 16 題上的 `sigma_auc_L` 無法分辨單題進展**
    - **問題**：
      1. **時間低估**：簡報 §5 實測活樹 1 個 epoch 是 CPU 枚舉 5 分鐘（300 秒）。塊 2 卻假設跑 6 個 epochs 只要 `≤ 180 s`（即每 epoch ≤ 30 秒，加速 10 倍），理由是 `--subset L16`——但活樹訓練集本來就是 `L16`！就算砍掉 P 池與減少 `L`，若 `foundry / sleep_ops` 在每個 epoch 尾端仍觸發（甚至含 `llm_calls`），6 個 epochs 極可能落在 6～12 分鐘，塊 2（跑 4 次）＋塊 4（跑 8～9 次）總耗時會突破 1.5～2 小時。
      2. **離散雜訊失靈**：`L16` 只有 16 題。對 16 題做 bootstrap 1000 次，只要 1 題有差異，產生的題目抽樣標準差 $\sigma_{\text{boot}}$ 本身就約等於「1 題的 AUC 貢獻」。當子代比母代多解 1 題時，變化量 $\Delta \approx 1\sigma$，在塊 4 很容易被判為 `significant: false`；但要求單次隨機參數抖動在 16 題上同時多解 $\ge 2$ 題又不切實際。
    - **修正**：
      1. 快撥時預設關閉 `foundry` 的外部 LLM 呼叫（`evals_foundry = 0` / mock），純測既有與 `sleep_ops` 本地算子枚舉；若 `L=50k / 6 epochs` 仍 `> 180 s`，允許 `L=25k / 4 epochs` 為塊 4 標準快撥。
      2. **改用成對差值 Bootstrap（Paired Bootstrap on $\Delta$）**：不要對單一跑次的 16 題算絕對 $\sigma_{\text{auc\_L}}$（這量到的是「題目之間的難易度差異」，而非「兩棵樹的差異雜訊」！）——兩棵樹跑的是**同一組 L16 題目**，應該對每一題 $i \in \{1..16\}$ 計算兩棵樹的差值 $d_i = \text{score}_B(i) - \text{score}_A(i)$，再對 $\{d_i\}_{i=1}^{16}$ 做 bootstrap！這能消除跨題難度方差，讓 $\sigma(\Delta)$ 縮小數倍，真正檢出單題或加速進展。

---

### 五、塊 4 & 塊 5 其他工程瑕疵

12. **【低｜必敗指令】塊 4 的 git 污染檢查指令寫錯目標倉庫**
    - **問題**：塊 4 寫「驗收改為 `git -C arcagi status --porcelain | grep evo` 為空」。但產物路徑是 `/home/lorkhan/code/playground-arc1/ws/evo/`，根本不在 `arcagi` 目錄下，`grep evo` 永遠為空（假陽性通過）；且若工作目錄不在 `arcagi` 父目錄，`git -C arcagi` 會直接報路徑錯誤。
    - **修正**：改為檢查 `git -C <arcagi_repo_abs_path> status --porcelain` 在跑完前後的 diff 為空（確保沒有任何中間檔誤寫入 repo），並確認 `/home/lorkhan/code/playground-arc1/ws/evo/` 存在且非空。

13. **【低｜必敗驗收】塊 5 Janet 驗收 `janet -e '(import ./tree)'` 會因未定義符號而報錯**
    - **問題**：塊 5 格式為 `(tree "hammer" (file "_metainfo.json" {…}) …)`。在 Janet 中直接 `import` 該檔會將其當作程式碼求值（evaluate），因為沒有定義 `tree`、`file`、`dir`、`ref` 函數或巨集，`janet -e '(import ./tree)'` 必拋 `compile error: unknown symbol tree`。
    - **修正**：要嘛在生成的 `tree.janet` 檔頭附上極簡建構巨集／函數（如 `(defn tree [name & body] {:kind :tree :name name :body body})` 等），要嘛驗收改用 `(parse (slurp "tree.janet"))` 驗語法結構。附建構函數更符合「程式即資料」精神。

---

## (B) 提案：更好或補充的做法（5 條）

### 1. 用「成對題目差值 Bootstrap（Paired Delta Bootstrap）」取代單跑絕對 $\sigma$
- **做法**：在 `think2_noise.py` 與塊 4 顯著性檢定中，將每題 $i \in \text{L16}$ 的解題速度指標（如 $s_i = \max(0, 1 - \log\text{cost}_i / \log L)$ 或單題是否解出之 epoch 折現分）拆到單題粒度，對子代 $B$ 與母代 $A$ 計算成對向量 $\Delta_i = s_B(i) - s_A(i)$，再對 $\Delta_i$ 重抽樣 1000 次算信賴區間。
- **理由**：原方案對單次快撥做題目 bootstrap，量到的是「L16 內部哪些題好解、哪些題難解」的題間方差（必然很大），而非比較兩棵樹時的隨機誤差。成對差值消除了題目基準難度，能讓 `auc_L` 與 `auc_speed_L` 的檢定力提升一個數量級，直接解決「16 題太小看不出顯著改善」的痛點。
- **代價**：`quick.json` 需額外輸出一欄 `per_task: {<task_id>: {"solved_epoch": ..., "cost": ...}}`（約多 20 行 Python 程式碼）。

### 2. 快撥時透過「沙盒覆寫 `truth` 分池」物理根除 P 池洩漏，無需改動 hammer 原始碼
- **做法**：在 `think2_quick.py` 將 `tree.json` import 成快撥目錄 `ws/evo/quick/<id>/tree/` 後、執行 `ctl` 之前，由 `think2_quick.py` 直接把快撥樹目錄內的 P 池題目清單移出 `gate` 可見範圍（例如將快撥副本的練習池設為空或指向 L16 的子集），同時保持活樹 `ws/hammer/` 原封不動。
- **理由**：這能一舉兩得——既嚴格遵守「不改活樹既有檔、不改 hammer 原始碼」的限制，又能在塊 2 與塊 4 的快撥評估中**真正做到物理零洩漏**，不必依賴方向題 1 那個在邏輯上行不通的「事後用 `tainted_ops` 扣減 `eff`」。
- **代價**：快撥跑出的 `new_solves` 總數會比活樹少（因為少了 P 池題目充數），`judge` 升級門檻若寫死題數可能需在快撥配置中按比例調降（例如 `min_new_solves` 由 2 降為 1）。

### 3. 在塊 4 加入「引導式突變（Health-Guided Mutation）」，把塊 3 與塊 4 真正串起來
- **做法**：塊 3 既然已經產出了 `credit.jsonl` 與 `health.json`（標出哪些節點負分、哪些 op 是 `verdict=retire` 或 `idle_epochs` 過高），塊 4 的突變就不該是盲目均勻亂抽！讓 `mutate.py` 讀取母代的 `health.json` 與 `credit.jsonl`：
  - M2（休眠）／M3（刪除）／M4（換體）以 **80% 機率優先挑選 `verdict == "retire"` 或 `credit < 0` 的算子**下刀；
  - 保護 `credit > 0` 且有 `new_solves` 的核心算子不被 M2/M3 誤殺。
- **理由**：這直接落實了使用者方向 §1.4「上層把改進責任分給節點，分到責任的節點改進自己」。盲目隨機刪改一個只有 21 個算子的樹，8 個子代有 7 個會變笨；用塊 3 的歸責與體檢導引塊 4 的突變，能在極小族群（pop=8）下大幅提高找到正向子代的機率。
- **代價**：塊 4 執行前需先對母代跑一次塊 3（耗時 `< 1` 秒），`mutate.py` 增加約 30 行權重抽樣邏輯。

### 4. 外源算子種子庫（Seed Pool Injection）解決單親交配退化
- **做法**：不為 `aos/seedlib` 整棵樹寫 `boundary_profile`，而是寫一個極輕量的抽取器，把活樹 `ws/hammer/epochs/0..8/` 歷史曾產出過的候選算子，加上既有 `seedlib` 裡合規的單筆 comb/gate 算子，匯集成一個靜態 `ws/evo/op_bank.jsonl`。供塊 4 的 M4（換體）與新增的 **M6（插入一個外源算子）** 抽用。
- **理由**：徹底解決方向題 5「單親 hammer 起點下 M4 與交配 X1/X2 空轉退化」的問題，同時避開「為多棵異質樹寫 `boundary_profile`」的高昂工時。
- **代價**：需多寫約 40 行腳本從 `epochs/0..8/` 與既有庫收集算子並過一次 `formats.check_op`（約 0.5 小時工時）。

### 5. 將塊 2 的 F0 靜態檢查擴充為「行為等價去重（Semantic Dedup before Quick-Run）」
- **做法**：在塊 4 跑昂貴的 F1 快撥之前，除了比對 `genome_sha` 查 `fit_cache.jsonl` 外，另外計算一個 **`active_genome_sha`**：剔除所有 `status == "dormant"` 的算子、剔除不影響執行期的詮釋欄位（`born`, `by`, `mdl_bits`）、並對未改變算子排序與有效預算參數的個體計算活性雜湊。若子代的 `active_genome_sha` 與母代或兄弟相同，直接繼承 F1 分數，不重跑快撥。
- **理由**：許多突變（例如改到已經 dormant 的算子參數、或交配了相同的子樹 X2）會產生不同的 `genome_sha`，但執行行為 100% 相同。用 `active_genome_sha` 攔截可省下 20%～40% 的無效快撥 CPU 時間。
- **代價**：在 `check.py` 或 `refs.py` 多寫一個約 15 行的正規化過濾函數。
