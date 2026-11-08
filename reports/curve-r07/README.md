# r07 學習曲線（B 線）

**結論**：量具、學習循環、G1／G4、元優化都跑通了，三條 8-pass 曲線也交了，但空樹 8 個 pass 一題都沒多學會。`AUC_L`：空樹 16、空樹＋G1＋G4 16（三 seed 全距 0）、舊樹 72。空樹 pass 0 只解 2 題（`68b16354`＝`reverse $in`、`beb8660c`＝`sort (map (λ sort $0) $in)`），這兩支程式沒有共用的子樹（大小 ≥2），MDL 省量最多只到 0，所以 **seedlib 0 顆積木**。G4 在 20k 節點內沒把任何近失敗補成過 train 的程式，三個 seed 的 curve 一字不差。meta 跑了 3 回合，3 回合都是 6→6 拒絕。量具分得出樹：舊樹 pass 0 L16 解 9 題（門檻 ≥4），空樹 2 題（門檻 ≤2）。`llm_calls` 全 0。

## 指令

```sh
uv run python scripts/r07_taskset.py          # data/r07/taskset.json, sha1 9ce7c7ea16bb…
R="nice -n 19 systemd-run --user --scope -q -p MemoryMax=8G uv run python scripts/r07_curve.py"
$R --tree empty                               # 純枚舉
$R --tree empty --out reports/curve-r07/empty-rerun   # 雙跑
for s in 0 1 2; do $R --tree empty-g1g4 --seed $s; done
$R --tree old                                 # 舊樹對照（唯讀呼叫 solvers.search）
$R --tree meta --rounds 3 --passes 4 --out reports/curve-r07/meta
```

- 程式：`src/arcagi/grow/`（`curve` pass 循環、`compress` G1、`evolve` G4、`sig` 型別簽名推導、`knobs`、`meta`、`oldtree`）；測試 `tests/grow/`。
- 跑的時候：base commit `328eec7`，seed 引擎＝A 線 `fe9b759`（`src/arcagi/seed/*.py` 內容 sha 跑前跑後一致），workers 6，每題每 pass 100k 節點（G1＋G4 樹＝80k 枚舉＋20k G4）。
- pass 0＝學習前的起點樹，pass 1～8 是學習 pass；`AUC_L = Σ_{pass=1..8} solved_L`。
- 「解出」＝train 跟 test 都對（training 有答案）。H8 每 pass 都量，但不進 G1。

## 三棵樹曲線

| pass | empty L/H | empty-g1g4 L/H（三 seed 相同） | old L/H |
|---|---|---|---|
| 0 | 2/0 | 2/0 | 9/2 |
| 1–8 | 2/0 | 2/0 | 9/3 |
| **AUC_L** | **16** | **16**（平均 16，全距 0） | **72** |

- 每 pass 的節點：empty 2,226,239；empty-g1g4 pass 0 2,226,239、pass ≥1 2,204,794（log 使用次數先驗讓 `beb8660c` 早一點找到）。`lib_size`／`lib_bits` 全 0；`mean_prog_nodes` 4.0。
- 秒數：empty 每 pass 約 1.4 s；empty-g1g4 每 pass 4～35 s（G4 花的，機器上還有其他線在跑）。
- **empty 的快取**：輸入一樣（庫、排序、預算）時結果是確定的，所以 pass 2～8 直接重用 pass 1 算出的結果，`wall_s` 也照抄 pass 1。pass 0 和 pass 1 都是實算的。雙跑每次都從頭重算。
- **舊樹**：pass 0＝暫存 blocks-root，只放 28 個 `kind=primitive` 的積木資料夾（`ARCAGI_BLOCKS`），pool 是空帳（`ARCAGI_POOL`，只放 config.json 副本）；pass 1＝真 `aos/blocks/` 的暫存副本（473 個資料夾，含 retired）。舊樹不會學，所以 pass 2～8 照抄 pass 1。`solvers.search` 用 MAX_NODES 100k 加 20 s 秒預算，不回報節點數，所以 `nodes`、`lib_bits`、`mean_prog_nodes` 都留空。舊樹 pass 1 多解出的 H 題是 `44f52bb0`。

## 雜訊

- empty 雙跑：`curve_sha` 兩次都是 `25d96f364c82a7d1cbf130970bf8f4cb3cd9aa68`（`curve.curve_sha` 把 `wall_s` 欄清空再算 sha，因為秒數本來就不會重複；測試 `tests/grow/test_grow.py::test_empty_curve_is_deterministic` 也檢查這件事）。
- G4 三個 seed 0／1／2：`curve_sha` 都是 `4ea0894b…`，AUC_L 都是 16，全距 0。所以「旋鈕改了有沒有真進步」的門檻是 >0。

## seedlib 積木

**0 顆。** 原因是可壓的語料只有 2 支解出來的程式：`(reverse $in)`（大小 2）跟 `(sort (map (lam 1 (sort $0)) $in))`（大小 6）。所有大小 ≥2 的封閉子樹各只出現 1 次；兩兩反統一又因為根運算子不同，只會得到一個洞。這樣省量＝1×size−size−k×洞 ≤ 0。G4 也沒補出新的解，語料就一直沒變大。G1 本身是正常的：單元測試裡兩支共用 `sort∘transpose∘reverse` 的程式可以抽出省量 >0、帶型別簽名的積木。開發早期 A 線還沒定稿的時候，G4 曾經解出一支冗長的 `beb8660c`，G1 從裡面抽出了 3 顆省量 3～4 的積木，下一 pass 就用 `sort (blk …)` 解出來。那是舊版引擎的結果，不算數。基準檔 `aos/seedlib/blocks.json` 不存在；每條曲線的庫放在 `aos/seedlib/<tree>/blocks.json`（都是 `[]`）。

## meta 回合（4-pass 曲線，AUC＝Σ pass 1..3，G4 seed 0）

為了趕時間，meta 用 4-pass 曲線。挑旋鈕是 Thompson 抽樣（每個旋鈕一個 Beta(1+accepted, 1+tried−accepted)，次數從 ledger 讀回來）。

| 回合 | 旋鈕 | 前 → 後 | AUC 前 → 後 | 秒 | 採用 |
|---|---|---|---|---|---|
| 1 | order | prior → size | 6 → 6 | 34.9 | 否 |
| 2 | m | 3 → 5 | 6 → 6 | 40.9 | 否 |
| 3 | max_holes | 2 → 1 | 6 → 6 | 42.6 | 否 |

`aos/meta/ledger.jsonl` 多了 3 行（`kind=r07`）。旋鈕基準值在 `data/r07/knobs.json`：m=3、k=2、max_holes=2、g4_frac=0.2、order=prior、lam_depth=2。`lam_depth` 是在 runtime 設定 `seed.lam.LAM_DEPTH`，seed 的原始碼沒動。

## 下一步要看的

空樹沒長出東西，瓶頸在起點語料太小（2 題），不在 G1。G4 的近失敗大多是「整張照抄輸入」這類高像素分、離正解很遠的程式，變異詞彙又只取自這些近失敗。r08 可以考慮讓 G4 用原語型別做插入式變異（試過一版，太慢，這輪沒用），或者把題組擴大，讓 pass 0 有 ≥3 支可以互相壓縮的解。
