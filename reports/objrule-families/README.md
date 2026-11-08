支線 S3「每物件規則積木族」：在 `objrule` 上加了 10 個每物件原語（`src/arcagi/objrule/families/`，用 `FAMILY_PRIMS` 註冊），驗收兩項都達到。

← [支線](../../notes/rounds/支線.md)｜程式 [families](../../src/arcagi/objrule/families/__init__.py)｜測試 [tests/objrule/families](../../tests/objrule/families/)

## 結論

| 量什麼（純 Python search，HEAD 543e062 快照） | 沒有 families | 有 families（06f6779） |
|---|---|---|
| training 216 題子集（r05 同大小未解） | 1 | **35** |
| training 全量 | 95/400（同大小 47） | **130/400**（同大小 81），退步 0 |
| evaluation 全量 | 39/400（同大小 15/270） | **44/400**（同大小 **19/270**），退步 0 |
| 過 train 答錯（Python 選中程式） | eval 16、train 27 | eval 17、train 28 |
| 逐題耗時合計 | eval 1154 秒、train 622 秒 | eval 1483 秒（+28%）、train 745 秒（+20%）；單題最長不變（20.5 秒） |

- 驗收：216 子集 1→35 **達到**；evaluation 同大小 +4（≥＋2）、退步 0 **達到**。
- evaluation 新解 5 題：`070dd51e`、`aa18de87`、`c92b942c`、`f0df5ff0`、`5af49b42`。families 是在 training 上調的，evaluation 只量。
- 主線 r06（hybrid，含 C++）量的是快照 7220e25，見 [dsl-search-r06](../dsl-search-r06/README.md)：S3 原語參與 evaluation 新解 5 題。

<details><summary>加了哪些族（精確語意在各檔 docstring）</summary>

| 原語 | 族 | 一句話 | 例（training） |
|---|---|---|---|
| `halo4_key`／`halo8_key`、`bbox_fill_key`、`holes_fill_key`、`inner_key`、`outline_key` | keyed | 對每個物件塗一塊區域（外圈、外框內、洞、內部、邊），顏色查表，表的鍵是物件屬性（顏色、大小、形狀、最大／最小、洞數、高的奇偶…）；`-1`＝物件自己的顏色 | dc1df850、b27ca6d3、bb43febb、868de0fa、56ff96f3 |
| `part_key` | parts | 同上，區域換成物件的一部分：上／下／左／右半、隔一格、內部隔一格 | ce9e57f2、a5f85a15、3bdb4ada |
| `stamp_key` | stamp | 每種鍵蓋一個固定圖樣（相對物件框的位移→顏色） | 0ca9ddb6、d364b489、95990924 |
| `bridge` | bridge | 同色、同列／同欄的兩物件之間拉一條帶子（自己的色或固定色；`stop` 遇障礙不連、`pass` 繞過格線） | 06df4c85、dbc1a6ce、a699fb00 |
| `rays_key` | rays | 每種鍵朝一組方向射線（含斜向） | 5c0a986e、623ea044 |
| `mirror_about` | mirror | 以選中的那個物件為中心補對稱（左右／上下／兩者／四向旋轉） | 4938f0c2、4c5c2cf0 |
| `move_ex` | moves | 朝來源方向**只走一步**，或滑過去並**刪掉沒有來源值的物件** | dc433765、a48eeaf7 |
| `template_paste` | template | 盤面上的多色樣板貼到同尺寸的單色方塊（或對錨點色／中心） | e76a88a6 |

物件範圍 `scope`（所有族的 `conn` 參數）：除了 `4same` 等，多了 `4same@5`（**指定背景色重抽物件**：把 5 當背景，S2／主線要的變體）和 `group`（同色所有格子算一個物件，連不連通都行）。

</details>

<details><summary>防背答案</summary>

- 沿用主線門檻：作用物件 ≥3；表裡每一格 ≥2 個物件支持；非 `const` 的鍵，train 上的值（含「不動」）≥2 種。候選必須重現每一對 train。
- `stamp_key` 更嚴：每格與每個位移 ≥3 個物件支持（r06 指出它帶大表；改後 training 0962bcdd 不再過 train 答錯，training 解題數不變）。
- 合成集（S5 `data_synth/`）抽查：同一題 halo 比 stamp 泛化好（4258a5f9 halo 27/27、stamp 15/27），所以註冊順序 keyed 在 stamp 前。
- 仍會過 train 答錯的（training）：`60b61512`（`bbox_fill_key` 用 4 連通 vs 8 連通，train 分不出）、`d687bc17`（`move_ex`）、`10fcaaa3`（`stamp_key`）；evaluation `e7dd8335`（`part_key`）。

</details>

<details><summary>指令與輸出（可重跑）</summary>

- 快照：`git archive <commit>` 到 scratchpad，資料夾 symlink 到本 repo 的 `data/ARC-AGI`；基準把 `families/__init__.py` 換成空的 `FAMILY_PRIMS`。
- 評測：`artifacts/s3-families/ev.sh <copy> <split> <name> [tasks-dir]`＝`systemd-run --user --scope -q -p MemoryMax=8G nice -n 19 python -m arcagi eval --split <s> --solver arcagi.solvers.search:solve --timeout 45 --workers 6`（`PYTHONPATH` 指快照的 `src`；開跑前 pgrep 確認沒有別的 `arcagi eval`）。
- 輸出：`artifacts/s3-families/{ev,tr}-{base2,dev2}.json`、`sub-dev2.json`（216 題子集）、`*-traces.jsonl`；對照 `cmp.py a.json b.json`、過 train 答錯歸因 `ptw.py traces.jsonl`、一步直接檢查 `direct.py`。
- ledger 列（給主線核後寫入）：`objrule-families-s3 | python search + FAMILY_PRIMS (06f6779) | evaluation 44/400 (same 19/270) vs 39 (15) | training 130 vs 95 | regressions 0 | 結論：是`。

</details>

## 代定

- D-S3-1：families 只做「整題 train 全對才給候選」，不做部分一致（`partial` 留在 `keyed.fit` 但沒開），以免 BFS 變寬。
- D-S3-2：`stamp_key` 支持度提高到 3（依 training 證據＋主線建議），代價是可能少解 evaluation 的 stamp 題（量時未見損失：c92b942c、f0df5ff0 仍解）。
- D-S3-3：`group` 與 `@c` 範圍放進所有塗色族的候選；`mirror_about`、`move_ex` 只用原本的四種連通。
- D-S3-4：量法用 Python search 單獨跑（不經 C++），基準與實驗同一個 HEAD 快照。
