# 02b Argon 審（Gemini 4 Argon (High)，agy headless，全文貼 01＋02、不用工具）

← [01](01-簡報.md)｜[02 fable](02-規劃-fable.md)｜[代定清單](代定清單.md)｜[progress](progress.md)

呼叫：scratchpad `t7/run-argon.sh`（`agy -p … --model "Gemini 4 Argon (High)" --mode plan`，exit 0，18 KB）。原文照錄於下；隊長處置見[代定清單](代定清單.md)「Argon 處置」節。

隊長查核摘要（對 Argon 自己的事實核對）：
- A4-1「1 條在 e1 升 live、其餘才能 ×3」部分錯：親代 status 表 lib_size 在 e1 已=1，即那條 comb 在 e0 末升、吃 ×4。但「之後新產的 comb 最多 ×3」成立 → 採下修預期。
- A5-1「e1→e2 logcost 870.3→872.1 微退化」屬實，01 漏寫，補進代定 T7-D。
- A7-2「H24 fuse 在迴圈內用 holdout 回滾」是 hammer 既有機制，非本輪新增；但方案 A 若依賴它兜底即違反審計紀律 → 採：判定不可依賴 fuse。
- 隊長自補（Argon 未提）：comb 從同 64 題的解抽出、再讓同題變快，gain 有「自我加速」循環成分 → 審計欄必報 transfer_bits（e0 未解題的 gain）。

---

## (A) 審查

1. **[P0｜機制漏洞] 方案 A「批次影子（batch shadow）無逐條歸因」會導致廢 comb 搭便車整批升 live（審點 1、2）**
   - **問題**：02 §2 寫道 `speed_bits` 為整批 incubating comb 一起跑的批次總量，並寫入每條 `o["evidence"]["speed_bits"]`，再由 `judge.py` 判斷 `speed_bits >= speed_min_bits`。這代表只要批次內**有 1 條好 comb 省下 3 bit**，同批另外 2～5 條毫無貢獻甚至微幅拖慢的廢 comb 會**全部同時過門檻升為 live**。這會瞬間塞滿 `lib_cap`、阻斷 e2..e4 新 comb 晉升，並在 body 列舉時成倍放大分支因子、拖垮基本題。
   - **修正建議**：不需增加 shadow 算力即可做**逐條語法歸因（syntactic attribution）**——在 shadow 命中的程式 AST `prog_shadow[t]` 中，直接檢查該程式實際呼叫了哪條 incubating comb $c$；只有實際出現在加速題 AST 中的 $c$ 才能分到正的 `speed_bits`，未出場的 $c$ 正向貢獻記為 0（並分攤基本題被拖慢的負項）。

2. **[P0｜量法與門檻錯誤] 符號檢定（Sign Test）結構性失靈（必假陰性／假紅），且硬表與 3 臂 Holm 校正算術矛盾（審點 3）**
   - **問題**：
     1. **算術矛盾**：02 §1 硬表（`n=15→k≥12; n=18→k≥13; n=20→k≥15`）是**未校正單臂 $\alpha=0.05$** 的臨界值（例如 $n=18, k=13$ 單側 $p=0.0481$；$n=15, k=12$ 單側 $p=0.0176$），兩者皆**未過** 3 臂 Holm 最嚴門檻 $\alpha/3 = 0.0167$（$n=18$ 需 $k\ge 14$，$n=15$ 需 $k\ge 13$）。02 §2 寫「k_pos 達上表（Holm 後）」自相矛盾。
     2. **檢定選錯導致假陰性／假紅**：擴充 `lib` 的物理特性是「少數用到新 comb 的題大賺（每題 +4～+12 bit），多數沒用到的已解基本題因分支因子微增而微虧（每題 −0.1～−0.5 bit）」。例如 6 題各賺 +6 bit（+36 bit）、14 題各虧 −0.3 bit（−4.2 bit），淨增益高達 **+31.8 bit**，但符號檢定只看正負號不看大小，會算出 `k_pos = 6/20`（判無結論甚至顯著為負的**假紅**）！親代本身就有 11 題微負（think-4 05），正是明證。
   - **修正建議**：廢除無權重的純符號檢定（或設定平手死區 $|Δ_{\text{題}}| < 0.5\text{ bit}$ 視為平手剔除），改用計入幅度的**成對 Wilcoxon 符號等級檢定**或**逐題成對置換檢定（paired permutation test，10,000 次）**，並與 `meter_stats.compare` 統一為單一主檢定，避免三重檢定疊床架屋。

