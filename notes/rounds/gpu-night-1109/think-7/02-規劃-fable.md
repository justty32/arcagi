# think-7 02 規劃（fable）：讓 e1 之後還有新資訊

← [01 簡報](01-簡報.md)｜[02b Argon](02b-Argon審.md)｜[代定清單](代定清單.md)

## 0. ELI5 結論

推薦 **方案 A：H1「judge 對齊量尺」＋ H5 的 m 旋鈕**。現在 judge 只給「解出新題」的積木發通行證，但量尺 168.7 bit 的增益幾乎全是「舊題變快」（17 題 ntf 變小，只 1 題新解）。改成「讓已解題總共省 ≥ 2 bit 也放行」，被判死刑的 reverse／transpose 類積木（saving 6–10）就能在 e0 末升 live、從 e1 起吃滿 ×4，而且 e1 feed 變了、e2 還能再長一批——這就是「e1 之後的新資訊」。預期 **+15～+50 bit**（親代 168.7 的 9–30%），量尺上看得到的形態是 lib_size(e4) 從 1 → ≥3、e2..e4 的 b 還在漲。要使用者裁：(1) 准不准改 hammer 原始碼（`judge.py` 一行＋`epoch.py` 影子段算一個新 evidence 欄位，frozen.judge 新欄位預設關、親代位元不變）；(2) GA 線**暫停**，不是殺——等 A 落地再把 genome 換成學習規則旋鈕。方案 B（H3 分桶先驗）次之、方案 C（H4 預算重配）因 B_REF 截斷直接增益為 0，只當後備。

## 1. 共同前提

- 量尺不動：64 題、L=40000、E=4、`meter_stats.compare`（|Δ|≥2、奇偶半同號、|z|≥2）＋逐題成對符號檢定＋Holm（跨臂）。健全門：raw verify、clone=親代（位元相同）、|no-learn-all gain|<1。
- 新增一條**算力門**：Σ(evals_body＋evals_shadow) 變體 ≤ 親代×1.05，超過判無效（不是紅、是作廢重跑）。
- 門檻只在 training 64 題選；H8/H24 只審計寫進報告，不進判定。
- 判準先 commit（prereg_commit，沿 `reports/think4-1110/f/g1.json` 格式）再跑。
- 符號檢定硬表（單側 α=0.05，n＝有變動題數，平手剔除）：n=15→k≥12；n=18→k≥13；n=20→k≥15；n=25→k≥18。跨臂 Holm：最小 p 要 ≤ 0.05/臂數。
- 假綠／假紅：變動題只有 ~17–20 題，符號檢定功效低。**紅**必須「顯著負」；「不顯著」一律記「無結論」而非紅。**綠**除符號檢定外還要 compare 的奇偶半同號（已內建）。
- 副量尺「後段斜率」S = Σ_題 Σ_{e=2..4}(b_e − b_1)。親代 S≈0（logcost_L 870.3→872.1，實為微負）。這是本輪最重要的形態指標：有 S>0 才證明「e1 之後有新資訊」，不是只把 e1 那一跳放大。

## 2. 方案

### 方案 A（主推）：H1 speed-only 升級 ＋ H5 m=6

**改什麼（改 hammer 原始碼）**
- `epoch.py` ④影子段：對每條 incubating comb 的批次影子結果算 `speed_bits = Σ_{t∈L 共同已解} log2(ntf_live[t] / ntf_shadow[t])`（有號，含被拖慢的負項），寫進 `o["evidence"]["speed_bits"]`。影子已經在跑、不加算力。
- `judge.py:42`：`hit = new_solves or witness_hits>0 or speed_bits >= frozen.judge.speed_min_bits`。`frozen.json` 新欄位 `judge.speed_min_bits`，**預設 None=關**，親代 run 位元不變（clone 門可驗）。
- ops `gate_g1.m` 3→6（不改碼；H5 旋鈕）：每輪多產候選，給新 feed 多一點料。
- 注意：影子是整批 incubating 一起跑，speed_bits 是批次量；逐條歸因沒有。先接受批次升級（已有 no_crowd、lib_cap、H24 fuse、ablate 兜底）。

**為什麼 e1 之後還有新資訊**：e0 末 3–5 條 comb 升 live → e1 的 ntf／feed 程式本身改寫（用 comb 的更短程式進 feed）→ uses 分布變、anti-unification 的輸入變 → e1 sleep 能長出二階 comb（comb 套 comb），e2 再升。迴路不再在 e1 到達不動點。

**預期增益與推理**：think-4 05 逐題表，transpose／reverse 類題 ntf 可再降 ×2–10（1–3.3 bit/題）；目前 dormant 的 saving 6–10 的 3–4 條 comb 覆蓋約 6–10 題；e1 起吃 ×4 → 粗估 +25～+60；扣掉 lib 變大讓純 primitive 題小輸（think-4 05：11 題 0.2–14.7 bit，但有號 speed_bits 會把這筆算進門檻）→ 淨 **+15～+50**。

**預先登記判準**
- 臂：A2（speed_min=2）、A4（speed_min=4）、A2m6（speed_min=2＋m=6）。Holm 跨 3 臂。親代 t4f 已有、不重跑。
- 主判準（綠）：Δgain_bits ≥ +15 **且** compare.significant **且** 符號檢定 k_pos 達上表（Holm 後）。
- 副判準（至少兩項）：S ≥ +5；lib_size(e4) ≥ 3；|no-learn-all| < 1；new_solves 不減。
- 算力門：Σ(body＋shadow) ≤ 親代×1.05。
- 失敗判定：**紅**＝Δ ≤ −2 且符號檢定顯著負（H1 讓 lib 擠壓 primitive 題）。**無結論**＝其餘；若三臂 lib_size(e4) 仍 =1 → 「門檻太高或 no_crowd 卡死」，看 shadow 的 speed_bits 分布再定一次門檻（只准再調一次、仍只看 training）。

