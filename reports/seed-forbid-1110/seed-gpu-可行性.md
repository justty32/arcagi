# seed 列舉搬 GPU：可行性評估（只評估，未實作）

對象：`native/src/seed_enum.cpp` 的 `Enumerator`（bottom-up、按大小分層、觀測等價去重）。數字出自本目錄 `report.md` 的量測（training 前 100 題、4 執行緒）。

## 現況：CPU 一個節點要做什麼

每個候選（`emit`）＝
1. **組合**：`choose` 遞迴枚舉 (op, 大小切分, 每個子位置的 bank 項目)，含型別 unify（`Subst` 複製）。
2. **求值**：原語走 `eval_prim`，對 n 個 train 例逐一 `apply_prim`；子值直接從 `flat[entry.voff + j]` 取，是 64-bit handle。list 結果要 `Store::make`（hash-cons：配置＋雜湊＋查表；r09 量到約 37% 熱點）。帶 lambda 的高階原語（map/filter/fold/zipwith）在 `eval` 裡逐元素跑小直譯器。
3. **去重**：`seen_insert` 用 (型別, n 個 handle) 雜湊開址表；因為 list 已 hash-cons，比較只比 handle。
4. **命中檢查**：跟 `sp.outs` 比 handle。

吞吐：約 2.4–3.8M 節點／秒／執行緒（預算 100k–1M）；預算 1M 時 100 題總共 9,257 萬節點約 36 task-秒。

## 哪段能搬

| 部分 | 適合 GPU？ | 理由 |
|---|---|---|
| 一階原語在 int／bool 上（add、eq、lt、not、len、head…） | 很適合 | 純 SIMT：每執行緒一個 (子 i, 子 j) 對 × n 例，查兩個 handle 陣列、算、寫。 |
| 一階原語產 list／grid（reverse、sort、transpose、take、concat…） | 可以，但要換值佈局 | CPU 靠 hash-cons 的 handle；GPU 上要嘛定長槽（list ≤30、grid ≤30×30），要嘛先算雜湊再只對新值物化。 |
| 去重＋命中 | 適合 | (型別, n 個值雜湊) → 64-bit 指紋，GPU 開址雜湊表（warp 協作插入）；命中＝指紋等於 outs 指紋後再 CPU 精確比。 |
| 組合枚舉（choose） | 可以展平 | 每層 (op, 切分) 的候選數＝各子位置 bank 大小乘積，可用前綴和把全域執行緒 id 映到 (i, j)。型別 unify 先在 CPU 對「型別桶」做，GPU 只見同型桶。 |
| lambda 高階原語、block 展開、cond_witness | 不適合（先留 CPU） | 逐元素直譯、深度不定、要 `Arena`；分歧大。 |

## 建議資料佈局

- **值**：每個 bank 項目對 n 個例子各存一個 64-bit 指紋＋（若是 list）一個指向 GPU 值池的偏移；值池用 SoA 定長槽：`int8 cells[slot][900]`、`uint8 h, w`。ARC 值域小（顏色 0–9、長度 ≤30），int8 足夠。
- **bank**：按 (大小, 型別) 分桶，每桶連續陣列；新一層由 kernel 產出後 stream-compact 接到尾端（跟 N2 `gpusearch` 的前綴緩衝同一招）。
- **去重表**：全域 GPU 雜湊表放指紋；寫入勝者才物化值、才進 bank（避免為重複值配置槽）。

## 預估加速

- 一階 int／bool 層：每候選 n×幾個整數運算，GPU 對 4 執行緒 CPU 估 30–100 倍（參考：N2 格子步驟雛形在 grid 程式上量到 GPU 對 6 執行緒 CPU 45–105 倍，`reports/native-cuda-1109/prototype.md`；seed 的 int／bool 運算比 grid 步驟輕，比例應不低於此）。
- list／grid 層：受記憶體頻寬限制，一個 grid 候選讀寫約 1–2 KB；RTX 5060 Ti 帳面約 448 GB/s，隨機存取打折後估 10⁷–10⁸ 候選／秒，對 4 執行緒 CPU（約 10⁷）約 3–10 倍。
- 整體受 Amdahl 限制：lambda 類原語在 seed 的解裡佔比高（map／zip_pos 是主要分解），若它們留在 CPU，整體加速可能只有 2–4 倍。要大加速得把「lambda 體池（BodyPool）× 元素」也做成定長 kernel——等於另寫一個小 GPU 直譯器，是 N2 雛形之外的另一個大工程。

## forbid 跟 GPU 的關係

forbid 是根樣式比對，GPU 上可以在組合階段用「(op, 子項目的頭符號) 查表」便宜地做，但本次量測顯示它只擋 0.6–3% 候選（見 `report.md`），對 GPU 版不是關鍵。GPU 版真正的價值是把「生成＋求值＋雜湊」這段整個並行化，而那段正是 forbid 想省、卻只能省很小一角的部分。

## 若要起頭，最小可驗的一步

只做「大小 2–3、一階原語、輸入是 grid」的一層：CPU 給 bank（大小 1–2 的值池）、GPU 生成＋求值＋指紋＋去重，回傳新項目；跟 CPU `Enumerator` 同層比對 (指紋集合相等、節點數相等)。驗收：同層集合一致＋吞吐比。
