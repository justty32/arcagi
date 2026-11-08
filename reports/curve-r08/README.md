# r08 學習曲線（B 線：練習池、迭代加深、logcost_L、5-seed CRN meta）

**結論**：練習池這一輪**沒有讓曲線動起來**。主樹 `pool`（分解 DEFAULT＋G1＋主題練習池 P32，seed `b67dc2a`）的 AUC_L 是 32、Δ_L 0，跟 r07 對照 `dec-g1`（32）一樣，也跟不學的 `pool-noG1`（32）一樣。原因是主題 P32（`draw.ring_around`、`objects.copy_stamp`、`pattern.make_symmetric`、`overlay.boolean`）在 25k～400k 預算下 0 題過 train，`clean_P` 全 0，G1 沒有料可學，冷啟動死鎖照舊。

改成按空樹立足點挑主題的 `pool-foot32`（D-r8-18）以後，練習池第一次真的吐出料：`clean_P` 10→15，`false_pos` 0，長出 8 個 P 積木，`reverse $in` 被 L16 用了 8 次，`transpose $in` 被 6 題共用，H24 1→2。但同時 L16 少解 1 題（beb8660c），AUC_L 降到 26，反而比較差。

5-seed CRN meta 跑了 5 回合，全部不採用；拆法動作 `halves`、`nest` 也都不採用。halves 讓 L16 從 4 題升到 6 題（AUC_L 12→18，5 個 seed 都一樣），但 H24 不動，跨題 bootstrap 的判準也沒過（降幅 20.3 < 2×SE 25.8）。H8 全程 0，`llm_calls` 全 0。

## 指令

```sh
uv run python scripts/r08_taskset.py   # data/r08/taskset.json（兩次 sha 相同）
R="nice -n 19 systemd-run --user --scope -q -p MemoryMax=16G uv run python -u scripts/r08_curve.py --workers 8"
$R --tree dec-g1                         # r07 對照（r07 規則：test 對的 L16 解進 G1、庫上限 40、閒置 3 pass 淘汰）
$R --tree pool                           # 分解 DEFAULT＋G1＋主題練習池 P32
$R --tree pool --out reports/curve-r08/pool-rerun   # 雙跑
$R --tree pool-noG1                      # 同 P 預算排程、不學（算力紅利）
$R --tree pool-rand32                    # P 改盲抽 32 題（D-r8-15）
uv run python scripts/r08_foot.py        # 立足點探針 → data/r08/foot_pass0.json，再重跑 r08_taskset
$R --tree pool-foot32                    # P 改「空樹立足點」主題（D-r8-18）
for s in 1 2 3; do $R --tree pool-g4 --seed $s; done   # ＋G4，CRN（P 取 80% 子集）；seed 4、5 因時限停掉
$R --tree meta --rounds 5                # 層 1＋層 2，4-pass、P 封頂 100k、seeds 1..5
$R --tree action --action decomp:halves --fresh --commit b67dc2a   # A 線拆法當 meta 動作
$R --tree action --action decomp:nest --commit b67dc2a
$R --tree pool-halves                    # 參考：DEFAULT＋halves（未採用）
uv run python scripts/r08_report.py reports/curve-r08/<tree>      # 表格數字
```

