# N8c：一階評估與高階函式迴圈的結構性浪費（假說＋選一項實作 arcbatch-hot-e）

依據 [n8b.md](n8b.md) 1e7 剖面（FO 28.3% / HO loop rest 24.7% / HO lambda body 23.4% / HO build 10.1%）。
注意：剖面是 rdtsc 巢狀 scope，FO 6.25e9 次、HO body 1.38e10 次這類極小 scope 被計時本身墊高，
真實占比估計要打折（FO 估實際 ~20%）。

## 讀到的熱路徑

- 候選評估 `native/hot/seed_enum.cpp:844-877` `eval_prim()`：bottom-up 列舉，每個候選 × 每個 train 範例 j
  各呼叫一次 `apply_prim(op.prim, a, cx)`，參數多半直接是 `flat[offsets[k]+j]`（HOT_B 已把 entry metadata 提到範例迴圈外）。
- `native/hot/seed_value.cpp:456` `apply_prim()`：~40 case 的大 switch、非 inline，開頭固定 `Store& S = store()`
  （函式內 thread_local，含初始化 guard）——連 ADD 也付這筆。
- 高階函式 `seed_value.cpp:571-655`：每元素 `call()`（:668，`arena()` TLS、A 快取 hash+查表、兩次 `store().off.size()`）
  → `eval()`（:705）樹走訪：每個節點一次遞迴呼叫、`arena()` TLS、拷貝 24 B CNode；葉節點（CONST/VAR/INPUT）也走完整函式呼叫。
- 早停：`eval_prim` 遇 ERR 已立即 return false；`emit()`（seed_enum.cpp:824）ok 才 offer。早停不是問題。

## 三條假說

| # | 假說 | 位置 | 預估可省（1e7 牆鐘） |
|---|---|---|---:|
| H1 | **FO 逐範例分派**：無 lambda 參數的純量 prim，每範例重付「非 inline 呼叫＋大 switch＋store() TLS guard＋Ctx 建構＋steps 累加」。把 switch 提到範例迴圈外，每 prim 一個讀 `flat` 連續段的緊迴圈（批次化 train 範例）。 | seed_enum.cpp:856-874、seed_value.cpp:456-470 | 4–8% |
| H2 | **lambda body 葉節點遞迴**：`eval()` 對 CONST/VAR/INPUT 子節點也做完整遞迴呼叫＋`arena()` TLS＋CNode 拷貝；body 很小（lam_body_max），子節點多是葉。kid 迴圈內就地解葉、`Arena&` 由 call() 傳入。 | seed_value.cpp:705-723、:668-702 | 3–7% |
| H3 | **TLS accessor 重複取**：`store()`/`arena()` 每元素、每節點重取（HO 迴圈內 `S.data(a[1])[i]` 每次重算 `elems.data()+off[lid]`）。改傳參考／迴圈前快取基底指標（Store 可能在 body 內長大，需每次 make 後重取）。 | seed_value.cpp:571-655、:668 | 1–3% |

（結果快取 A/C、緩衝重用 D 已在 N8/N8b 量過，不再列。）

## 選定：H1（交 codex 實作 `arcbatch-hot-e`，`-DHOT_A -DHOT_B -DHOT_E`）

理由：
1. 直接打 28% 那一桶，且呼叫數最大（6.25e9）；每次實際工作（如 ADD）只有幾條指令，固定開銷占比最高。
2. 精確性最容易保證：無 lambda 參數時 `cx.steps` 不變、`steps` 累加 0，純量 prim 不碰 Store 寫入，
   批次後結果、ERR 早停位置、Store 狀態與 eval_steps 逐一相同；配置清單與 HO prim 原路不動。
3. H2 牽涉 eval 遞迴與 A 快取的 steps 記帳，改錯風險較高；H3 預估太小、可能過不了 2% 門檻。

任務書：scratchpad `n8c/codex-task.md`；實作回報：[n8c-impl.md](n8c-impl.md)（codex 寫）。

## 結果

（跑中，見 [n8c-progress.md](n8c-progress.md)；收結果後補表與判讀。）
