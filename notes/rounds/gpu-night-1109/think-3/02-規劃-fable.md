# think-3 規劃（fable）：GPU 下一步押哪裡才能讓 aos 樹搜得更快

← [01-簡報](01-簡報.md)｜數字出處見簡報括號；本檔另查了 `reports/seed-gpu-1110/report.md`、`reports/seed-gpu-e2e-1110/progress.md`、`reports/task-features-1109/progress.md`、`native/src/seed_*`、`notes/rounds/總表/使用者方向.md`。

## ELI5 結論

今晚的數據說：顯卡算得再快，seed 搜樹整體最多快 1.35 倍（74% 的時間花在顯卡還不會算的 map／if／library），而且搜樹是指數問題——算力快 10 倍只多走半層，但**每層少試 20% 的爛選項，六層就省 3.8 倍**，而且會跟任何算力加速相乘。所以這輪 GPU 不進 seed 內圈硬拼 kernel，先做三件便宜事：(1) 一個工作段把那 74% 拆清楚、量出「到解節點數」基線；(2) 用 seed 自己的解題軌跡學一個**通用的原語先驅（排序＋預算分攤，不丟候選）**，看到解節點數掉多少；(3) bank 常駐只當低風險小修，讓 `--gpu-seed` 至少不輸 CPU。lambda kernel 設數字門檻、GP 修 holdout 這輪不做。N2 的 ARC 專屬窮舉保留為工具與剖面產生器，不進起點樹。

## 四方向比較

搜樹速度＝同預算下「到解節點數」或 wall；或固定秒數下 test 對題數。Amdahl：$S=1/((1-f)+f/s)$，f＝可搬上 GPU 的時間占比，s＝該段加速倍數。

| 方向 | 預期搜樹速度收益（估算與依據） | 工時 | 風險 | 與「起點樹不含 ARC 知識」相容性 |
|---|---|---|---|---|
| 1 lambda kernel（map/zipwith/filter/fold/if 上 GPU） | 1e6 預算：f＝一階 26%＋lambda 類未知份額。假設評估合計 f≈0.7、s＝10～30 → S≈2.7～3.1×；f＝0.8、s＝30 → 4.4×。層數換算：N5b 每層節點成長 2.3～40×，3× ≈ 多走 0.3～0.5 層。1e6 時多數層太小（0.13～7×），實際更低；1e7 才接近上限。library（任意子樹）不搬則 f 再打折。 | **大**（lambda 本體要在 kernel 內解釋；不定長值 concat/range/repeat 今天也被排除；if 分支發散；等同 think-2 D6 否決的 `native/gpu/ast/`） | 高：e2e 已是 0.43×；可能做完 ≤2× 卻吃掉整輪；正確性對帳量大 | **高**（seed 是通用層） |
| 2 bank 常駐＋增量上傳＋跨子題／跨題合併 launch | 只殺開銷：100 題 1e6 中 GPU 模式多付 ~10～12 s（21.1 vs 9.1 s 中位），每層 27 ms 上傳＋14 ms launch。做完約回到 CPU 持平（`--gpu-min 200000` 今天已持平 9.1 s），再往上受 1.35× 牆。純收益 ≤1.35×、1e7 可能 1.2×。 | 小～中 | 低；但單獨做收益小，主要是方向 1 的前置 | **高** |
| 3 換戰場：GPU 不進內圈，(a) 大批評估、(b) 題目剖面、(c) 剖面訓練排序器／剪枝器 | (c) 是唯一「跟深度相乘」的槓桿：每層有效分支數 b→0.8b，深度 6 → 1/0.8⁶≈3.8×；b→0.5b → 32×（軟排序只在命中層省，約一半；預算分攤才會壓全程）。(b) 作「題目路由器／預算分配」：固定總秒數下多解幾題，依 N4 近似分數曲線分錢。(a) N2 型大批評估對 aos 樹速度無直接貢獻。 | (c) 中、(b) 小～中、(a) 已完成 | 中：seed 1e6 只解 train_ok 7/100，訓練料薄；先驅可能無訊號；硬剪枝會失完備 | (c) **高**（學到的先驅是優化器自己長出的，特徵只用原語 id／型別／深度／值形狀，不用格子語意）；(b)(a) 低（N2 字母表、顏色物件特徵）→ 只當工具／對照組 |
| 4 GP 加 holdout／MDL | 修的是**正確性**不是速度：GP 吞吐比窮舉慢近 2 個數量級，在窮舉夠得到的深度必輸；修好 test 1/7 後能否在深度 >6 贏窮舉未知。對本輪判準收益≈0。 | 小（holdout）～中（MDL 調參＋重跑） | 低工程風險、高「做了也沒速度回報」風險 | 低：N3 GP 吃 N2 字母表。使用者建議 1 的「GP 演化整棵 aos 樹（Janet 表示）」才是相容版本，屬另一輪設計 |