3. **[P0｜算力門漏洞] 算力門 `Σ(evals_body+evals_shadow) ≤ 親代×1.05` 堵不住偷算力，卻會誤殺方案 C 與 A2m6（審點 3）**
   - **問題**：
     1. **分母被未解題稀釋，堵不住偷算力**：64 題中有 44 題未解，每輪固定耗滿 40,000 步（佔總 `evals_body` 近 90%）。變體就算在 20 道已解題或 `sleep_ops`（未計入 `evals_body+shadow`）多花 40% 算力，被 44 道未解題稀釋後總和仍 `< 1.05×`。此外，若 `ntf`/`evals` 計的是「候選程式數」而非「底層 primitive 執行次數」，把 5 個 op 包成 1 個 comb 表面上 `ntf` 下降，實質每步候選的底層計算量卻放大，算力門與量尺皆未設防。
     2. **與方案 C 100% 矛盾**：親代中 20 道已解題在 `ntf < 40,000` 就提早停機，省下的預算並未花掉；方案 C 把省下的預算轉分給未解題花掉，**總 `evals_body` 必然高於親代**，卻設「算力門嚴格 $\le \text{親代}\times 1.00$」，必觸發作廢。
     3. **誤殺成功晉升的變體**：若啟用 `ablate`（leave-one-out 拔除測試）兜底，升上 live 的 comb 越多，`ablate` 重跑的 evals 就成倍增加，反而因為「成功學到多條 comb」而衝破 `1.05×` 被判作廢。
   - **修正建議**：(1) 算力門改為分別卡控：「單題列舉上限 $\le 40,000$（方案 C 例外）」＋「`evals_body`（不含 ablate）$\le \text{親代}\times 1.02$」＋「`sleep + shadow + ablate` 牆鐘時間或總 primitive op 呼叫數 $\le \text{親代}\times 1.15$」；(2) 方案 C 算力門應改為「`Σ evals_body` $\le 64 \times 40,000 \times E$（總預算池上限）」。

4. **[P1｜事實與時序錯] 02 方案 A「e0 末升 live 吃滿 ×4」與「後段斜率 $S \ge +5$」及 01 表格時序矛盾，增益 +15～+50 bit 嚴重高估（審點 1、2）**
   - **問題**：
     1. 看 01 §2 表格：親代 `m=3/輪`，e0 末產生的 3 條候選中，1 條在 e1 升 live，其餘 **2 條**（不是 3～4 條）在 e2 轉 dormant；後續候選要到 e1、e2 末才由 `sleep` 產出，最快只能在 e2、e3 升 live（只能吃 **×3 或 ×2**，吃不到 ×4）。
     2. **自相矛盾**：若如 02 §0 所言「在 e0 末升 live、從 e1 起吃滿 ×4」，則增益在 `b_1` 就已完全實現，後段斜率 $S = \sum_{e=2..4}(b_e - b_1)$ 必為 **0**，不可能同時滿足副判準 $S \ge +5$！反之，若要 $S \ge +5$，代表增益發生在 e2..e4，乘數最多 ×3～×1。
     3. 親代已拿走 168.7 bit（其中 comb 98.6 bit），且 `lib_size=1` 就已造成 11 道基本題虧損 0.2–14.7 bit；當 `lib_size` 升至 3～5，基本題分支懲罰將擴增 3～4 倍。
   - **修正建議**：將方案 A 預期淨增益下修為 **+8～+25 bit**，主判準綠燈門檻由 `Δ ≥ +15` 下調至 `Δ ≥ +8`（配合成對檢定顯著），以免把真實的 +10 bit 改善誤判為無結論。

