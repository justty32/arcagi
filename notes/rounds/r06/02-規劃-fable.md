第六輪規劃：規劃者（fable）讀完 01 簡報後的定案，回答 §7 五問；隊長據此寫 03 設計、派線。

← [01 簡報](01-簡報.md)｜下一步：隊長寫 03 設計、派線施工。

## 1. 結論先

- 做 **E1+E2 合一線（A）、E3b+E4（B）、E5（C）**。
- 理由：A 是使用者主軸本體（優化產生積木的過程、遞迴嵌套）；S5 證據說根因在評分料太少，E2 的合成集軟接就是 E1 的分數定義，不該拆兩線。B 是本輪唯一分數有把握的案（r04 已量 42），E4 省 ×3 耗時讓那一次全量 evaluation 跑得完。C 便宜、路徑不重疊，把 S2 的 34 顆候選接進 node-pool，順手做出 A/C 都要的「影子跑」工具。
- 不做：E3a（主線重做 S1 寬樹＝與支線搶同一塊表達力）、E6（要等 meta 層 1 穩定）、新原語族（S1 領地）。
- 預期：evaluation 42→42～45；本輪真正產出是**量法**（空基準、雜訊、meta 帳、影子門檻）第一次落地。

## 2. 分線

路徑名由隊長 03 設計對照實際檔名；原則：**A 只碰產生器/元優化/帳，B 只碰求解入口/評測/文件，C 只新增檔**。線內只跑 ≤50 題子集；全量 training、evaluation 各一次由隊長合併後跑（§3）。

### 線 A：元優化正式做＋合成集軟接（E1+E2）
- 目標：`_gen/_meta` 從空基準重跑、調 `gen_extract`＋`gen_formula`、分數防背答案、meta 帳落地。
- 可寫：產生器三檔（gen_formula/gen_extract/gen_predicates）、`_gen/_meta` 所在檔、帳/pool 模組、`aos/blocks/`（只經產生器寫）、`aos/pool/`、新 `aos/meta/`、對應 tests。
- 步驟：(1) `git diff --stat aos/blocks aos/pool` 須為空，否則先 commit；加 `--blocks-root` 指暫存目錄跑，HEAD 樹不動。(2) 三台產生器評分加合成集多數門檻（§3）；有收入者不退休。(3) 空基準 1 次＋雜訊基準 2 次得 σ。(4) meta 層 1：≤8 設定、先 extract 後 formula；設定挑選用 training 奇數 200 題、驗證偶數 200 題。(5) 每跑一次記 meta 帳。(6) 層 2（調 meta 自身變異範圍）為延伸，不夠時延 r07。
- 驗收：σ 報出；最佳設定主分 > 基準 + max(2σ, 1)；偶數 200 題不低於基準；新上線 pred 的合成集「多數不過」率 50%→≤30%（extract ≤30%、formula ≤10%）；`formula_0832d6a3`、`extract_f23ec080` 仍 live；meta 帳 ≥11 筆；50 題子集 training 解題數不降。

### 線 B：入口＝native 混合＋改寫搜尋門控（E3b+E4）
- 目標：主線正式定求解入口＝`arcagi eval --external native/bin/solve`（Python 先跑、無解 C++ 補、Python 重驗）；改寫搜尋只對前景 IoU 高的題開。
- 可寫：eval CLI/外部入口模組、改寫搜尋開關與門控所在檔、`scripts/eval_*`、`notes/支線.md`（S1 邊界節）、`notes/rounds/r06/`、對應 tests。不碰 `native/`、`dsl/ext/`。
- 步驟：(1) 50 題子集比 HEAD 主線 vs 混合入口。(2) 量 r05 training 上改寫搜尋有貢獻的 1～2 題的前景 IoU，門檻定在保住它們（預設約 ≥0.5）；預設開門控、ledger 記「被門控略過」。(3) trace 加歸因欄：每題由 python/native 哪方解、用了哪些積木。(4) 寫合併後全量的跑法腳本與門檻表給隊長。(5) 更新支線.md。
- 驗收：子集混合 ≥ 主線；改寫搜尋耗時降 ≥50% 且子集解題數 ±0；trace 歸因欄齊；支線.md 有 S1 邊界；合併後全量達 §3 門檻。