### 方案 B：H3 uses 按題型分桶（條件先驗）

**改什麼（改 hammer 原始碼，較大）**：`epoch.py:317-321` 的 `state.uses` 變 `uses[bucket][op]`，bucket 由現有 features 算（輸出尺寸＝/＞/＜輸入 三桶起步）；`compress.order_from_uses` 接桶；`body.py:227` 已按 order 分批，改成每題取自身桶的 order。無 bucket 計數時回退全域 uses（保證 e0、無資料桶與親代一致）。

**為什麼有新資訊**：不是時間上的新資訊，而是把 e1 已有的資訊**不再互相稀釋**——同尺寸題不用被放大題的 transpose／tile 先驗壓在後面。think-4 05 那 11 題（0.2–14.7 bit 反輸）是直接目標。

**預期**：回收那 11 題的一半 → +10～+30 bit；S 仍 ≈0（它不製造後段斜率）。若與 A 疊加，A 長出的 comb 進桶後效果可能更乾淨，但那是第二輪的事。

**判準**：主判準 Δ ≥ +8 且 compare.significant 且符號檢定過；副：那 11 題中 ≥6 題 Δ_題>0；lib_size 與親代相同（它不該動 comb）；算力門同上。紅＝Δ≤−2 顯著。風險：桶太細 → 每桶樣本 <5 題、先驗退化成噪音；先登記「桶內 feed <3 題回退全域」。

### 方案 C（後備）：H4 預算重配

**改什麼**：`epoch.py:276-277` budgets：已解題在 e≥1 用 min(L, 2×ntf_{e−1})，省下的池按未解題均分加碼；總 evals 不增。

**關鍵限制**：量尺 b = log2(40000) − log2(min(ntf, 40000))，新解若 ntf > 40000 → **b=0，直接增益為零**。C 的價值只在「新解進 feed → uses／comb 有新料」的間接路徑，且 L 題第一輪就沒解的題目在 2–3 倍預算內解出的機率不高。放後備；若要做，判準：new_solves ≥ 2 **且** S ≥ +5（間接路徑的證據），Δ ≥ +8；算力門嚴格 ≤ 親代×1.00（它的賣點就是不加算力）。

（H2「按題去重的 uses」不另立方案：它預期 Δ=0，只在 A 出現不明斜率時當對照臂加跑一次。）

## 3. 推薦順序與 GA 線

1. **A 三臂**（A2、A4、A2m6）先跑；它是唯一直接製造「e1 後新資訊」的方案，且改動最小（兩檔、一欄位、預設關）。
2. A 綠 → **B** 疊在 A 上（親代換成 A 的勝臂重登記）；A 無結論且 lib_size 仍 1 → 查 shadow speed_bits 分布再調門檻一次；A 紅 → 直接跑 B（B 的目標題正是 A 會傷的那批）。
3. C 只在 A、B 都無結論時才排。

**GA 線：暫停，不殺。** 理由：01 §3 證明現行 genome（comb 狀態、路由、權重）不在熱路徑且會被 meter 洗掉，繼續跑是花 GPU 買零。但 GA 框架（突變→meter→符號檢定）本身可用。等 A 落地，把 genome 改成**學習規則旋鈕**：`speed_min_bits`、`m`、`k`、`max_holes`、`lib_cap`、`mdl_div`，撤掉 comb status／route／node weight；round-trip 效果門改成「fixture 上 e2..e4 的 b 有變」。若使用者**不准改 hammer**，GA 唯一還值得的標的是 H5 旋鈕組（m、max_holes、k），但受 §2b 限制預期近零，只當 1 run 的零成本對照，不排整夜。

## 4. 方向題（≤5）

1. **准不准改 hammer 原始碼？**　推薦：准，條件是 frozen 新欄位預設關、clone 門驗親代位元不變。後果：不准 → 只剩 H5 旋鈕，預期近零，本輪等於停。
2. **speed_bits 用有號和（含被拖慢的負項）還是只加正項？**　推薦：有號，與量尺同構，自帶擠壓懲罰。後果：只加正項會多升 comb、更容易把 primitive 題拖慢，A 紅的機率升。
3. **門檻 2 bit 是否先登記為固定、還是三臂掃？**　推薦：三臂掃（2、4、2+m6）＋Holm，只在 training 選。後果：單臂省 2/3 算力但一次沒中就無結論；三臂選到的門檻要在 holdout 審計欄註明「training 選的」。
4. **批次升級沒有逐條歸因，要不要加逐條影子？**　推薦：不加（影子算力 ×n）；靠 no_crowd＋lib_cap＋H24 fuse／ablate 兜。後果：可能一次升進一條壞 comb，由 fuse 在 holdout 回滾，training 量尺不受影響但 lib 會有雜訊。
5. **B_REF 截斷讓新解零分，要不要動量尺？**　推薦：不動（量尺是跨輪比較的基準）。後果：C 線直接增益永遠為 0，只能靠間接證據（S）判定；接受。

## 5. 算力與時程

A 三臂＝3 個 meter run（各 64 題×5 epoch），與 t4f 一次 GA 批（9 標的）相比少 2/3。B 一臂、C 一臂。本輪先排 A；B/C 等 A 結果。全部只在 training 64 題判定、H8/H24 審計欄照寫。