5. **[P1｜診斷遺漏] 01 §2(a) 漏讀自身表格：`e1→e2` 並非無新資訊，而是新進題更新 `uses` 反致退化，且漏掉「新 comb 缺乏 `uses` 先驗」的冷啟動問題（審點 1）**
   - **問題**：
     1. 01 §2 表格顯示 `gate_in` 在 e0 為 14 題、e1 增為 20 題（多 6 題），而 `logcost_L` 在 e1 是 `870.3`，到 e2–e4 卻退化為 `872.1` 並鎖死。這證明 **e1 末那 6 道新解題進 feed 更新 `uses` 排序後，反而把 e2 的列舉順序弄糟了（+1.8 logcost）**，直到 e2 後解集不再變才鎖死在 872.1！
     2. 當一條新 comb 剛進 shadow 或剛升 live 時，它在過往 `state.uses` 的計數為 **0**（因為舊 feed 程式是用展開前的 primitive 寫的）。若 `order_from_uses` 未給新 comb 合理的初始權重（如繼承其 anti-unification 的 support 題數），新 comb 在列舉順序中會排在最後，連在 shadow 中都可能測不出應有的加速（`speed_bits` 被低估）。
   - **修正建議**：在 01 §2 補上「新進題污染全域 `uses` 導致 e1→e2 微退化」與「新 comb 在 `uses` 中的冷啟動順位」兩項診斷，並在方案 A 確認新 comb 的 `uses` 初始值是否已用 support count 熱啟動。

6. **[P1｜推論漏洞] 方案 A「一階 comb 進 feed 會自動長出二階 comb（comb 套 comb）」忽視 AST 壓縮對 anti-unification 門檻的反效果（審點 1、2）**
   - **問題**：02 §2 推論「e1 的 feed 程式改用一階 comb 改寫 → e1 sleep 能長出二階 comb，e2 再升」。但當原本 4～6 個節點的子樹被替換成 1 個 `comb_0` 單節點後，AST 深度與節點數大幅縮小；`sleep_ops` 做 anti-unification 時，含 `comb_0` 的外層共同骨架往往只剩 1～2 個節點，其 `saving` 與 `mdl_div` 反而**更難跨過 `gate_g1` 的硬門檻**，且呼叫同一條 `comb_0` 的題數可能低於 `loo_min_pairs=3`。因此 e2 大機率長不出二階 comb，$S \ge +5$ 不宜押注在「二階 comb」上。
   - **修正建議**：若要長出二階 comb，`sleep_ops` 計算 `saving` 時應以「展開回 primitive 的等效節點數」計價，而非把 `comb_0` 當作大小為 1 的原子節點。

7. **[P1｜審計紀律違反] 方案 A「失敗後看 training 的 `speed_bits` 分布再重調門檻」與「靠 H24 fuse 在 holdout 回滾」違反隔離與預先登記原則（審點 3）**
   - **問題**：
     1. 02 §2 寫「若三臂 `lib_size(e4)` 仍 =1 → 看 shadow 的 `speed_bits` 分布再定一次門檻（仍只看 training）」。在同一個 64 題 training 集上看完全部結果與特徵分布、事後挑一個剛好能過的門檻，再用同一批 64 題跑假設檢定，屬於**資料依賴的事後選門檻（post-selection inference）**，檢定 p 值直接失效。
     2. 02 §2 與 §4 Q4 寫「可能一次升進一條壞 comb，由 H24 fuse 在 holdout 回滾」。若在訓練 epoch 中用 H24（holdout）的表現來觸發回滾，等於**把 holdout 當成早停／篩選驗證集摻入模型狀態演化**，直接違反「H8/H24 只審計、不進判定」。
   - **修正建議**：(1) H24 fuse 嚴禁在 training 的 e0..e4 迴圈內介入狀態回滾，迴圈內只能用 training 自身的 `no_crowd` / `ablate`；(2) 不要盲猜 2、4 bit 跑完三臂才偷看分布——**親代 `t4f-parent` 跑過的 10 條 dormant comb 已經有現成的 shadow 紀錄**，應在寫 prereg 前先離線算完親代那 10 條的 `speed_bits` 分位數，一次定死單一門檻。