## 方向題

**Q1 GPU 這輪押 seed 內圈（1＋2）還是外圈（3）？**
選項：A 內圈 kernel 全上；B 外圈為主、內圈只做 bank 常駐；C 全部外圈。
**推薦 B。** 選：排序器收益跟任何未來 kernel 加速相乘，且不依賴 GPU 空檔；bank 常駐讓 `--gpu-seed` 不再是負資產。不選（選 A）：整輪賭一個上限 ~3× 的工程，1e6 預算下可能連 2× 都看不到。

**Q2 排序器訓練料用 N4 features.csv（N2 字母表）還是 seed 自己的軌跡？**
選項：A N4；B seed 軌跡（`native/tools/seed_record.py`＋`--seed-prof`）；C 兩者混。
**推薦 B，N4 料只拿去做題目路由器。** 選：先驅直接作用在 seed 的原語×型別桶，不需跨字母表翻譯，也不把 rot180/fill_enclosed 的知識帶進起點樹。不選（選 A）：N2 的 prim_* 頻率對 seed 的 map/zipwith/lib 沒有對應，等於學了個用不上的先驅。

**Q3 先驅怎麼用：軟排序（保完備）還是硬剪枝（丟候選）？**
選項：A 只排序；B 排序＋每層按先驅分攤節點預算（候選不丟，只延後）；C 硬剪枝。
**推薦 B。** 選：解集合只會「更早到」不會變少，可用「0 mismatch 或更多解」直接驗；預算分攤才能壓全程而非只壓命中層。不選（選 C）：到解節點數可能掉更多，但沒基線前無法分辨「剪掉爛的」與「剪掉解」，且與 N5 forbid 教訓同型（語法層剪枝幾乎無收益）。

**Q4 N2 的 ARC 專屬 GPU 窮舉之後是什麼身分？**
選項：A 繼續加原語衝解題數；B 凍結字母表，當對照組＋剖面產生器＋路由器資料源；C 棄用。
**推薦 B。** 選：符合「純解題長跑只當題目特性採集」原話，也不違反起點樹約束（它不是起點樹）。不選（選 A）：解題數上去但與 aos 樹速度無關，是使用者點名的「空轉」。

**Q5 lambda kernel 的開工門檻？**
選項：A 不設門檻直接做；B 設數字門檻：1e7 `--seed-prof` 顯示 map＋zipwith＋if 評估占 Enumerator 時間 ≥50% 且 host 簿記（choose／unify／hash-cons／建樹）≤25%，且排序器線已達「繼續門檻」或停手；C 永不做。
**推薦 B，開工也只做 map/zipwith 帶一階 body，不做 library／filter／fold。** 選：Amdahl 上限至少 ≥2.7× 才值得大工時。不選（選 A）：重演 N5c——對帳全對、e2e 更慢。

## 推薦路線

順序：**M0 量 → R1 排序器（主線）→ B1 bank 常駐（小修）→ T1 路由器（次線）→ L1 lambda kernel（門檻制）**。M0 與 B1 可同天；R1 是本輪主投入。

### M0 量基線（1 個工作段，無 GPU 需求）
- 模組：`native/src/seed_enum.cpp`（只讀 `--seed-prof` 輸出）、`native/tools/seed_record.py`、`reports/seed-gpu-e2e-1110/`（N5c 1e7 晨報）。
- 量法：training 前 100（`scratchpad/n5c/train100.txt`），`native/bin/arcbatch --mode seed`，4 緒，1e6 與 1e7，3 次取中位：wall、nodes/s、train_ok/test_ok、**每解題的 eval_steps（到解節點數）中位**。`--seed-prof` 1e7 一次：把 74% 拆成 map／zipwith／if／lib／filter-fold／host 簿記六桶（簡報 §6 第 1 點未解）。
- 門檻：這是量，不設門檻；產出一張六桶表＋到解節點數分佈，寫進 `reports/seed-ranker-1110/baseline.md`（新夾，由施工者建）。

### R1 seed 通用先驅排序器（主線，中工時）
- 模組：新 `native/src/seed_prior.{hpp,cpp}`（或 `native/tools/seed_prior.py` 離線學＋`seed_enum.cpp` 讀一張表）；訓練料來自 `seed_record.py` 的已解程式（training＋evaluation 都跑，**驗以 evaluation 為準**，避 re-arc 洩漏）。
- 先驅形式：P(原語 | 回傳型別桶, 深度) 與 P(子項型別桶 | 原語)，以 leave-one-task-out 統計（加一平滑）。特徵只允許：原語 id、型別、深度、子項大小；**不允許**格子語意（顏色、物件、對稱）。
- 用法：每層先按先驅排 job 順序（命中早停受益），再按先驅比例分攤該層節點預算（低先驅 job 延到下一輪補齊，不丟）。
- 量法：同 M0 基準；主指標＝已解集合的「到解節點數」中位比（ranked／base）；副指標＝solved@1e6、test_ok、wall 增幅、解集合 mismatch（必須 0 或變多）。
- 門檻：**繼續**＝到解節點中位 ≤0.5× 且 solved@1e6 ≥ 基線、wall 開銷 ≤5%；**停手**＝兩次迭代後仍 >0.8×，或 evaluation 上 test_ok 下降。