- **seed commit**：主表全部用 A 線合入後的 **`b67dc2a`**（`git archive b67dc2a src` 解到 scratchpad，再疊上本線的 `grow/`，用 `PYTHONPATH` 跑）。`dec-g1` 在 `0bea07d`（＝r07 的 `efdee5d`）快照和 `b67dc2a` 快照上的 curve sha 都是 `7aebb3c73f28`，`nodes_solved` 逐 pass 跟 r07 一樣（120160→7053），所以 DEFAULT 拆法的行為逐位不變。
- 舊門（MDL 用 /4，D-r8-19 之前）在 `0bea07d` 跑的五條曲線留在 `gate4-0bea07d/`，只當參考。
- 每 pass 重搜 L16＋H8＋H24（每題 100k）和 P（25k 起每 pass ×2，封頂 400k）。`AUC_L = Σ_{pass 1..8} solved_L`；P 跟 H24 都不進 AUC_L。
- **G1 門（D-r8-6、D-r8-19）**：不看 test，也不看 S5。條件是過 train，而且 (a) 程式節點數 < train 輸出格數總和（MDL），(b) train ≥3 對時做留一：拿掉 1 對，用其餘的對、同設定、1/4 預算重搜，找到的程式要能解出留出的那一對。L16 跟 P 一律過這道門才能進 G1，權重相同，每題送一支（枚舉找到的最小程式）。test 對錯只記審計欄 `false_pos`（進 G1 的程式裡 test 錯的支數），S5 只記 `synth_ok`（進 G1 的 P 程式裡，S5 合成 pair 過半對的題數）。
- **logcost_L（D-r8-10）**：每題 `log2(min(nodes_to_first, 100k))`，沒解出記 `log2(100k)`；pass 0 就解出的題，之後的加速最多算 2 bits。表中的值是 pass 1..8 的和。
- 庫：活躍庫上限 16（`lib_cap`），連 2 pass 沒被任何新解用到就淘汰（D-r8-12）。`dec-g1` 照 r07 規則：上限 40、閒置 3 pass 淘汰。

## 題組（`data/r08/taskset.json`，sha1 `418234a6748e3f4ed13ecffd6a2e7aa8be98efa9`）

| 組 | 題數 | 規則 |
|---|---|---|
| L16 | 16 | 照抄 `data/r07/taskset.json`（計分） |
| H8 | 8 | 照抄 r07（只量） |
| H24 | 24 | training 扣 L16/H8，按 `sha1(task_id+"r08H24")` 取前 24（只量不學；本線沒有讀這些題的內容） |
| P32（主題，D-r8-14） | 32 | `draw.ring_around` 12、`objects.copy_stamp` 11、`pattern.make_symmetric` 7、`overlay.boolean` 2 |
| rand32（D-r8-15） | 32 | 同一批剩餘題，按 `sha1(task_id+"r08R32")` 取前 32 |
| foot32（D-r8-18） | 32 | `scale_tile.mirror_tile` 11、`draw.connect_points` 9、`recolor.global_map` 6、`geometry.flip_rot` 4、`geometry.transpose` 2 |

- P32 的主題照規則寫死：先排 L16 裡出現 ≥2 次的 subcategory，再排其他 L16 subcategory，按 training 同類題數降序。隊長預估第三主題是 `fill.bbox_or_gap`，實際排到的是 `objects.copy_stamp`（training 同類題比較多）；ring_around 只剩 12 題，因為 L16/H8/H24 已經用掉幾題。
- foot32 的立足點來自 `data/r08/foot_pass0.json`：空庫、DEFAULT 拆法、100k，在 L16/H8/H24 以外的 352 題上只看 train_ok，共 17 題過 train。各主題命中數：mirror_tile 5、flip_rot 4、global_map 2、transpose 2、其餘 1（同數按名，所以 connect_points 排來補滿 32）。

## 曲線（solved 欄是 pass 0..8）