8. **[P1｜歸因錯誤與高估] 方案 B（H3 分桶先驗）誤把「`lib` 膨脹的擠壓損失」當成 `uses` 稀釋，且小桶回退後增益遠低於 +10～+30 bit（審點 2）**
   - **問題**：01 §4 H3 與 02 §2 方案 A 自己都寫道「親代 `lib` 變大後純 primitive 題反小輸 0.2–14.7 bit（11 題）」，但在方案 B 卻宣稱「只把 `uses` 按尺寸分三桶、不動 `lib`，就能回收那 11 題的一半（+10～+30 bit）」。事實上：(1) 那 11 題的損失有相當比例來自 `lib_size=1` 新增的 comb 搶走列舉分支，分桶 `uses`（若不把 comb 也按桶隔離）根本無法消除 `lib` 的分支膨脹；(2) 20 道過 gate 題中約 70%～80% 集中在「同尺寸」桶，「放大／縮小」兩桶各僅 2～4 題（低於 `<3` 題門檻即回退全域，高於門檻則因樣本僅 3～4 題導致未出現的 primitive 計數歸零、順序劇烈退化）。
   - **修正建議**：方案 B 必須連同 **live comb 一併納入 `uses[bucket]` 計數**（某桶沒用過的 comb 在該桶排到最後），並對小桶採用 Dirichlet 平滑（$\text{uses}_{\text{bucket}} + \lambda \cdot \text{uses}_{\text{global}}$）取代硬回退，預期增益下修至 **+4～+15 bit**。

9. **[P2｜方案設計與順序] 直接跑 A 三臂缺「Step 0 離線驗屍」，且 `A2m6` 混雜雙變因又白付 Holm $\alpha/3$ 懲罰（審點 4）**
   - **問題**：(1) 未先離線檢查親代現有 10 條 dormant comb 在 shadow 中的實際 `ntf_shadow` 就直接改碼跑 3 個 meter run，若親代 shadow 中那 10 條因冷啟動順位問題本來就沒讓 `ntf_shadow < ntf_live`，三臂會全軍覆沒；(2) `A2m6` 同時改了 H1（`speed_min=2`）與 H5（`m=6`），混雜兩個假設，且 3 臂並跑使每臂顯著水準腰斬為 $\alpha/3 = 0.0167$，在小樣本下極易三臂全落入「無結論」。
   - **修正建議**：先做 **Step 0（零算力離線分析親代 shadow log）** 鎖定最佳 `speed_min`；正式實驗改為**階層式單臂序列檢定（Fixed-sequence testing）**：先跑單一主臂 `A_best`（獨享完整 $\alpha=0.05$），只有 `A_best` 過門檻才加跑 `+m6` 測邊際貢獻。

10. **[P2｜GA 線定位矛盾] 02 §3 擬將 GA 改搜 6 個學習規則旋鈕（`speed_min_bits, m, k...`），既無梯度又違反「不在 training 64 題反覆調參」（審點 1、3、4）**
    - **問題**：(1) 01 §3 正確指出舊 genome 被 meter 洗掉，但漏了另一半真相：學習規則旋鈕（`m, k, max_holes, lib_cap, mdl_div`）作用在僅 14～20 題的離散集合上，多重門檻交集形成大片「階梯高原（單步突變 $\Delta=0$）」，用線上 GA 隨機單步突變依然是高成本盲搜；(2) 02 §1 嚴格規定「門檻只在 training 64 題選、最多重調一次」，但 02 §3 卻規劃「用 GA（突變→meter→符號檢定）自動搜 `speed_min_bits, m, k...`」——在 64 題 training meter 上跑多代 GA 演化這 6 個超參數，本質上就是在 training 集上做數十次無校正的自適應門檻微調，必然過擬合 64 題！
    - **修正建議**：**徹底停掉線上 meter-in-the-loop 的超參數 GA**。`m, max_holes, mdl_div` 等睡眠超參數應在離線 AST fixture 上用確定性網格檢查候選品質（見提案 5），不該丟進線上 GA 燒 GPU 與透支統計檢定力。

