# 02b Argon 審（Gemini 4 Argon (High)，agy headless，全文貼 01＋02、不用工具）

← [01](01-簡報.md)｜[02](02-規劃-fable.md)｜處置見 [代定清單](代定清單.md)

## (A) 審查

1. **[P0｜語意漏洞・審點(2)] A2「先跑全層 CPU 段、再跑 GPU 段」必破 `nodes_to_first` 與超預算截斷之 `0 mismatch`**
   - **問題**：`02` A2 擬將 `segs` 走兩遍（先跑完全層 `!g.sup` CPU 段，再跑 GPU 段），並稱「需確認是否互讀寫同一層 bank」。但依 `01` §2 第 3、4 點，原迴圈依 `(op, comp)` 順序走訪，期間累加 `nodes` 並在 `nodes >= budget` 時立即 `throw Done`，且 CPU 段 `apply()` 與 GPU `SURV` 皆呼叫 `emit()` 驗解、寫入當層 bank 並抓指紋雙胞。將全層 CPU 段提前會直接改變：① 同層找到首解時的已訪節點數 `nodes_to_first`；② 最後一層撞到 `budget` 截斷時哪些候選先被評估（絕大多數列舉器皆在最後一層因超預算中止）；③ 同層指紋雙胞誰先進 bank。必破 `0 mismatch`。
   - **修正建議**：刪除 A2（兩遍走訪）。其實只做 A1（預先非同步 launch GPU chunk，仍按原 `(op, comp)` 順序走訪，走到該 `g.sup` 段才 `cudaEventSynchronize`），排在 GPU chunk 之前或之間的 CPU `apply()` 段**天然就會與背景執行中的 GPU chunk 重疊**，完全不必改動段順序，100% 保 `0 mismatch`。

2. **[P0｜模型漏項與判準矛盾・審點(1)(3)] 模型漏計 `sync_s`（10.1 s）與每層多 chunk 同步次數，導致 A0 門檻（`λ ≤ 0.6 ms`）假綠**
   - **問題**：① `01` F4 顯示 B1 的 `sync_s = 10.1 s`（`g_sync` 增量上傳，平均 `1.62 ms/層`）獨立於 `gpu_s = 166.0 s` 之外，但 `01` §3 公式 $T_{\text{gpu}} \approx [W_c + W_g/X + s\cdot\lambda - \text{overlap}]/P$ 漏列 $T_{\text{sync}}$ 與 host 端組 jobs 開銷。若如 `02` A 風險欄所言 `1.6 ms/層` 是無法重疊的固定成本，光 `sync_s`（10.1 s）就已吃光 $W_g$（10.5 s），即使 $\lambda \to 0$ 也不可能達成 1.2×（總開銷須 $\le 3.8\text{ s}$）。② `01` §2 指明每層依 rank 分多個 chunk、「每 chunk 一次 D2H 同步」，故實際 chunk 同步次數 $s_{\text{chunk}} = \sum \text{chunks} \ge 6,230$，而非層數 6,230。③ `02` A0 只量單次 `e2e_run_chunk` 且以 `λ ≤ 0.6 ms` 為閘 1 判準，未將 `g_sync` 與每層 chunk 數計入，會在閘 1 判出**假綠**。
   - **修正建議**：將打平／1.2× 不等式修正為 $s_{\text{layer}}\cdot\lambda_{\text{sync}} + s_{\text{chunk}}\cdot\lambda_{\text{chunk}} \le 3.8\text{ s}$；A0 微基準必須連同 `g_sync` 一起測（或將 `g_sync` 非同步併入 chunk stream，見提案 2），且閘 1 門檻改看「每層含 `g_sync`＋該層所有實際觸發 chunk 的總阻塞時間平均 $\le 0.6\text{ ms}$」。

