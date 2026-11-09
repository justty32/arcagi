# think-6 02 規劃（fable）：GPU 窮舉當主線候選來源，下一步

← [01 簡報](01-簡報.md)｜[代定清單](代定清單.md)。只規劃，不畫圖紙、不施工。基準：主線 training 147／evaluation 56；N4f 補位線 149／58。所有門檻只在 training 選，evaluation 只審計（D-r7-18／D-r8-21）。

## 0. ELI5 結論

GPU 17 原語在未解題上能挖的，N4f 已經挖走大半（training +2、eval +2）。再往下走，**推薦 B（不冗餘門）先做、A（定向深搜 d6 → d7，只對 13 題）當唯一一次 GPU 實驗、D（CPU 提早停型繼續加深）並行當對照；C（GPU prefix 當主線 seeds）封存到 A 過閘再談**。預期全部做完：**training +0～1、evaluation +0～1（審計），兩 split 合計 0～2**；最可能的結果是 training +0 但假解從 3 降到 ≤1。若 A 閘門不過，GPU 補位線就此封存，資源回主線。

## 1. 方案

### A. 定向深搜 d6–d7（母體 13 題：gain>0.05 且 d2 後 best 仍上升；01 §1c）
- 做什麼：對 `features.csv` 篩出的 13 題（train 5、eval 8）用 gpusearch 跑 d6，每題預算 10×（200 s）；d6 best 比 d5 有進步的題再跑 d7。輸出格式同 phase-A（`best.program`／`samples`），直接丟進 `reports/gpu-fallback-1110/replay.py` 的 SOURCES 重放，**必須與 B 的門一起接**。另取 gain>0.05 但 d1 就到頂的 6 題（train 2、eval 4）當對照組，驗證「d2 後上升」是不是有效篩子。
- 成本：GPU 13×200 s ≈ 45 min（d7 再 +30 min 以內）；CPU 重放數分鐘；工時 2–3 h（篩題、排程、重放）。
- 預期：training 0～1、evaluation 0～1。
- 硬判準（training）：新增 train 全對 ≥1 **且** test 對 ≥1、新增假解 ≤1、與主線衝突 =0、149 不降。evaluation 只記錄 58 變多少、假解幾題。
- 失敗怎麼停：d6 跑完 13 題沒有任何新增 train 全對（轉換率 <1/13）→ 不跑 d7，封存；有全對但 test 全錯且 B 擋不住 → 封存。

### B. 補位候選加「不冗餘」門
- 做什麼：在 `load_gpu_programs`（載入端，來源不可知）加程式級過濾，R1 門（table+unseen）保留不動。候選規則（每條單獨開關、在 training 上逐條量）：(1) 相鄰兩步同原語**且同參數**；(2) 抵消對：tile→downscale／upscale→downscale 回到原尺寸、flip×2、rot 累積 360°；(3) colormap 步數 ≥2 或 colormap 非尾步；(4) 等價正規化後有更短程式過 train 則取短。目標：擋 N4g 的 25d8a9c8（upscale×2、split_overlay×2、尾 colormap）、1fad071e（tile>downscale 抵消）、f8ff0b80（需先看程式）；**不得**擋 a79310a0、46f33fce。注意 66e6c45b（eval 對）是 gravity>gravity——規則 (1) 必須看參數，否則 eval 審計會掉 1 題，而且不能據此回調。
- 成本：GPU 0；CPU 重放 19 檔合併 ×2 split ≈ 10 min；工時 2–4 h。
- 預期：training 新增對 0（它是精度門）；價值在假解 3→≤1、讓 A／C 的來源能安全擴大。
- 硬判準（training，19 檔合併設定）：149 不降、假解 ≤1（原 3）、衝突 =0；只用 phase-A 設定也不得掉題。evaluation 審計：58 與假解 1 記錄即可。
- 失敗怎麼停：任一規則組合都做不到「149 不降且假解 ≤1」→ 只保留不傷 149 的規則，其餘寫進代定清單；A／C 不開。

### C. GPU top 程式／prefix 當主線 `seeds`
- 做什麼：`native/src/search.cpp` 已有 seeds（program＋prefix 後的 train/test grids，從 seed 深度起 dfs）。把 phase-A／A 的 top-k（含未全對 prefix，k≤3）轉成 seeds JSON，max_depth 需提到 seed 深度+2；seeded 解已標 `origin:"seed"`，一律再過 R1 門。母體：§1d 的 19 題非全對。
- 成本：GPU 0（用既有輸出）；CPU 19 題 ×60 s ×k ≈ 1 h；工時 6–8 h（grids 匯出、JSON 對接、max_depth 與 learners 互動）。
- 預期：training 0～1、evaluation 0～1；**記表假解風險最高**（prefix 之後 local_rule／x_vrule 很容易湊出過 train 解）。
- 硬判準（training）：新增對 ≥1、新增假解 ≤1、衝突 =0；seeded 解若 test 錯比例 >50% 直接停。
- 失敗怎麼停：A 沒產生新 train 全對 → 不開 C；C 跑完新增對 =0 → 封存。