---

## (B) 提案

1. **影子逐條語法歸因（Zero-Cost Per-Comb Attribution）＋ 新積木先驗熱啟動（Prior Warm-Start）**
   - **做法與高回報理由**：直接堵死方案 A 最大的兩個破口（批次搭便車＋新 comb 冷啟動順位墊底）。在 `epoch.py` 影子段，解析每道加速題的命中 AST `prog_shadow[t]`，只把正的 $\log_2(\text{ntf}_{\text{live}}/\text{ntf}_{\text{shadow}})$ 歸因給實際出現在該 AST 中的 incubating comb $c$（若多條共現則均分），並讓每條 $c$ 承擔未被加速題的平均分支負項；同時將新產出 comb 在 `state.uses` 的初始計數設為其 anti-unification 的 `support_count`（在幾道 feed 題中出現），讓它在 shadow 與 e1 列舉中排進合理順位。
   - **成本**：極低（改 `epoch.py` 與 `compress.py` 約 20 行，**零額外 shadow 列舉算力**）。
   - **第一步**：不跑新實驗，直接寫腳本讀取親代 `t4f-parent` 既有的 `epochs/*/status.json` 與 shadow 輸出，離線計算那 10 條 dormant comb 的「批次 `speed_bits` vs 逐條語法歸因 `speed_bits`」及它們當時的列舉順位。

2. **殘差加權睡眠與先驗（Residual-Weighted Sleep & Uses：專抽「慢解題」的共同結構）**
   - **做法與高回報理由**：01 §2 指出的核心病灶是「e1 後 20 題解集不變，`sleep_ops` 每輪對同樣 20 題平權抽 common subtrees，被幾百步秒解的簡單題佔滿 `m=3` 名額」。事實上，20 題中「`ntf` 高達 5,000～35,000 的慢解題」才是真正有大空間可降 bit 的金礦！將 `sleep_ops` 的 `saving` 評分與 `uses` 累加乘上每題的**殘差成本權重 $w_t = \max(0, \log_2(\text{ntf}_{t, e-1}) - \text{floor})$**（慢題權重高、已被壓到秒解的題權重自動衰減）。如此一來，即使 20 題名單不變，當 e1 把第一批慢題壓快後，權重在 e2 會自動轉移到下一批慢題，**不靠新解也能讓 e1→e2→e3 輪輪抽出不同題群的新積木**。
   - **成本**：低（改 `grow.py:sleep_ops` 候選計分與 `epoch.py` 的 `uses` 加權，約 15 行，不增加算力）。
   - **第一步**：取出親代 e1 的 20 道過 gate 題，按 `ntf_1` 由慢到快排序，對最慢的 8 題單獨離線跑一次 `sleep_ops`，比對抽出的 top-3 comb 與原全集 top-3 的差異。

