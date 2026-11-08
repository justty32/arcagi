# r07 學習曲線（B 線）

**結論**：最終的 seed 是 A 線 `efdee5d`。這一版的主曲線（分解開＋G1＋G4，3 個 CRN seed）`AUC_L` = 32、全距 0、Δ = 0：pass 0 解 4 題，之後 8 個 pass 一直是 4 題，多出來的進步全靠 A 線改優化器（pass 0 從 2 題到 4 題），不是自動學習學來的。

自動學習只在兩個地方看得到：

- **空樹＋G1**（冷啟動）：`AUC_L` 從 16 到 24，Δ = +1。G1 從近解抽出 `take 2 $h0`，pass 1 就解出 `d10ecb37`。
- **分解＋G1**：`AUC_L` 不變，但解出題的節點總數 `nodes_solved` 從 120,160 降到 7,053（壓縮 17 倍）。G1 學到 `map (λ sort $0) $h0`，被 1e0a9b12 和 beb8660c 共用。

其他數字：舊樹 `AUC_L` = 72，是 pass 0 L16 解 9 題 × 8。拿掉 transpose 的消融（empty-noT）在這 16 題上不影響解題數（16）。`llm_calls` 全 0。seedlib 有積木的省量 >0。

## 指令

```sh
uv run python scripts/r07_taskset.py          # data/r07/taskset.json, sha1 9ce7c7ea16bb…（兩次相同）
R="nice -n 19 systemd-run --user --scope -q -p MemoryMax=8G uv run python -u scripts/r07_curve.py"
$R --tree empty            # 純枚舉，decompose=False
$R --tree empty --out reports/curve-r07/empty-rerun
$R --tree empty-noT        # 純枚舉，暫時拿掉 transpose（seed.prims.without）
$R --tree empty-g1         # 只有 G1
$R --tree dec              # 分解開，純枚舉
$R --tree dec-g1           # 分解＋G1
for s in 0 1 2; do $R --tree dec-g1g4 --seed $s; done   # 分解＋G1＋G4，CRN
$R --tree old              # 舊樹對照（唯讀呼叫 solvers.search）
$R --tree meta --decomp --rounds 3 --passes 4 --seeds 0,1,2 --out reports/curve-r07/meta
```

- **seed commit**：`efdee5d`（A 線最終版）。實際跑法：把 `git archive HEAD src` 解到 scratchpad，再疊上 grow 的程式，用 `PYTHONPATH` 指過去跑。比對過，`seed/` 跟 `efdee5d` 一模一樣，跑的過程中不會被 A 線的工作樹改動影響到。workers 6，每題每 pass 100k 節點；有 G4 的樹是 80k 枚舉＋20k G4。
- 每 pass 都重新搜全部 24 題，已經解出的也重搜（D-r7-9）。pass 0 是學習前的起點，`AUC_L = Σ_{pass=1..8} solved_L`，`Δ = solved_L(8) − solved_L(0)`。`nodes_solved` 是解出題的 `nodes_to_first` 總和；G4 解出的題用它的總節點數。
- 「解出」＝train 跟 test 都對。H8 每 pass 都量，但不進 G1。
- G1 冷啟動（D-r7-10）：解出題數 ≤2 時，把未解 L 題的最佳近解也拿來抽模板，槽懲罰 k = 1；解出題數 >2 時，回到只看解出程式、k = 2。近解只拿來抽模板，不算使用次數。
- G4 適應度（D-r7-11）：尺寸吻合 ×（目標跟輸入不同的格子上的對率），所以照抄輸入拿不到分。

## 曲線（L／H 是 pass 0..8 每 pass 的解出題數）

| 樹 | solved_L | solved_H | AUC_L | Δ | nodes_solved p0→p8 | 庫 | curve_sha（去 wall_s） |
|---|---|---|---|---|---|---|---|
| empty | 2/2/2/2/2/2/2/2/2 | 全 0 | **16** | 0 | 26068→26068 | 0 | `1abb6824eec5` |
| empty-rerun | 同上 | 全 0 | 16 | 0 | 26068→26068 | 0 | `1abb6824eec5` |
| empty-noT | 2/…/2 | 全 0 | **16** | 0 | 25093→25093 | 0 | `b0394cc9307d` |
| empty-g1 | 2/3/3/3/3/3/3/3/3 | 全 0 | **24** | **+1** | 26068→11915 | 1 | `7ba473669842` |
| dec | 4/…/4 | 全 0 | **32** | 0 | 120160→120160 | 0 | `4a55a61174c2` |
| dec-g1 | 4/…/4 | 全 0 | **32** | 0 | 120160→**7053** | 1 | `5ce6e1820f6e` |
| dec-g1g4 seed0 | 4/…/4 | 全 0 | 32 | 0 | 101484→5913 | 1 | `4d22d3045fa2` |
| dec-g1g4 seed1 | 4/…/4 | 全 0 | 32 | 0 | 101484→5913 | 1 | `4d22d3045fa2` |
| dec-g1g4 seed2 | 4/…/4 | 全 0 | 32 | 0 | 101484→5913 | 1 | `8e922c9ac740` |
| old | 9/…/9 | 2/3/…/3 | **72** | 0 | （記不到） | 473 | `6fc55fac800f` |

