以下依您的要求，針對 `02-規劃-fable.md`（對照 `01-簡報.md` 事實）進行審稿，分為 **(A) 審查** 與 **(B) 提案** 兩段。

---

## (A) 審查：設計 02 的錯誤、漏洞、失明／誤判風險與「假綠」分析

### 一、剝光 `comb` 後，尺是否還在量「學習能力」？

1. **`[P0 致命｜量錯標的]` `learn_bits` 直接加總 $e=1..E$ 且不扣 $e_0$，實際上 70%–100% 在量「Epoch 0 靜態搜樹速度」，而非「跨輪學習能力」**
   - **問題**：A1 定義 $\text{learn\_bits} = \sum_{e=1}^E \sum_{t \in L'} [\log_2 B - \log_2 \min(\text{ntf}_{t,e}, B)]$，並稱「不相對 $e_0$（庫存已剝，$e_0$ 解出的就是骨架自己的本事）」。但 $e_0$ 時樹還沒有從題目合成／晉升任何新 `comb`，此時解出的題目靠的是原生算子＋`decomp`＋初始 `route/weight` 的**靜態暴力搜尋**。
   - **後果**：一題在 $e_0$ 靠原生算子解出，會在 $e=0,1,2,3$ **重複領 4 次分數**（佔總分大頭）；反觀真正透過跨輪學習（在 $e_0, e_1$ 合成新 `comb` 並經 `gate/judge` 晉升，於 $e_2, e_3$ 才首次解出或大幅壓低 `ntf`）的題目，只領 1～2 次分數。結果量尺主體仍在量「$e_0$ 靜態路徑排序」，而非「跨輪合成與學會積木的能力」。

2. **`[P0 致命｜選題矛盾]` $L'$ 從 P48 取「活樹首解 `ntf` 最小」的 10 題，要麼免學即解、要麼剝庫後全掛**
   - **問題**：A2 選題規則為「L16 已解 6 題＋P48 已解 15 題中依活樹首解 `ntf` 由小到大取 10 題」，同時依 D17 清空 P 池、剝光 `comb`。
   - **兩種崩潰情境**：
     - **情境甲（若活樹首解在 $e_0$）**：`ntf` 最小代表根本不需要合成 `comb`、僅靠原生算子幾百～幾千節點就能秒解。放進 $L'$ 只會讓 4 個 epoch 都重複測 $e_0$ 原生搜尋，`auc_speed` 趨近 0。
     - **情境乙（若活樹首解在後期 epoch）**：活樹之所以 `ntf` 極小（如 01 簡報中 `68b16354` 的 `ntf=13`），是因為**命中既有 `comb` 積木**，而該積木可能來自 P48 其他「踏腳石題目」在長預算／多輪下的合成。一旦剝光 `comb` 又清空 P48 其餘 38 題，失去踏腳石的題目在 50k/4 輪內將全數未解（`bits=0`）。

3. **`[P1 嚴重｜演化失明]` 全剝 `comb` 使既有子代（`g1`）與算子類突變直接「基因失明」**
   - **問題**：方向 1 認為全剝 `comb` 後「`op status`／刪 `op` 突變在尺上失明（分數相同→不被選，無害）」。
   - **後果**：這一點都不無害：(1) 驗收 A5.3 要測「現成 `g1` 8 個子代」，但 `g1` 在 think-2 產生時包含針對 `comb` 的突變或權重／路由調整（外加 B1 提到 `X1/X3` 交配撞 sha），剝光 `comb` 後這些子代在副本上與親代**完全同構**（$\Delta=0, \sigma=0$）；(2) 若 `tree.json` 的 `route`/`weight` 仍指向被刪掉的 `comb` ID，未清理懸空引用（dangling refs）可能影響權重正規化（normalization）或引發 `check_root`／執行期異常。

---

### 二、`learn_bits` 公式與「只計 `test_ok`」是否合理？

4. **`[P0 致命｜資料洩漏＋斷崖效應]` 主分只計 `test_ok` 造成測試集洩漏（Test Leakage），且抹殺未過 `test` 的學習訊號**
   - **測試洩漏**：ARC 的 `test` 輸出是留出驗證（hold-out）用的，搜尋與 `judge` 晉升只看 `train` pair。若把 `test_ok` 當作演化挑選（`select.py`）的 `learn_bits` 過濾門，等於把 $L'$ 的 `test` 答案直接洩漏給 GA 當演化適應度。
   - **零分斷崖與介面漏欄**：對尚未解出（或 `train` 解出但 `test_ok=False`）的題目，分數一律為 `0`，毫無連續梯度（如 `near_score`）。此外，`01a` 指出 `test_ok` 在 `solutions.jsonl` 而非 `quick.py` 的 `per_task`，但 `02 A6` 的 `per_task` schema（`bits[], ntf[], solved[], first_epoch, seconds[]`）甚至**漏列 `test_ok[]`**，實作容易對錯欄位。

5. **`[P0 致命｜公式漏洞]` `learn_bits` 內含 $\log_2 B$，導致跨預算比較（如 `half-budget`）產生數學假象**
   - **問題**：公式 $\log_2 B - \log_2 \min(\text{ntf}_{t,e}, B)$ 中的基準 $B$ 若隨當次執行的 `L` 改變：
     - 當 `half-budget` 以 $L=25\text{k}$ 執行、親代以 $L=50\text{k}$ 執行時，任何在 $<25\text{k}$ 節點內解出的題目，由於決定論搜尋順序完全相同，其 `ntf` **一模一樣**，但公式卻因為 $\log_2(25\text{k}) - \log_2(50\text{k}) = -1$，每題每輪自動被扣 1 bit（4 輪扣 4 bits）！
     - 反之，若公式固定參考基準 $B_{\text{ref}}=50\text{k}$（只把搜尋截斷在 25k），則所有 $\text{ntf} \le 25\text{k}$ 的題目 $d_t = 0$，只有落在 $(25\text{k}, 50\text{k}]$ 的極少數邊緣題有差異（見下條，少於 4 題時 $z$ 永遠過不了 2）。

---

### 三、16 題 Bootstrap ＋ 兩半同號的顯著門是否夠？

6. **`[P0 致命｜數學盲區]` 在 16 題成對 Bootstrap 下，只要改變題數 $\le 3$ 題，數學上 $|z|$ 永遠不可能 $\ge 2$（必然假陰性）！**
   - **數學證明**：設 16 題中有 $k$ 題發生同向改變（設每題差值皆為 $c > 0$），其餘 $16-k$ 題不變（$d_t = 0$，例如未解或同 `ntf`）。有放回抽 16 題加總的母體標準差為 $\sigma = |c|\sqrt{16 \cdot \frac{k}{16} \cdot \frac{16-k}{16}} = |c|\sqrt{k(16-k)/16}$，總差 $\Delta = k c$，故：
     $$|z| = \frac{\Delta}{\sigma} = \sqrt{\frac{16k}{16-k}}$$
     - 當 $k=1$（新解出 1 題）：$|z| = \sqrt{16/15} \approx \mathbf{1.03} < 2$（且奇偶兩半必有一半為 0，不同號！）
     - 當 $k=2$（新解出 2 題）：$|z| = \sqrt{32/14} \approx \mathbf{1.51} < 2$
     - 當 $k=3$（新解出 3 題）：$|z| = \sqrt{48/13} \approx \mathbf{1.92} < 2$
   - **嚴重後果**：單刀突變或 `gate-dormant` 極可能只影響 1～3 道邊緣題（其餘題目全未解 $0=0$ 或秒解不變）。在 A4 規則下，**就算一棵樹真正學會並多解出 3 道大題（暴增 45 bits），$|z|$ 最大也只有 1.92，永遠被判「不顯著」**，量尺照樣分不開！

7. **`[P1 嚴重｜尺度無關假陽性]` 缺乏最小效應量門檻（$\Delta_{\min}$），5 題微幅雜訊即可假顯著，而全題等量改善卻判不顯著**
   - **無效應量下限**：因為 $z = \Delta / \sigma$ 具尺度不變性（scale-invariant），若某次權重微調沒有改變學習能力，僅因 tie-break 讓 5 道已解題的 `ntf` 各多花 5 個節點（例如從 4000 變成 4005，總共才差 $0.007$ bits），只要奇偶各分到 2～3 題，就有 $|z| \approx \sqrt{16 \times 5 / 11} \approx \mathbf{2.70} \ge 2$ 且兩半同號，立刻被誤判為「顯著」！
   - **$\sigma=0$ 邏輯顛倒**：若某改變讓 16 題每題剛好都減少 1 bit（$\Delta = -16, \sigma = 0$），訊噪比為 $\infty$，A4 卻因 $\sigma=0 \to z=\text{null}$ 判為「不顯著」。
   - **Bootstrap 不必要隨機性**：成對抽樣加總的標準差有精確閉式解 $\sigma_{\text{exact}} = \sqrt{\sum_{t=1}^N (d_t - \bar{d})^2}$。A4 用 `n_boot=2000` 隨機抽樣卻未鎖定 RNG seed，當 $|z| \approx 2.0$ 時重跑會隨機翻盤。

---

### 四、6 棵改笨樹的預期是否站得住？驗收能不能被「假綠」？

8. **`[P0 致命｜驗收假綠]` A5.2 只要求「6 改笨樹中 $\ge 3$ 棵通過」，可完全繞過唯一測學習的 `gate-dormant` 而假綠**
   - **為什麼會假綠**：6 棵改笨樹中：
     - `no-decomp`、`route-flat`、`weight-floor` 破壞的都是 **$e_0$ 靜態搜尋結構**（就算只跑 1 個 epoch 不做任何學習也會退步）；
     - `half-budget` 根本不是改樹，而是**直接砍尺的預算**（若用各自 $B$ 算分更是自動扣常數混分）；
     - 真正唯一隔離測試「跨輪晉升／學習能力」的只有 **`gate-dormant`**！
   - **假綠路徑**：只要 `no-decomp`、`route-flat`、`half-budget` 這 3 個靠 $e_0$ 靜態搜尋退步或預算截斷通過 $z \le -2$，就算 **`gate-dormant` 完全沒差（$\Delta=0$，代表尺根本沒量到跨輪學習）**，A5.2 依然「$\ge 3$ 棵通過」亮綠燈！此外，A5.2 只驗 `z <= -2`，完全沒驗 A3 表格寫的退步幅度（例如 `weight-floor` 就算只差 0.01% 也能混過）。

9. **`[P1 嚴重｜假陰性對照]` `judge-high` 修改程式根本不讀的欄位，只能測「決定論 $0=0$」，測不出假陽性率**
   - **問題**：`01a` 與 `02` 都明言 `judge.py:41` **根本沒讀 `new_solves_min`**，且快撥是決定論（$\sigma_{\text{rerun}}=0$）。
   - **後果**：改一個沒被讀取的 JSON 欄位，輸出必與親代位元組 100% 相同（全題 $d_t = 0$）。這只相當於跑 `compare(parent, parent)`，完全無法檢驗量尺對「無關擾動（neutral perturbation，如打亂同權重算子順序）」是否會產生假陽性。

10. **`[P1 嚴重｜驗收假綠]` A5.3（`g1` 8 子代至少 1 個 $|z|\ge 2$）只看絕對值且無效應量門檻，加上 A2 挑預算存在先看答案（Data Snooping）**
    - A5.3 沒限制方向也沒限制 $|\Delta_{\text{bits}}|$ 下限，只要 8 子代中有 1 個因動到靜態權重讓 4～5 題慢了幾個節點，就會以 $|z|\ge 2$ 假綠過關。
    - A2 預算選擇直接拿驗收用的「親代＋6 改笨樹」跑 C25/4 與 C50/4，挑「分出較多棵」的那組直接當 A5.2 驗收結果，屬於在同組測試集上挑超參數。

---

### 五、多程序並行風險與實作漏洞

11. **`[P0 致命｜並行撞檔]` 以 `ws/evo/meter/<genome_sha>/` 為目錄，在 `half-budget`、6 改笨樹、重跑自檢與 `g1` 重複 sha 時必相撞**
    - **問題**：A2 設計 `meter-batch --jobs 4` 每體目錄為 `ws/evo/meter/<genome_sha>/`。但：
      1. `01` 限制 D20 規定「個體身分只認 `genome_sha`（改 born/by 會讓快撥崩）」，而 A3 的 6 棵改笨樹是直接改副本（或 `half-budget` 直接拿親代改參數 `L=25k`），其 `tree.json` 內的 `genome_sha` **全都是親代的 `genome_sha`**！
      2. A5.1 要求親代重跑 2 次自檢（同 `genome_sha`）。
      3. `g1` 子代中已知有 `X1`、`X3` 與親代同 `genome_sha`。
    - **後果**：`meter-batch --jobs 4` 並行時，多個工作會同時讀寫同一個 `ws/evo/meter/<parent_sha>/`（及其 `quick.json`、`quarantine_P.json`），造成競態覆寫與崩潰！此外需注意 `quick` 是寫在 **`root.parent`**，若傳給 `quick` 的 `root` 是 `ws/evo/meter/<id>`，則 `root.parent` 是共用的 `ws/evo/meter/`，仍會全撞在一起（必須是 `ws/evo/meter/<run_id>/root`）。

12. **`[P1 嚴重｜耗時失算]` 剝庫＋`threads=1`＋C50/4 單體耗時將突破 100–150 秒，直接撞紅 A5.1（$\le 60\text{s}$）**
    - **問題**：`01a` 實測 C50 在 **`threads=4`** 且**有 5 題靠庫存早期秒解**時就要 **35 秒**。
    - **後果**：A2 改為 **剝光庫存**（未解題全部跑滿 50k 節點 × 4 輪）且把每程序降為 **`threads=1`**（少 4 倍執行緒），外加 4 程序並行爭搶記憶體頻寬與 L3 cache，單體 wall time 必然從 35 秒暴增至 **100～150 秒以上**，A5.1 的 `wall ≤ 60 s` 必紅。

13. **`[P2 中度｜塊 B/C 漏洞]` 交配重抽失敗後的缺額未定義、D18 樣本數過小、Janet 往返位元組相同忽略 JSON 正規化**
    - **塊 B1**：`crossover` 重抽 5 次仍撞 sha 時回傳 `collapsed=true`，但未規定 `ga.py` 如何補齊該子代名額（若直接保留則違反「無子代 sha 等於親代」驗收；若丟棄則族群縮水；應 fallback 轉 `mutate`）。
    - **塊 B3**：1 代僅 4 guided vs 4 uniform（$n=4$），個體間突變隨機性極大，直接用成對題集 $|z|\ge 2$ 判生死容易受單一極端突變誤導。
    - **塊 C1**：Janet 的 `nil`/`null` 轉換、table 無序性與浮點數格式，若未強制經過 canonical JSON（排序 key、固定縮排與 float 格式），`tree.json -> .janet -> tree.json` 不可能「位元組相同」。

---

## (B) 提案：具體可落地的修正方案（8 條）

1. **`[修主分與剝庫]` 改為「只剝命中題庫存（Targeted Strip）」並將主分拆為「跨輪學習增量 `learn_gain_bits`」與「首輪基底 `base_bits_e0`」**
   - **做法**：不剝光全部 `comb`（保留未被 $L'$ 在 $e_0$ 直接命中的基礎積木，讓踏腳石與 `op status`／權重突變仍有意義；只剝除親代在 $L'$ 上 $e_0$ 直接命中的那幾顆答案算子）。
   - **公式修正**：固定參考預算常數 $B_{\text{ref}} = 50000$，定義單題單輪位元 $b_{t,e} = \max(0, \log_2 B_{\text{ref}} - \log_2 \min(\text{ntf}_{t,e}, B_{\text{ref}}))$。將分數拆為：
     - **基底搜速**：$\text{base\_bits} = \sum_{t \in L'} b_{t,0}$
     - **跨輪學習增量**：$\text{learn\_gain} = \sum_{e=1}^{E-1} \sum_{t \in L'} (b_{t,e} - b_{t,0})$
     - **綜合主分**：$\text{learn\_bits} = \text{base\_bits} + w_{\text{gain}} \cdot \text{learn\_gain}$（設 $w_{\text{gain}} = 2 \sim 3$ 放大跨輪改善權重），徹底杜絕 $e_0$ 靜態搜尋獨霸總分。

2. **`[防測試洩漏與斷崖]` 演化挑選只看 `train` 解（加 `near_score` 尾數），`test_ok` 僅作報表診斷門**
   - **做法**：`learn_bits` 計算以 `solved`（通過全部 `train` pairs）為準，對未解題加上連續輔助梯度 $\epsilon \cdot \text{near\_score}_{t,e}$（例如 $\epsilon = 0.5\text{ bit}$，上限不超過已解題最低分），消除全 0 斷崖。`test_ok` 從 `solutions.jsonl` 彙整進 `per_task.test_ok[]`，僅用於防止假解膨脹的「過擬合監控指標」，不直接餵給 `select.py`。

3. **`[修題集梯度]` $L'$ 改採「分層抽樣（Stratified Taskset）」而非全取最小 `ntf`**
   - **做法**：從活樹歷史紀錄中按難度分三層組合成 16～24 題：(a) **基底邊緣層 6 題**（$e_0$ 無庫存時 `ntf` 落在 $10\text{k} \sim 45\text{k}$ 的題，測搜尋排序靈敏度）；(b) **跨輪學會層 6～10 題**（活樹 $e_0$ 未解、但在 $e_1..e_8$ 靠新合成 `comb` 解出的題，加上其合成來源的踏腳石題，專門測學習曲線）；(c) **攻堅層 4 題**（`ntf` 落在 $45\text{k} \sim 80\text{k}$ 的高難邊緣題，測正向突破）。

4. **`[修顯著門]` 廢除隨機 Bootstrap，改用閉式精確 $t/z$ 搭配「最小效應量 $\Delta_{\min}$ ＋ 單題突破保底（Max-Task Fallback）」**
   - **做法**：
     1. 用閉式解 $\sigma = \sqrt{\sum_{t=1}^N (d_t - \bar{d})^2}$ 取代 `n_boot=2000` 隨機抽樣（消除重跑翻盤）；當 $\sigma = 0$ 且 $|\Delta| \ge \Delta_{\min}$ 時判為 **`significant = True`**（修正全題同幅改善卻判不顯著的 bug）。
     2. **雙軌顯著門（解決 $\le 3$ 題必死與微小雜訊假陽性）**：必須同時滿足 $|\Delta| \ge \Delta_{\min}$（例如 $\Delta_{\min} = 2.0\text{ bits}$，擋掉幾個節點的 tie-break 雜訊），且滿足以下任一：
        - **群體軌**：$|z| \ge 2.0$ 且奇偶兩半非零同號（$\Delta_{\text{odd}} \cdot \Delta_{\text{even}} > 0$，適用 $\ge 4$ 題改變）；
        - **突破軌（針對稀疏學習）**：新解題數 $|\Delta \text{solved}| \ge 1$（或單題 $|\Delta b_t| \ge 6.0\text{ bits}$ 即節點數快 $64\times$），且反方向退步總和 $< 0.5\text{ bit}$。

5. **`[防驗收假綠]` 將 `gate-dormant` 列為必過硬門檻、剔除 `half-budget` 混分、換掉假陰性對照**
   - **做法**：
     - 將 `half-budget` 移出「6 棵改笨樹」，改列為獨立的「量尺單調性自檢」（且必須固定 $B_{\text{ref}}=50\text{k}$ 算分）。
     - A5.2 改為：**`gate-dormant` 必須單獨顯著退步**（驗證真能量到跨輪晉升），且其餘 4 棵結構改笨樹（`no-decomp`、`route-flat`、`weight-floor`、外加一棵「刪除半數 `decomp`」）至少 2 棵顯著退步且退步百分比達標。
     - 陰性對照改為 **`route-tie-shuffle`**（僅將同優先權／dormant 節點在 JSON 中的排列順序對調，測試決定論搜尋在中性擾動下的假陽性基線），保留 `judge-high` 僅作單元測試。

6. **`[防並行撞檔與超時]` 工作目錄改用 `<run_id>` 雙層隔離，並行改為 `jobs=2, threads=2`**
   - **做法**：
     - 每個量分任務建立獨立雙層目錄 `ws/evo/meter/<run_id>/root/`（其中 `<run_id> = <recipe_or_slot>_<genome_sha[:8]>_<nonce>`），確保 `root.parent`（`ws/evo/meter/<run_id>/`）在重跑親代、`half-budget`、6 改笨樹與重複 sha 子代時**絕對不會撞檔**。
     - 將 `meter-batch` 預設改為 `--jobs 2 --threads 2`（總核心數仍為 4），單體執行時間可壓回 45～60 秒內，且降低 4 程序同時跑滿時的 cache 爭搶。

7. **`[補塊 B 交配與對照漏洞]` 交配撞 sha 超限時自動 fallback 為 `mutate`，D18 對照擴至 $8\text{ vs }8$**
   - **做法**：`crossover.py` 重抽 5 次仍與任一親代或 `seen` 撞 sha 時，標記 `collapsed_to_mutate=true` 並由 `ga.py` 自動呼叫一次 `mutate(parent)` 補齊名額，確保一代 8 子代皆為全新 `genome_sha`。D18 引導 vs 均勻對照改跑 2 代或單代 $8\text{ guided} + 8\text{ uniform}$，以 Mann-Whitney U 或雙樣本置換檢定（permutation test）比較個體分數分佈。

8. **`[固塊 C 往返驗證]` Janet 轉換強制經 Canonical JSON 正規化，並避開 `nil` 吞鍵陷阱**
   - **做法**：`sexpr.py` 在 `tree.json -> .janet -> tree.json` 寫回時，統一使用 `json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)` 並正規化浮點數（如 `round(v, 6)`）；Janet 側解析 JSON 時明確指定 `:null :null` 關鍵字而非 `nil`（避免 Janet table 遇到 `nil` 自動刪除 key），確保 `genome_sha` 與位元組 100% 往返一致。