| 樹 | solved_L | AUC_L | Δ_L | logcost_L | solved_H | solved_H24 | clean_P | budget_P | false_pos | P 積木被 L16 用次 | 單一積木最多共用題數 | curve_sha |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dec-g1 | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1940.959 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | –/–/–/–/–/–/–/–/– | – | –/–/–/–/–/–/–/–/– | 0 | 2 | `7aebb3c73f28` |
| pool | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1969.168 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 0/0/0/0/0/0/0/0/0 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 0 | 0 | `b2f4e170ad1f` |
| pool-rerun | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1969.168 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 0/0/0/0/0/0/0/0/0 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 0 | 0 | `b2f4e170ad1f` |
| pool-noG1 | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1980.096 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 0/0/0/0/0/0/0/0/0 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 0 | 0 | `4d33bbce43c8` |
| pool-rand32 | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1970.884 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 0/0/1/1/1/1/1/1/1 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 0 | 1 | `c7c00ac38b0a` |
| pool-foot32 | 4/4/4/3/3/3/3/3/3 | **26** | -1 | 1972.41 | 0/0/0/0/0/0/0/0/0 | 1/2/2/2/2/2/2/2/2 | 10/13/15/15/15/15/15/15/15 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 8 | 6 | `b2d09f895442` |
| pool-g4/seed1 | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1965.117 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 0/0/0/0/0/0/0/0/0 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 0 | 0 | `3f8d9ead5179` |
| pool-g4/seed2 | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1965.117 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 0/0/0/0/0/0/0/0/0 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 0 | 0 | `28bba1acd38d` |
| pool-g4/seed3 | 4/4/4/4/4/4/4/4/4 | **32** | +0 | 1965.117 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 0/0/0/0/0/0/0/0/0 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 0 | 0 | `35098ba409ab` |
| pool-halves（未採用） | 6/6/6/6/6/6/6/6/6 | **48** | +0 | 1917.739 | 0/0/0/0/0/0/0/0/0 | 1/1/1/1/1/1/1/1/1 | 2/2/2/2/2/2/2/2/2 | 25k→400k | 0/0/0/0/0/0/0/0/0 | 8 | 1 | `d9c67691b110` |

- 「P 積木被 L16 用次」：來源含 P 題的積木出現在 L16 test 對解裡的次數，9 個 pass 加總。「共用題數」：同一個積木被幾道不同題（L16 或 P）的 test 對解用到。
- `dec-g1` 用新程式重跑，`AUC_L` = 32，跟 r07 相同；`nodes_solved` 120160→7053 也逐 pass 相同。H24 每 pass 解 1 題。
- `pool`（主題 P32）：P 在 25k～400k 全程 0 題過 train，`clean_P` 全 0。新門下 L16 進 G1 的只有 3 支（beb8660c 被留一擋掉），三支程式沒有省量 >0 的共同子樹，所以庫一直是空的（0 個積木）。跟 `pool-noG1` 唯一的差別是使用次數先驗改了枚舉順序：logcost 1969.2 對 1980.1，解題數相同。
- `pool-foot32`：P 的 `clean_P` 10→15（pass 2 起持平），`false_pos` 全 0，`synth_ok` 9→14。從 P 長出 8 個積木，其中 `reverse $in`（P＋L）被 L16 解用了 8 次，`transpose $in` 被 6 道不同題的真解共用。**但 L16 從 pass 3 起少解 beb8660c**（4→3，AUC_L 26），H24 則從 pass 1 起由 1 變 2。
- `pool-g4` 只跑了 3 個 seed（1～3）：一條 8-pass 要 4～9 分鐘，seed 4、5 停掉，把時間留給 meta 和拆法動作（隊長 D-r8-18 允許縮成 3 seed）。三個 seed 的 AUC_L 都是 32、logcost 都是 1965.117，全距 0；sha 不同，只差在 G4 的節點數。這幾條的庫只有冷啟動近解模板（`repeat 3 $h0` 等）和 `transpose $in`：連 2 pass 沒人用就淘汰，下一 pass 又被重抽回來，所以 `lib_size` 在 2 和 5 之間來回。
- `pool-halves`（DEFAULT＋halves，halves 沒有過 meta 判準，**只當參考**）：pass 0 就是 6 題，AUC_L 48、Δ 0，所以這 +16 全部來自 A 線手加的拆法，跟學習無關（記 `kind=r08-agent`）。H24 維持 1。halves 也讓主題 P32 過了 2 題（`overlay.boolean`、`pattern.make_symmetric` 各 1，都過門），長出 `reverse $in`（P＋L），被 L16 用了 8 次。
- 舊門版（`gate4-0bea07d/`）的 AUC_L：pool 32、pool-noG1 32、pool-rand32 32（rand32 的 clean_P 0→1）。


## 每主題（P 內，最後一個 pass：過 train／過 G1 門／test 對）