### B1 bank 常駐（小修，與 M0 同天）
- 模組：`native/gpu/seed/e2e_kernel.cu`、`e2e.hpp`、`seed_enum_gpu.cpp`：bank 留顯存、每層只傳新 entry、分解子題共用父 bank；小層 warp 協作雜湊（N5b 已知限制）。
- 量法：N5c 的 `bench.sh` 1e6／1e7 三模式中位（cpu／gpu／gpuhi），0 mismatch。
- 門檻：**繼續**＝gpu 模式 1e6 wall ≤ cpu（持平）、1e7 ≥1.2×；**停手**＝做完仍 <1.0×，則把 `--gpu-seed` 預設改 `--gpu-min 200000` 凍結。

### T1 題目路由器（次線，小～中）
- 模組：`reports/task-features-1109/features.csv`（晨報後有）＋`native/tools/profile_features.py`；新 `native/tools/gate_select.py` 延伸（已存在）→ 用近似分數曲線（best_d1..d6 斜率）決定每題配多少 GPU／CPU 秒。
- 量法：800 題固定總秒數，比「均分」vs「路由」的 test 對題數（**test 對題數 vs GPU 秒曲線**，N3 報告建議的格式）。
- 門檻：**繼續**＝同秒數多解 ≥10%；**停手**＝<5%。它是 ARC 專屬工具，不進起點樹，與 Q4 一致。

### L1 lambda kernel（門檻制，大）
- 只在 Q5 門檻達成後開；範圍限 `map`／`zipwith` 帶一階 body（body 就是 bank 中函式型 entry，kernel 內查表求值），`native/gpu/seed/` 內做，不開 `native/gpu/ast/`。
- 量法：N5b 式逐層對帳 0 mismatch ＋ N5c 式 e2e 1e7 中位。
- 門檻：**繼續**＝e2e 1e7 ≥1.5×；**停手**＝<1.2× 或對帳有 mismatch 兩天未清。

## 這輪不做

- **lambda kernel 直接開工**：Amdahl 上限 ~3×、1e6 下更低、工時最大、think-2 D6 已否決同型；改為門檻制 L1。
- **GP holdout／MDL**：改正確性不改速度；N3 GP 字母表是 N2 的，與起點樹不相容。cheap 的 holdout 可當別輪 N3 收尾，不佔本輪。使用者建議 1「GP 演化 aos 樹（Janet）」另立設計輪。
- **N2 加原語／衝深度 8**：解題數上升但與判準無關；凍結字母表只當剖面源。
- **硬剪枝器／神經排序器**：沒有到解節點數基線前，分不清剪掉的是爛候選還是解；小網路排序器等 R1 統計先驅有訊號再談（也符合「盡量不用神經網路」）。
- **語法樣式剪枝再加**：N5 已證明在觀測等價去重上無收益。

## 給 Argon 的審查重點

1. **74% 的成分**：我假設其中評估占多數（f≈0.7～0.8）。若 host 簿記（choose 遞迴、unify、hash-cons、建 PP 樹）其實 >40%，lambda kernel 上限 <2×，我的「外圈優先」更穩；若評估 ≈90%，上限升到 6×＋，L1 應提前。M0 的六桶表是裁決點，請審「門檻 ≥50%／≤25%」訂得合理否。
2. **排序器收益估算**：「b→0.8b 六層 3.8×」假設先驅能跨題泛化，而 seed 1e6 只解 7/100，訓練料極薄；leave-one-task-out 可能幾乎無訊號。請審是否該先用 1e7 或合成題擴充已解集合再學。
3. **軟排序只在命中層省**：seed 命中即停、但有分解子題與 library 增長，實際省幅可能遠低於估算；預算分攤「延後不丟」在 BFS bank 下是否真能壓全程，我沒有實測依據。
4. **N4 料對 seed 無用的假設**：我判 N2 字母表的 prim_* 頻率對 seed 無對應，只能做路由器；若 Argon 認為近似分數曲線本身（與字母表無關）可當 seed 的題目難度先驅，T1 與 R1 可合併。
5. **「能用 GPU 就用」vs 本輪 GPU 幾乎只做剖面**：路線把 GPU 留在 B1 小修與 N2/N4 長跑，seed 內圈短期不吃 GPU。這與使用者 11-09 晚「兩個都試試看、不用降低負載」是否衝突，請審是否該把 L1 門檻放寬或改成並行小探針（如只做 `map` 一個原語的 kernel 量 f）。