3. **[P0｜數學推導錯誤・審點(1)] A2 重疊上限用「每層平均 $W_c = 4.8\text{ ms}$」推導 `λ ≤ 5.4 ms`，犯了均值代換（Jensen 不等式）與範圍錯誤**
   - **問題**：`02` A 算「每層 $W_c \approx 4.8\text{ ms}$，故重疊後 1.2× 條件放寬為 $\lambda \le 5.4\text{ ms}$」。此推導有兩處錯誤：① **候選數跨層高度偏斜**：6,230 層中多數是 L2–L4 小層（$W_{c,i}$ 僅數十 $\mu\text{s}$，遠小於 $4.8\text{ ms}$，藏不住 ms 級 $\lambda$），少數大層雖有數十 ms 的 $W_{c,i}$，但單層最多只能藏住一個 $\lambda$；由 Jensen 不等式 $\sum_{i=1}^s \max(0, \lambda - W_{c,i}) \gg s \cdot \max(0, \lambda - \bar{W}_c)$。② **$W_c$（74%）不全在 `wait` 之前**：74% 含 GPU `SURV` 回 CPU 後的 `emit()` 驗解、bank 去重與簿記（F3 佔 17%），這些發生在 `wait` **之後**，依賴 GPU status，無法與當次 `wait` 重疊。
   - **修正建議**：廢除 `5.4 ms` 門檻。改用既有 profile 逐層實算 $\sum_i \max(0, \lambda - W_{c,\text{pre-wait},i}) \le 3.8\text{ s}$（其中 $W_{c,\text{pre-wait},i}$ 僅計入該層在等待該 chunk 前可執行的 CPU 段時間）求真實容許之 $\lambda$。

4. **[P1｜事實與算式錯讀・審點(1)] `01` F3 與 `02` C 對 Amdahl `1.9×` 與 `5.7×` 的物理意義寫錯**
   - **問題**：`01` F3 寫「一階 ≈37%、lambda 46%、簿記 17%；只一階免費→≈1.6×，lambda 也免費→≈1.9×，兩者＋簿記外≈5.7×」，`02` C 接著寫「1.9×（一階＋lambda 免費）～5.7×（簿記也外移）」。驗算可知：$1/(1-0.37) = 1.59\times$（只一階免費）；$1/(1-0.46) = 1.85\times \approx 1.9\times$（這是**只讓 lambda 46% 免費**，而非一階＋lambda 兩者免費！）；$1/(1-0.37-0.46) = 1/0.17 = 5.88\times \approx 5.7\times$（這才是**一階＋lambda 兩者免費、留 17% 簿記在 CPU 外**！若連簿記也外移則是 $1/0 \to \infty$）。`01` 把「只 lambda 免費」誤寫為「lambda 也免費」，`02` 又把「留簿記在外（簿記外）」誤讀為「簿記也外移」。
   - **修正建議**：更正 F3 與方案 C 上限表述：只一階免費 $1.6\times$、只 lambda 免費 $1.9\times$、**一階＋lambda 兩者免費（留 17% 簿記在 CPU）即達 $5.7\times$**。這代表方案 C 不必把全部 CPU 簿記搬上 GPU 就已經擁有 $5.7\times$ 的 Amdahl 上限。

5. **[P1｜效能自殘與假紅・審點(1)(2)(3)] A1 整層無條件預發忽略「最後一層超預算浪費」，且判準強制 `--gpu-min 0` 必造假紅**
   - **問題**：① 原程式「walk 走到才 launch chunk」是為了避免最後一層超預算浪費（最後一層總候選可達百萬，但剩餘預算 `budget - nodes` 常只剩幾千，第 0 個 chunk 就 `throw Done`）。A1 改成「整層 chunk 全部預先 launch」，雖不改 `nodes` 計數，卻會在全部 1,253 個列舉器的最後一層白做整層 jobs 建構、H2D 與 kernel 執行，嚴重反噬牆鐘。② `01` F1 已明言 L2 小層 GPU 吞吐僅 `0.13×`（比 CPU 慢 7 倍），`02` 卻在 A1/A2 通過判準硬規定 `--gpu-min 0` 下 1e6 要 $\ge 1.2\times$ CPU，等於強迫把必虧的小層全送 GPU，必造成**假紅**。
   - **修正建議**：① A1 預發必須加上**剩餘預算上限**（只預發累計候選數 $\le \text{budget} - \text{nodes}$ 的 chunk，或雙 chunk 滑動視窗預發）。② 移除判準中的 `--gpu-min 0`，將 `--gpu-min` 視為必調門檻（見提案 1）。