- dec-g1g4 的 `AUC_L` 平均 32，全距 0。seed2 的 sha 跟另外兩個不同，只差在 pass 0 的總節點數（G4 在未解題上花的節點不一樣），解題數完全相同。
- dec 在 pass 0 解出 4 題：`68b16354`（reverse）、`1e0a9b12`（transpose∘map sort∘transpose）、`d10ecb37`（map (take 2)∘take 2）、`beb8660c`（sort∘map sort）。`44f52bb0` 過 train 但 test 答錯。H8 一題都沒解出。
- empty-g1 在 pass 1 解出 `d10ecb37`，程式是 `map (λ blk_take2 $0) (blk_take2 $in)`；分解沒開也能靠學到的積木解出來。
- 舊樹：pass 0 用暫存 blocks-root，只放 28 個 `kind=primitive` 積木，pool 是空帳；pass 1 用真 `aos/blocks` 的暫存副本（473 個資料夾）。舊樹不會學，pass 2～8 照抄 pass 1。`solvers.search` 不回報節點數，所以節點相關欄位留空。這條曲線跟 seed 版本無關，在 seed `efdee5d` 進來前就跑完了，程式路徑相同。

## 雜訊

- empty 雙跑：兩次 curve_sha 都是 `1abb6824…`（`curve.curve_sha` 先把 `wall_s` 欄清空再算；有對應測試）。
- G4 CRN 三個 seed（0／1／2）：`AUC_L` 都是 32，全距 0。原本規劃 5 個 seed，時間不夠減成 3 個。meta 的「真進步」判準照 D-r7-11 縮放成 ≥⌈0.8n⌉ = 3/3 個 seed 不退步，而且平均增量 ≥1 題。

## seedlib 積木（MDL 省量 >0）

| 樹 | 名稱 | body | 簽名 | 省量 | 來源 | 用次 |
|---|---|---|---|---|---|---|
| dec-g1、dec-g1g4×3 | `g1_f72643d574` | `(map (lam 1 (sort $0)) $h0)` | `(list[list[a]]) -> list[list[a]]` | 2.0 | 1e0a9b12、beb8660c（解出程式） | 16 |
| empty-g1 | `g1_0fe6fca1dc` | `(take 2 $h0)` | `(list[a]) -> list[a]` | 1.0（k=1 冷啟動） | d10ecb37 近解 | 16 |

每棵樹的庫放在 `aos/seedlib/<tree>/blocks.json`，跑完的那份另外複製到 `reports/curve-r07/<tree>/blocks.json`。基準檔 `aos/seedlib/blocks.json` 不存在。

## meta（層 1＋Thompson 層 2，4-pass 曲線，AUC＝Σ pass 1..3，CRN seeds 0,1,2）

為了趕時間，meta 用 4-pass 曲線。起點是 `knobs.json` 加上 `decomp=True`。旋鈕有 7 個：原本 6 個再加「分解 開／關」。

見 `meta/rounds.json`；表格如下：

| 回合 | 旋鈕 | 前 → 後 | AUC（seeds 0,1,2）前 → 後 | 秒 | 採用 |
|---|---|---|---|---|---|
| 1 | decomp | True → False | [12, 12, 12] → [12, 12, 12] | 136.6 | 否 |
| 2 | k | 2.0 → 1.0 | [12, 12, 12] → [12, 12, 12] | 96.3 | 否 |
| 3 | lam_depth | 2 → 1 | [12, 12, 12] → [12, 12, 12] | 58.1 | 否 |

三回合都是 [12,12,12]→[12,12,12]，沒有一回合採用。分解在有 G1＋G4 的 4-pass 曲線上關掉也不掉分：分解關掉時，pass 0 只解 3 題，但 G1＋G4 在 pass 1 就補回 4 題（`meta/r1-decomp/seed0/curve.csv`），所以在 Σ pass 1..3 上看不出差別。

`aos/meta/ledger.jsonl` 本輪新增的行：上一版設定留下的 3 行 `kind=r07`（seed `fe9b759`，單 seed）、1 行 `kind=r07-agent`（A 線三段人工改優化器 `fe9b759→35049ef→0349a1d→efdee5d`，pass 0 從 2 題到 4 題，cost_s 1800），以及這次 meta 的 3 行 `kind=r07`（帶 `auc_*_seeds`）。

## 偏置與限制

- 題組維持 L16 8 題已解／8 題未解、H8 4／4，格子 ≤15×15，這是算力限制造成的偏置（隊長代定：taskset 不改，報告列出偏置）。
- G4 在分解樹上沒有額外解出任何題。分解已經把 G4 能補的近解直接解掉了，剩下的近解離正解太遠。
- 早期版本（seed `35049ef`、還沒有分解）的 empty-g1g4 曾經跑出 `AUC_L` 26～32、Δ +1～+2：G4 先解出 1e0a9b12 跟 d10ecb37，G1 再壓縮，枚舉就能更早找到。那批是舊 seed，已經被本表取代，資料沒有保留。