| 曲線 | 主題 | 題數 | 過 train | 過 G1 門 | test 對 |
|---|---|---|---|---|---|
| pool | `draw.ring_around` | 12 | 0 | 0 | 0 |
| pool | `objects.copy_stamp` | 11 | 0 | 0 | 0 |
| pool | `overlay.boolean` | 2 | 0 | 0 | 0 |
| pool | `pattern.make_symmetric` | 7 | 0 | 0 | 0 |
| pool-rand32 | `draw.ring_around` | 1 | 0 | 0 | 0 |
| pool-rand32 | `geometry.flip_rot` | 1 | 1 | 1 | 1 |
| pool-rand32 | `objects.copy_stamp` | 1 | 0 | 0 | 0 |
| pool-rand32 | `overlay.boolean` | 1 | 0 | 0 | 0 |
| pool-rand32 | `rand32` | 27 | 1 | 0 | 0 |
| pool-rand32 | `recolor.global_map` | 1 | 0 | 0 | 0 |
| pool-halves（未採用） | `draw.ring_around` | 12 | 0 | 0 | 0 |
| pool-halves（未採用） | `objects.copy_stamp` | 11 | 0 | 0 | 0 |
| pool-halves（未採用） | `overlay.boolean` | 2 | 1 | 1 | 1 |
| pool-halves（未採用） | `pattern.make_symmetric` | 7 | 1 | 1 | 1 |
| pool-foot32 | `draw.connect_points` | 9 | 0 | 0 | 0 |
| pool-foot32 | `geometry.flip_rot` | 4 | 4 | 4 | 4 |
| pool-foot32 | `geometry.transpose` | 2 | 2 | 2 | 2 |
| pool-foot32 | `recolor.global_map` | 6 | 2 | 2 | 2 |
| pool-foot32 | `scale_tile.mirror_tile` | 11 | 7 | 7 | 7 |

- 被 L16 用到的、源自 P 的積木，只有一個來自 foot32 的 `scale_tile.mirror_tile`：`reverse $in`（來源 4c4377d9、6fa7a44f、8be77c9e，另加 L16 的 68b16354），共用 8 次。P32 和 rand32 長出的積木都沒有被 L16 用到。rand32 只有 `geometry.flip_rot` 的 1 題過門，長出 `transpose $in`（P＋L），L16 用到 0 次。rand32 表裡標成 `rand32` 的 27 題不屬於任何主題。


## 門：舊門（MDL /4）跟新門（MDL /1）各擋掉哪些題

| 曲線 | 舊門（gate4-0bea07d）擋掉的 | 新門擋掉的 |
|---|---|---|
| pool | L `beb8660c`（留一，pass 0–2）、L `d10ecb37`（MDL，全程） | L `beb8660c`（留一，全程） |
| pool-rand32 | L `beb8660c`（留一）、L `d10ecb37`（MDL）、P `3c9b0459`（留一，pass 1）、P `7b7f7511`（MDL，test 錯，擋得對） | L `beb8660c`（留一）、P `3c9b0459`（留一，pass 1）、P `7b7f7511`（留一，pass 1–8，test 錯，擋得對） |
| pool-foot32 | — | L `beb8660c`（留一，pass 0–2）、P `b1948b0a`、`c8f0f002`（留一，pass 0–1） |

- 被擋的 L 題 test 其實都對（beb8660c、d10ecb37）：門是保守的。新門下 `false_pos` 全 0。
- `pool-noG1` 不學，門只影響哪些程式進 G1，所以 pool-noG1 的解題數不受門影響；新快照照樣重跑了一次（sha `4d33bbce43c8`）。

## seedlib 積木（來源 P／L）