6. **[P1｜量法與門檻問題・審點(3)] A0 用中位數（median）判門檻會假綠；B 綁定「汙染條件 $\ge 1.0\times$」不可重現**
   - **問題**：① 牆鐘總延遲是總和 $\sum_{i=1}^s \lambda_i = s \cdot \text{mean}(\lambda)$。因每層候選數高度右偏，$\text{mean}(\lambda)$ 遠大於 $\text{median}(\lambda)$；A0 用 `median λ ≤ 0.6 ms` 當判準會低估總延遲，產生**假綠**。② B 的通過判準要求「汙染條件（$\lambda \approx 27\text{ ms}$）1e6 $\ge 1.0\times$ CPU」，但 8 個背景夜跑的負載隨時跳動，並非受控環境，極易產生隨機**假綠／假紅**。
   - **修正建議**：① A0 門檻改用依 1e6 實況候選數分佈加權後的 **mean $\lambda$**。② 若要驗證方案 B 對高延遲的韌性，應在乾淨環境下人工注入固定延遲（如每次 launch 附加固定 $\mu\text{s}$ sleep 或 busy-wait kernel），而非依賴不可控的背景夜跑。

7. **[P1｜防汙染漏洞・審點(3)] 乾淨判定與 50 層 Canary 無法防住 CPU 記憶體頻寬爭搶與時間片空檔假綠**
   - **問題**：① `02` 定 `loadavg(1m) < P`（$P=4$），但本機有 16 核，若有 3 個背景行程各吃滿 1 核（`loadavg = 3 < 4`），雖不搶這 4 條 worker 的 CPU 核，卻會爭搶共用 L3 cache 與記憶體頻寬；而 `arcbatch` 的 bank 去重與 AST 建構高度受限於記憶體頻寬，會把 CPU 基線拖慢（且 task 秒加總也會同幅變慢，雙報抓不到），造成 GPU 相對比值的**假綠**。② 開跑前 50 層 $\lambda$ canary 在低負載空檔僅需 $\approx 10\text{ ms}$，在時間切片下極易剛好滑進其他行程的空檔而測出低值，無法代表後續 20 秒的排隊狀況。
   - **修正建議**：① 乾淨條件收緊為系統 `loadavg(1m) < 0.5`（除本行程外無活躍 CPU/GPU 行程），且 ABAB 交錯時檢查 CPU 版的「每節點耗時（ns/node）」與歷史基準偏差 $<5\%$。② 取消開跑前 50 層 canary，改為直接記錄 `arcbatch` 全程每層實際 `wait_ns` 的 mean/p90/p99。

8. **[P2｜推論漏洞・審點(1)(2)] 誤判「提高 $P$ 對比值沒幫助」與「跨題合批必須同層（同 size）」**
   - **問題**：① `02` A 稱「$P$ 由 4 提到 16 對比值沒幫助，CPU 版也可開 16 執行緒」。但當 $P$ 已達實體核數（16 核）後，繼續超額訂閱（如 $P=32$）對純 CPU 版毫無幫助；反之 GPU 版在等待同步時若用 `cudaEventBlockingSync`，等待中的執行緒會睡眠讓出 CPU 核給其他執行緒跑 $W_c$，故**超額執行緒（$P > \text{核數}$）只會幫 GPU 版藏 $\lambda$**，比值會提升。② `01`/`02` 皆假設 B 必須「N 題**同層**一起 launch」，但 GPU kernel 只是評估 `(op, arg1, arg2)` 陣列，不同列舉器即使處於不同 `size`（如 L4 與 L5）也能合批 launch，限制「同層」白白把 $N_{\text{eff}}$ 切碎了 5 倍。
   - **修正建議**：① 將「超額執行緒＋`cudaEventBlockingSync`」納入藏延遲手段（見提案 3）。② B0 模擬 $N_{\text{eff}}$ 時不限同 `size`，凡處於待 launch 點的列舉器皆可合批。