3. **把「`train_ok` 但未過 LOO gate」的邊緣解納入睡眠候選池（打破 20 題封閉資訊池）**
   - **做法與高回報理由**：01 §2(c) 點出 44 道未過 gate 題完全不供料。但未進 `gate_in` 的題目中，存在「已通過 `train_ok`（或答對 $k-1/k$ 個訓練對）卻被 `loo_min_pairs` 擋在 gate 外」的邊緣命中程式。這些程式往往是因為缺了一個關鍵積木才被迫用冗長破脆的 AST 湊出解。允許 `sleep_ops` 從「`gate_in` $\cup$ `train_ok_only`（打折權重 0.5）」抽取 anti-unification 候選（但 `state.uses` 仍只計 `gate_in` 以防過擬合噪音污染排序），能直接從卡關題抽出跨題共享積木，在下一輪把邊緣題推進 `gate_in`（一題新解即拿 $+15.29 \times (E-e)$ bit）。
   - **成本**：低（`train_ok` 程式在 `epoch.py` 本來就已搜出，傳入 `sleep_ops` 僅約 10 行改動，**零額外列舉算力**）。
   - **第一步**：統計親代 `t4f-parent` 在 e0..e4 各輪中「`train_ok=True` 但未過 `gate`」的題數與 AST，看能為 `sleep_ops` 多提供多少新樹。

4. **列舉先驗保底混合（$\epsilon$-Floor Prior Mixing）或雙佇列交錯，零特徵工程根治 11 道基本題倒退**
   - **做法與高回報理由**：親代與方案 A/B 最怕「學了 `uses` 與新 comb 後，11 道純 primitive 題倒退 0.2–14.7 bit」，方案 B 想靠任務特徵分桶救，卻受制於小桶樣本不足。其實某題會暴跌 14.7 bit（`ntf` 暴增 $2^{14.7}\approx 26,000$ 倍），是因為 `order_from_uses` 把本輪未出現的某個 primitive 排到最底，或列舉預算 100% 押在更新後的單一順序上。只要在列舉器採用 **$(1-\epsilon)$ 學習順序與 $\epsilon$ 原始 e0 基準順序交錯列舉**（例えば $\epsilon=0.25$，每 4 步有 1 步走 e0 無 comb 原始佇列，已測程式 hash 去重），任何題目在數學上 `ntf` 最差只會退化 $1/\epsilon = 4$ 倍（**單題最大可能虧損硬封頂於 $-2.0\text{ bit}$，徹底消滅 -14.7 bit 暴雷**），而用到新 comb 的加速題最多只慢 $1/(1-\epsilon) = 1.33$ 倍（僅少賺 $0.41\text{ bit}$）。
   - **成本**：低～中（若在 `compress.order_from_uses` 對 log1p 權重做保底收縮與 comb 懲罰偏置僅需 10 行；若在 `body.py` 做 3:1 批次交錯約 25 行，總 `evals_body` 不變）。
   - **第一步**：調出 `think-4 05` 那 11 道倒退題在 e0 與 e1 的 `ntf`，離線模擬 $\epsilon=0.25$ 交錯列舉下這 11 題可確定性回收多少 bit（凡是單題虧損 $>2\text{ bit}$ 的部分可 100% 回收）。

5. **離線毫秒級「睡眠—裁判重放器（Offline Sleep-Judge Replay）」，取代線上 GA 調參**
   - **做法與高回報理由**：02 §3 打算等 A 落地後用線上 GA 搜 `m, k, max_holes, lib_cap, mdl_div, speed_min_bits`。其實 `sleep_ops`（anti-unification）與 `judge` 過濾完全不需要跑 GPU 列舉，在 CPU 上對 20 棵 AST 跑一次只需幾毫秒！寫一個離線重放腳本，直接載入親代 e0/e1 的 feed AST 與 shadow 紀錄，在 CPU 上 1 秒內掃完 `(m, max_holes, mdl_div)` 的完整網格，直接看哪組旋鈕能抽出「高 saving、跨題覆蓋廣、且包含二階組合」的候選集，挑出唯一最佳組合後再進 `meter` 做單次預先登記驗證，省下 95% GPU 算力且不污染 training 統計檢定。
   - **成本**：極低（約 40 行 Python 離線分析腳本，GPU 算力成本 = 0）。
   - **第一步**：把親代 e0（14 題）與 e1（20 題）的命中 AST 存成單一 JSON fixture，跑一次 `m ∈ {3,6,10} × max_holes ∈ {1,2,3}` 的離線 `sleep_ops` 矩陣表。