| 樹 | 名稱 | body | 簽名 | 省量 | 來源 | 主題 | L16 用次 | 共用題數 |
|---|---|---|---|---|---|---|---|---|
| dec-g1 | `g1_0177e4faae` | `["lam", 1, ["sort", ["$0"]]]` | `(list[a]) -> list[a]` | 3.0 | L | — | 0 | 0 |
| dec-g1 | `g1_f72643d574` | `["map", ["lam", 1, ["sort", ["$0"]]], ["$h0"]]` | `(list[list[a]]) -> list[list[a]]` | 2.0 | L | — | 16 | 2 |
| pool-rand32 | `g1_0652240849` | `["transpose", ["$in"]]` | `list[list[int]]` | 2.0 | P+L | geometry.flip_rot | 0 | 1 |
| pool-foot32 | `g1_2ff25d9c21` | `["map", ["lam", 1, ["append", ["$0"], ["reverse", ["$0"]]]], ["$in"]]` | `list[list[int]]` | 7.0 | P | scale_tile.mirror_tile | 0 | 5 |
| pool-foot32 | `g1_019b408846` | `["reverse", ["$in"]]` | `list[list[int]]` | 6.0 | P+L | scale_tile.mirror_tile | 8 | 4 |
| pool-foot32 | `g1_0652240849` | `["transpose", ["$in"]]` | `list[list[int]]` | 6.0 | P+L | geometry.flip_rot, geometry.transpose | 0 | 6 |
| pool-foot32 | `g1_6b6baf343b` | `["transpose", ["reverse", ["blk", "g1_0652240849"]]]` | `list[list[int]]` | 6.0 | P | geometry.flip_rot | 0 | 3 |
| pool-foot32 | `g1_e6ba9d8a6f` | `["reverse", ["blk", "g1_0652240849"]]` | `list[list[int]]` | 6.0 | P | geometry.flip_rot | 0 | 1 |
| pool-foot32 | `g1_996048a4bc` | `["append", ["blk", "g1_2ff25d9c21"], ["reverse", ["blk", "g1_2ff25d9c21"]]]` | `list[list[int]]` | 4.0 | P | scale_tile.mirror_tile | 0 | 3 |
| pool-foot32 | `g1_0392d6a5b1` | `["append", ["$in"], ["blk", "g1_019b408846"]]` | `list[list[int]]` | 3.0 | P | scale_tile.mirror_tile | 0 | 2 |
| pool-foot32 | `g1_ab1fc6264d` | `["reverse", ["blk", "g1_6b6baf343b"]]` | `list[list[int]]` | 2.0 | P | geometry.flip_rot | 0 | 2 |
| pool-g4/seed1 | `g1_82c739c4e2` | `["repeat", 3, ["$h0"]]` | `(a) -> list[a]` | 5.0 | L-near | — | 0 | 0 |
| pool-g4/seed1 | `g1_2119d64b73` | `["repeat", 3, ["repeat", ["$h0"], ["$h1"]]]` | `(int, a) -> list[list[a]]` | 1.0 | L-near | — | 0 | 0 |
| pool-g4/seed1 | `g1_1a40b22956` | `["repeat", 4, ["$h0"]]` | `(a) -> list[a]` | 1.0 | L-near | — | 0 | 0 |
| pool-g4/seed1 | `g1_0652240849` | `["transpose", ["$in"]]` | `list[list[int]]` | 2.0 | L | — | 0 | 0 |
| pool-g4/seed1 | `g1_d417bb28c8` | `["sort", ["transpose", ["$h0"]]]` | `(list[list[a]]) -> list[list[a]]` | 1.0 | L-near | — | 0 | 0 |

- `pool`（主題 P32）一個積木都沒長。`pool-g4` seed 2、3 的積木跟 seed 1 相同。來源 `L-near`：冷啟動時從未解 L16 題的最佳近解抽出的模板（D-r7-10）。

庫放在 `aos/seedlib/r08-<tree>/blocks.json`；每條曲線出生過的積木全部記在 `reports/curve-r08/<tree>/blocks_born.json`。


## meta（4-pass、P 封頂 100k、CRN seeds 1..5、`pool` 設定不開 G4）