9. **[P2｜路線順序問題・審點(4)] 推薦路線把「等停夜跑量 A0」當成唯一閘 0，忽略可在汙染下立即完成且決定架構生死的兩項前置檢查**
   - **問題**：`02` 把所有行動卡在「等使用者排 10–15 分鐘停夜跑量 A0」。但有兩項關鍵檢查**完全不受 GPU 排隊影響、現在就能做**，且直接決定路線 A/B 是否成立：① 輸出 1e6/1e7 每層 `(size, 總候選, GPU支援候選, 剩餘預算)` 分佈（補齊 E14），算出濾除小層後的真實 $s$ 與 $W_g$；② 拆解 `g_sync` 的 `10.1 s` 究竟是 host 端 CPU 序列化開銷還是 CUDA 同步阻塞。若 host 端 CPU 打包本身就 $>3.8\text{ s}$，即便乾淨 GPU $\lambda=0$ 也不會過 1.2×。
   - **修正建議**：將「E14 每層候選與剩餘預算分佈統計」與「`g_sync` host/device 計時拆帳」移到閘 0 之前立即執行，不必空等乾淨 GPU 窗口。

---

## (B) 提案

1. **提案 1：以「有效候選數 `min(GPU候選數, 剩餘預算) >= gpu_min`」做動態門檻＋預算上限預發（零架構改動砍掉 60%–80% $s$）**
   - **為何回報更高**：6,230 層中大半是 L2–L4 小層（F1 顯示 L2 GPU 吞吐僅 0.13×，上 GPU 反而倒貼）或最後一層「整層候選大、但剩餘預算 `budget - nodes` 極小」的截斷層。現行只看整層總候選 `< gpu_min`，且設定非 0 即 200,000（全關）。改用 `eff_cands = min(gpu_cands, budget - nodes) >= gpu_min` 並只預發累計候選 $\le \text{budget} - \text{nodes}$ 的 chunk，能直接砍掉 60%–80% 的無效同步 $s$ 與 `sync_s`，同時保留 $>90\%$ 的大層 $W_g$（L5–L6 吞吐 30×）。
   - **成本**：0.5 天（約 20 行程式碼，天然維持 `0 mismatch`）。
   - **第一步**：在 `seed_enum_gpu.cpp:gpu_layer()` 印出每層 `(gpu_cands, budget - nodes, 實際走訪 nodes, cpu_ns)`，離線掃描 `gpu_min ∈ {5k, 10k, 25k, 50k}` 畫出「保留 $W_g$ vs 剩餘同步次數 $s$」的 Pareto 曲線。

2. **提案 2：開啟 NVIDIA MPS 消除多行程時間切片排隊＋將 `g_sync` 改為 Pinned Async H2D 併入首個 Chunk Stream**
   - **為何回報更高**：① `01` §5 指出 $\lambda=27\text{ ms}$ 源於 Default 模式 8 行程硬體時間切片（context switch 動輒數 ms）。開啟 CUDA MPS（Multi-Process Service）後，多行程共用單一硬體 context 並在 SM 上空間多工，**不改一行程式碼、也不必停夜跑**即可大幅壓低共存時的排隊延遲 $\lambda$。② B1 的 `sync_s = 10.1 s`（每層 1.6 ms）單項就吃光打平餘裕；將 bank 增量改寫入 host pinned buffer，並延遲到該層第一個 GPU chunk 確定要跑時，用 `cudaMemcpyAsync` 掛進同一個 CUDA stream 連同 jobs 一起發射，可直接消滅每層獨立的 `g_sync` 同步點。
   - **成本**：MPS 實測 1 小時；`g_sync` 非同步合併 1 天。
   - **第一步**：先將 `g_sync` 拆為「host 打包 ns」與「CUDA 傳輸／同步 ns」確認 10.1 s 的真兇；同時在測試機啟用 `nvidia-cuda-mps-control -d` 跑 A0 微基準比較 $\lambda$ 降幅。