### 線 C：S2 候選進帳＋影子跑工具（E5）
- 目標：把 `aos/llm/candidates/*/_rule.json`（唯讀）當「LLM 產生器」產出，影子跑過門檻才進 `aos/blocks/`，標 `source: llm`、`origin: <hash>`。
- 可寫：新 `src/arcagi/shadow/`（輸入一包積木 json，輸出每顆過/不過與原因，不動 live）、新 `gen_llm.py`（只讀候選、轉積木格式）、`aos/blocks/llm_*`（只新增）、`reports/llm-intake-r06/`、tests。不碰 `aos/llm/`、`src/arcagi/llm/`、預算分配（`generator_budget` 接入延 r07）。
- 步驟：(1) 影子工具＋預核：用舊資料算 245 顆現有積木能過幾顆，寫報告。(2) 34 顆候選轉積木，影子跑 training 支持題＋合成集。(3) 過的入庫，不過的列原因到報告。(4) 50 題子集確認不退。
- 驗收：預核數字報出；34 顆每顆有判定與原因；進帳 ≥1 顆且子集 training 不降、過 train 答錯不增；工具對 A 線產出可直接重用（同輸入格式）。

## 3. 整體門檻與量法

- **本輪門檻（合併後各一次全量）**：evaluation ≥42（混合入口）、同大小 ≥16、過 train 答錯 eval ≤14／train ≤26、training ≥95、全量耗時 ≤ r05 主線。未達列原因，量法不回滾。
- **跑序**：三線合併 → 全量 training 一次（含 E4 門控、新積木）→ 過 train 檻才跑全量 evaluation 一次。開跑前 `pgrep -af "arcagi eval"`、`nice -n 19`、`--workers ≤6`。
- **空基準**：`aos/blocks/` 只留 `source` 非產生器者（原語 ~30＋手寫巨集 7 含 `m_sub_*`），刪全部 `extract_*/formula_*/pred_*`；`aos/pool/` 歸 epoch 0；在暫存 blocks-root 跑；跑前 diff 為空並記 commit hash。
- **雜訊**：空基準跑 3 次（原 seed、換 seed、題序打亂），σ＝三次主分標準差；σ=0 則門檻取 +1 題。
- **元優化分數**：主分＝Σ training 題 [被解 ∧ 解程式含本產生器積木 ∧ 該積木在此題合成集 8 份小樣本過 ≥50%] − 候選數/1000；副分＝帳 `generator_cut` 回流（只記不決策）。背答案積木（多數不過）不計主分、有收入不退休、新產不上線。設定挑選奇數 200 題、驗證偶數 200 題。
- **meta 帳**（`aos/meta/ledger.jsonl`，只記不分紅）：run_id、time、layer、target_gen、setting、seed、blocks_root_hash、base_commit、cost_wall_s、cost_cpu_s、n_tasks、n_candidates、score_main、score_div、baseline_ref、delta、sigma、accepted、note。回本＝Σcost 對 Σaccepted delta，r07 看。
- **影子上線門檻**（C 工具，A/C 共用）：(a) training 支持 ≥1 題出現在解程式；(b) 支持題中 ≥2/3 合成集多數過（pred 要全部）；(c) 批次上線後子集過 train 答錯不增；(d) 非 live 積木的 covered 重複。開跑前先預核。

## 4. 與支線的邊界

- **S1**：入口由主線（B）決定＝native 混合；S1 長原語（`native/`＋`dsl/ext/` Python 版），不寫 `aos/blocks/`；`native/bin/solve {input} {output} {trace}` 契約與 trace 格式由 B 定、S1 不破壞；Python 重驗不可省；S1 新原語入庫走 C 的影子工具、主線收（r07）。
- **S2**：候選唯讀；C 收，過的進 `aos/blocks/llm_*`；不過的原因在 `reports/llm-intake-r06/`，S2 自讀自改；主線不改 `aos/llm/`。
- **S5**：合成集唯讀（`--data-root data_synth`）；主線不改 `scripts/synth_*`；要更多樣本（如每題 48）向 S5 提；S5 軟接建議即 §3 分數。

## 5. 風險與延到 r07

- 風險：三線都想跑全量 → 線內只准子集，全量由隊長各跑一次；meta ≤8 設定 1 小時跑不完 → 先 extract、用子集；合成集門檻太嚴讓 live 積木大減 → 有收入豁免、先預核；混合入口 HEAD 未重量可能 <42 → 列原因、不回退 S1；三線合併後歸因靠 trace 欄，B 若沒做完則無法歸因。
- 延 r07：meta 層 2、gen_predicates 進 meta、gen_llm 接 `generator_budget` 分紅、E6 子樹即積木、E3a、S1 原語經影子工具入庫、`arcagi compare --labels`（等 S4）、data_synth 改為主評分、CUDA。