起點是 `data/r08/knobs.json`（分解開、DEFAULT 拆法、G1、`lib_cap` 16、`budget_mult` 2）。每回合跑 4-pass 曲線：P 用 80% 子集、封頂 100k，**不開 G4**（G4 一條 8-pass 要 4～9 分鐘，在時限內跑不完 30 條；開 G4 的曲線另見 `pool-g4`）。旋鈕池是 `kn.CHOICES` 扣掉 `decomp`（r08 的樹固定開分解）。層 2 用 Gaussian Thompson：每個旋鈕抽一次 `N(Σz/(n+1), 1/√(n+1))`，reward 是 bootstrap z，截斷在 ±3。判準程式化在 `meta.crn_judge`：≥4/5 個 seed 的 L16 logcost 沒有變差、平均降幅 ≥ max(1, 2×SE)、5 個 seed 的平均 AUC_L 不退。

| 回合 | kind | 動作 | 前 → 後 | L16 logcost（Σ pass 1..3，5 seed）前 → 後 | AUC_L 5 seed 前 → 後 | 平均降幅（L16＋H24） | bootstrap SE | z | 秒 | 採用 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | r08 | `lam_depth` | 2 → 1 | 738.438 → [738.435, 738.435, 738.435, 738.435, 738.435] | [12, 12, 12, 12, 12] → [12, 12, 12, 12, 12] | 0.002 | 0.002 | 1.0 | 79.7 | 否 |
| 2 | r08 | `m` | 3 → 2 | 738.438 → [738.438, 738.438, 738.438, 738.438, 738.438] | [12, 12, 12, 12, 12] → [12, 12, 12, 12, 12] | 0.0 | 0.0 | 0.0 | 87.1 | 否 |
| 3 | r08 | `k` | 2.0 → 3.0 | 738.438 → [738.438, 738.438, 738.438, 738.438, 738.438] | [12, 12, 12, 12, 12] → [12, 12, 12, 12, 12] | 0.0 | 0.0 | 0.0 | 87.1 | 否 |
| 4 | r08 | `sub_lam_depth` | None → 3 | 738.438 → [738.438, 738.438, 738.438, 738.438, 738.438] | [12, 12, 12, 12, 12] → [12, 12, 12, 12, 12] | 0.0 | 0.0 | 0.0 | 87.3 | 否 |
| 5 | r08 | `lam_depth` | 2 → 1 | 738.438 → [738.435, 738.435, 738.435, 738.435, 738.435] | [12, 12, 12, 12, 12] → [12, 12, 12, 12, 12] | 0.002 | 0.002 | 1.0 | 79.8 | 否 |
| — | r08-agent | `decomp:halves` | default → default+halves | 738.438 → [718.844, 719.079, 719.079, 719.171, 718.844] | [12, 12, 12, 12, 12] → [18, 18, 18, 18, 18] | 20.272 | 12.891 | 1.573 | 75.6 | 否 |
| — | r08-agent | `decomp:nest` | default → default+nest，sub_lam_depth 3 | 738.438 → [738.438, 738.438, 738.438, 738.438, 738.438] | [12, 12, 12, 12, 12] → [12, 12, 12, 12, 12] | 0.0 | 0.0 | 0.0 | 87.3 | 否 |

- 回合資料見 `meta/rounds.json`。拆法動作的 base（`b67dc2a` 快照、跟 meta 終點同一組旋鈕）見 `action/base.json`，各 seed 的曲線在 `action/<tag>/seed<k>/`。
- **5 個 seed 完全相同**：主題 P32 沒有任何一題過 train，所以 80% 子集怎麼換都影響不到 L16。D-r8-3 想避免的「配對 SE＝0」在這裡是真的退化，靠跨題 bootstrap 才有非 0 的 SE。5 個旋鈕回合的 Δ 全部 ≤0.002 bits，沒有一個採用。
- **`decomp:halves`（r08-agent）**：5 個 seed 的 L16 從 4 題升到 6 題（新解的是 A 線診斷過的 496994bd、ce4f8723），AUC_L 12→18，L16 logcost 每個 seed 降約 19.4。**H24 1→1，沒有變。** 判準沒過：L16＋H24 跨題 bootstrap 的平均降幅 20.27 < 2×SE＝25.78。進步集中在 2 題，跨題重抽的變異就很大。照判準 halves 不進主樹，旗子保持預設關。
- **`decomp:nest`（配 sub_lam_depth 3）**：Δ 0、SE 0，不採用。
- `pool-halves`（8-pass，DEFAULT＋halves，**沒有被採用，只當參考**）：見上方曲線表，AUC_L 48、Δ 0、H24 1→1。
- ledger 本線新增 7 行：`kind=r08` 5 行、`kind=r08-agent` 2 行（`decomp:halves`、`decomp:nest`，commit `b67dc2a`）。中途有一次 meta 因為 `r08_row` 參數撞名而崩潰，崩潰前沒有寫入任何 ledger 行，修好後整輪重跑。