3. **提案 3：將 Worker 數 $P$ 拉滿本機 16 核，並以「超額執行緒（$P=32$）＋ `cudaEventBlockingSync`」跨題藏延遲（免寫方案 B 排程器）**
   - **為何回報更高**：若目標是縮短「端到端牆鐘」，本機有 16 核卻只開 $P=4$（`01` §4a），把 $P$ 提到 16 可讓端到端牆鐘立刻縮短 **3～3.5×**（遠大於一階 GPU 的 1.35× 天花板）。針對 GPU 同步延遲，只需將 chunk 等待改為 `cudaEventBlockingSync`（睡眠等待不佔 CPU）並開 $P=32$（2 倍核數，共用單一 CUDA context 搭配 per-thread stream）：當 16 條執行緒卡在 GPU `wait` 時，OS 自動排程另外 16 條執行緒在 16 個 CPU 核上跑 $W_c$（74% CPU 段），**不必花 2–4 週寫方案 B 的協程狀態機與合批池，就能達到跨題藏 $\lambda$ 的效果**。
   - **成本**：0.5～1 天（改執行緒數、per-thread stream 與 `cudaEventBlockingSync`）。
   - **第一步**：先在純 CPU 模式測 $P \in \{4, 8, 16\}$ 的 1e6/1e7 牆鐘；再於 GPU 模式開 `cudaEventBlockingSync` 比較 $P=16$ 與 $P=32$ 的 CPU 核心利用率與牆鐘。

4. **提案 4：補齊剩餘 11% 一階原語上 GPU（將 Amdahl 天花板從 1.35× 提至 1.60×，容許同步預算翻倍）**
   - **為何回報更高**：`01` F2 與 F3 揭示：全部一階評估佔 CPU 時間 **37%**（上限 $1.60\times$），但目前 GPU kernel 只支援 **26%**（上限 $1.35\times$）。在 $1.35\times$ 上限下，要拿 $1.2\times$ 僅有 $3.8\text{ s}$ 同步預算；若把剩下 11% 的一階原語補進現有 GPU kernel，$W_g$ 從 $10.5\text{ s}$ 增至 $14.9\text{ s}$，拿 $1.2\times$ 的容許同步開銷從 $3.8\text{ s}$ 暴增至 **$8.2\text{ s}$（翻倍以上）**，工程量遠小於方案 B（2–4 週卻仍封頂 1.35×）與方案 C（1–3 個月）。
   - **成本**：3～5 天（在既有 `seed_enum_gpu` 內補齊一階 op 分支，不涉變長 BodyPool 與 GPU 去重）。
   - **第一步**：從 M0/N5c profile 列出這 11% 落差中佔比最高的前 3 個 `!g.sup` 一階 op，優先實作前 2 名。

5. **提案 5：直接優化 CPU 端 74% 熱點（Lambda 多範例批次評估 ＋ Bank 去重 Flat Hash Table）**
   - **為何回報更高**：依 F3，1e7 下 CPU 有 **46% 在 lambda 評估、17% 在簿記（bank 去重與 `emit`）**。與其花 1–3 個月把整個列舉器與去重搬上 GPU（方案 C），不如直接在 CPU 端優化這 74%：① lambda body 對同一題多個訓練範例（grids）的執行改為一次 AST 派發跑完全部範例（消除逐範例虛擬呼叫／分支開銷，並提早剪枝第一個失敗範例）；② 17% 簿記中的指紋查表改用預分配開放定址雜湊表（Flat Hash Table + `__builtin_prefetch`）壓低 L3 cache miss。CPU 端這 74% 只要提速 $1.35\times$，端到端牆鐘增幅就已超過「一階 GPU 0 延遲無限快」的理論極限，且完全不受夜跑搶卡影響。
   - **成本**：2～4 天（純 CPU 局部優化，0 架構風險，`0 mismatch` 易保）。
   - **第一步**：對純 CPU 1e7 跑 `perf record`（或 `--seed-prof`），抓出 46% lambda 與 17% 簿記中耗時前 3 名的 C++ 函式與 cache-miss 熱點。