### D. CPU 對照：提早停型繼續加深（01 §3）
- 做什麼：`search.cpp` `run()` 的 `if (!solutions.empty() || stopped) break;` 改成「該層只有記表解（local_rule／x_vrule）且預算未盡則繼續加深」；先只對 trace 裡 out_of_budget=False 的 13（train）／8（eval）題重跑，再跑 training 全 400 回歸。
- 成本：GPU 0；CPU 21×60 s ≈ 20 min＋全 400 回歸 ≈ 80 min；工時 2–3 h。
- 預期：training 0～1、evaluation 0～1（a79310a0 已被 N4f 拿走，對它的增量是 0）。
- 硬判準（training）：13 題中新增對 ≥1、假解 ≤1、全 400 回歸 147 不降、衝突 =0。
- 失敗怎麼停：13 題全無新增對 → 回滾，記錄「提早停型不是漏題主因」。

## 2. 推薦路線（閘門式）

1. **閘 0：B**。CPU 數分鐘、零 GPU；不過閘就別擴來源。並行起 **D**（獨立於 GPU，可同時做）。
2. **閘 1：A d6 on 13 題**（+6 題對照）。B 的門接著。沒有新增 train 全對 → 封存 GPU 補位線，本輪結束。
3. **閘 2：A d7**（只對 d6 有進步的題）。
4. **閘 3：C**。只在 A 有 ≥1 個新增 train 全對、且 B 擋住了新假解時才開。
5. 全程 evaluation 只審計：每閘記「58 變多少、假解幾題」，不回頭調門。

## 3. 方向題（≤5）

1. A 的母體取 13、19 還是 47？**推薦 13＋6 對照**。47 裡有 34 題 gain 在 0.001–0.05 之間，幾乎是原樣輸出，深搜只會湊寫死顏色的假解；取 19 可接受但 GPU 時間 ×1.5 且期望值幾乎不變。
2. 門放在載入端還是 `gated.gpu_fallback` 接受端？**推薦載入端**（`load_gpu_programs`）。後果：gated.py 邏輯不動、重放即可驗證；缺點是門看不到 R1 的 table/unseen 資訊，純程式級。
3. 不冗餘規則「同原語連續」是否看參數？**必須看**。不看會砍掉 66e6c45b（gravity>gravity，eval 對），且 eval 掉題不得用來回調，等於白賠 1 題。
4. C 要不要在本輪排進去？**推薦封存到閘 3**。工時最高（6–8 h）、記表假解風險最高、期望值與 A 相同（0～1）。
5. 增量對哪條基準算？**推薦：衝突對主線 147／56 算、增量與假解對補位線 149／58 算**；兩者分開記，避免把 N4f 的 +2 重複算成新成果。

## 4. 對 01 數字的疑點

1. §1 說主線未解 training 253／evaluation 344，§3 的「放棄」只有 233／335，差 20／9 題沒交代（推測是主線給了錯答而非放棄）；這些題不在 §3 分型內，A／D 都沒覆蓋。
2. §2b 的轉換率 4%～25% 中，4% 來自 phase-B＋filler d6 的 122 題（未按 gain 篩），套到 gain>0.05 的 13～19 題上是鬆的類比；25% 沒有出處。區間「0.2～3.2 題」應視為量級而非估計。
3. 「每多 1 題對伴隨 1～4 題假解」只靠 d6 的 1/5 和 GP 的 0/3，n 太小；B 做完才有可靠數字。
4. features.csv 是 profile 跑法，46f33fce 卻來自 phase-A 非 profile——同 17 原語兩種跑法結果不同，表示 §1 的天花板可能略低估 phase-A／d6 的實際產出；但方向（很低）不變。
5. §3「提早停型多半是記表解佔層」只有 a79310a0 一個已驗證例，13／8 題的成因要 D 跑了才知道。
6. §1d 表頭寫「前 22」但 25 題名單少 3 題，且 2013d3e2 的 identity 0.045 顯示 gain 對「尺寸改變」題與「同尺寸」題意義不同，混在同一門檻下比較稍嫌粗。