## 雜訊

- `pool` 雙跑的 curve sha 都是 `b2f4e170ad1f`（舊門版雙跑也相同，都是 `cb6bbe636ec1`）。`dec-g1` 換快照前後 sha 相同。
- CRN：seed 決定兩件事，G4 的隨機源和 P 的 80% 子集（`sha1(task_id+str(seed))` 排序取前 80%＝25 題）。meta 的前後比較用同一組 seed。配對 SE 是跨題 paired bootstrap：L16＋H24 共 40 題，題級重抽 1000 次，固定 seed `r08-boot`。

## 門檻（D-r8-11、規劃 §5）

| 門檻 | 主樹 `pool`（主題 P32） | `pool-foot32` | 過？ |
|---|---|---|---|
| AUC_L ≥ 40，且 Δ_L ≥ +1 來自學到的積木 | 32、Δ 0 | 26、Δ −1 | 否（`pool-halves` 有 48，但 Δ 0，來源是手加的拆法） |
| `pool` 比 `pool-noG1` 淨增 ≥2 題（AUC_L +8） | 32 對 32（+0） | 26 對 32（−6） | 否 |
| `clean_P` pass 8 ≥ 20，且 ≥ pass 0 的 1.5 倍 | 0→0 | 10→15（1.5 倍，但 <20） | 否 |
| ≥1 個源自 P 的積木被 L16 解用到 | 0 | 8 次（`reverse $in`） | 只有 foot32 過 |
| ≥1 個積木被 ≥2 道不同題的真解共用 | 0（無積木）；dec-g1 的 `map (λ sort)` 是 2 題 | `transpose $in` 共 6 題 | 只有 foot32 過 |
| H24 淨增 ≥2 | 1→1 | 1→2（+1） | 否 |
| `false_pos`（進 G1 的程式 test 錯） | 全 0 | 全 0 | 是 |
| H8 ≥1（目標） | 0 | 0 | 否 |
| `llm_calls` 全 0 | 是 | 是 | 是 |

## 偏置與限制

- 主題 P32（ring_around／copy_stamp／make_symmetric）對空樹的 list 語言太難：25k～400k 都是 0 題過 train，所以冷啟動照舊。這是否定結果。
- foot32 是用空樹自己的 pass 0 train_ok 挑出來的，選擇時沒看 test，也沒看 S5。
- 「新增積木反而讓 L16 少解一題」（foot32 的 beb8660c）：庫裡多了 P 長出來的積木，加上使用次數先驗，枚舉順序和分支度都被改了，`sort∘map sort` 在 100k 內找不到。
- G4 只用在計分組（L16/H8/H24），P 只做枚舉，為了省算力。
- 「源自 P 的積木被 L16 用到 8 次」要打折看：那個積木是 `reverse $in`，L16 用到它的就是 68b16354 自己的解（`reverse $in`），一個 pass 一次。它只是把一個原語包起來，沒有帶來新能力。真正跨題共用的組合積木（`map (λ append $0 (reverse $0))`、`transpose∘reverse∘transpose` 這類）只在 P 內部共用，沒有傳到 L16。
- `pool-g4` 只跑了 3 個 seed；meta 為了在時限內跑完 30 條曲線，用的是不開 G4 的 `pool` 設定。
- `reports/curve-r08/pool-g4/seed4/` 和 `aos/seedlib/r08-pool-g4-seed4/` 是停掉的半截 run，沒有 commit。
- `halves` 是 A 線看過 L16 白盒診斷後才加的拆法（Argon 指出的風險），所以 H24 的變化要並列來看。
