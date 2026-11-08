# gate-r07：通用守門收「過 train 卻答錯」（r07 C 線，離線）

## 結論

- **training（r06 混合基線 138 對、過 train 答錯 57）**：預設守門（`unseen`＋`synth` 降級＋`table`）**擋錯 35**（Python 16、native 19），**誤擋 0**，改判對 0，**淨對 138**。門檻（擋錯 ≥15、誤擋 ≤3、淨 ≥138）全過。
- **evaluation（審計，合成門自動停用）**：同一設定**擋錯 17／29**（Python 10、native 7），**誤擋 0**，淨對 56（不變）。
- 擋下來的幾乎全靠第 4 條門 **`table`（記憶型格表）**；規劃裡的 (a)(b)(c) 三條門在 r06 資料上要嘛沒用、要嘛害到答對的題（數字見下）。所以 (a) 跟形狀門預設關，(c) 只降級、不丟。
- 改判對的上限是 0：r06 trace 記下的過 train 程式（每題最多 30 支），在 57 題答錯的 training 題裡，沒有任何一支的測試輸出是對的。守門只能把錯答案換成「放棄」，換不出對的答案。

## 每門單獨與合併貢獻

擋錯＝r06 top-1 錯的題被改成放棄或換別的候選；誤擋＝r06 對的題被拿掉或換掉；淨＝基線 − 誤擋 + 改判對。

| 門（設定） | training 擋錯 | training 誤擋 | training 淨 | evaluation 擋錯 | evaluation 誤擋 | evaluation 淨 |
|---|---|---|---|---|---|---|
| 無 | 0 | 0 | 138 | 0 | 0 | 56 |
| (a) `support`：同輸出 ≥2 支相異程式才首選，否則降級 | 2 | 2 | 136 | 0 | 2 | 54 |
| (b) `unseen`：輸出含 train 輸出與該測試輸入都沒有的顏色 | 0 | 0 | 138 | 0 | 0 | 56 |
| (c) `synth` 否決：4 個合成 pair 要全過 | 55 | 62 | 76 | —（停用） | — | 56 |
| (c) `synth` 只降級 | 0 | 0 | 138 | — | — | 56 |
| (d) `table`：記憶型格表（新增） | **35** | **0** | **138** | **17** | **0** | **56** |
| (e) `shape`：違反 train 的形狀規律（新增） | 0 | 1 | 137 | 0 | 0 | 56 |
| `support`＋`table` | 36 | 1 | 137 | 17 | 1 | 55 |
| `table`＋`shape` | 35 | 1 | 137 | 17 | 0 | 56 |
| **預設** `unseen`＋`synth`(降級)＋`table` | **35** | **0** | **138** | **17** | **0** | **56** |
| 全開（`synth` 否決） | 55 | 62 | 76 | 17 | 1 | 55 |

完整組合見 `training-summary.json`、`evaluation-summary.json`；每題擋／放／改判見 `training-tasks.csv`、`evaluation-tasks.csv`（`verdict` 欄是 pass／block／switch；`outcome` 欄細分為 pass、block_wrong、switch_wrong、switch_right、block_right；`only_<門>` 欄是只開那一條門時的結果）。

## 各門為什麼是這個數字

- **(a) 最小支持度**：r06 的錯答案不缺支持度。57 題錯答中有 20 題 top-1 有 ≥2 支程式背書（通常是同一張 `local_rule` 表的 n4／n8 變體），而 138 題對的裡有 22 題也是這樣。照規格「降級不等於丟」：所有候選都只有 1 支時保留原順序（不放棄），不然會把 100 題以上單支程式的對題全部丟掉。開了只會換題，淨 −2。
- **(b) 未見值**：0／0。vote 和 learner 本來就不會造出新顏色，這條門在 r06 上用不到，但保留（成本很低，又是通用的）。
- **(c) 合成校準**：分辨力很強，卻是錯的那種強。55／57 錯答過不了 4 個合成 pair，可是 62／138 對答也過不了。原因是 RE-ARC 生成器會換顏色、換尺寸、換結構，原題卻固定不變。例如 `split_overlay`＋`colormap [[10,2]]` 的輸出色是寫死的，`transpose`（9dfd6313）、`symmetrize`（496994bd、f25ffba3）也有 0／24 的。改成「只用調色盤 ⊆ 原題的合成 pair」（誤擋還有 26～37），或者改用「輸出同構」比對（誤擋還有 59），都一樣救不回來。所以預設只**降級**：過不了合成的候選排到過得了的後面，不丟。r06 上這樣是 0／0。evaluation 沒有 `data_synth`，這條門會自動停用。
- **(d) `table` 記憶型格表（自加）**：`local_rule`／`x_vrule` 這兩種格鄰域表，每一列是一個會變色的鄰域鍵。在 train 進入該步的狀態上，那個鍵實際改到的格子少於 2 格的列叫「薄列」。表 ≥4 列、而且薄列過半，就判定這張表是逐格背答案，不信它。理由：Python learner 本來就要求每個變色鍵至少 2 格支持（`MIN_SUPPORT = 2`），但 native 擬合器和 `x_vrule` 候選沒有這條。r06 有 21 題錯答的表是「每列只改 1 格」。這條門對所有來源一視同仁，不管是哪支擬合器產的表都套同一條。
  - 先試過「測試輸入碰到 train 沒見過的鍵」，結果 0 命中：擬合時就已經拒絕這種表了。所以改成上面的證據量門。
  - 門檻是在 training 上選的，有過擬合風險，邊界案例如下。≤3 列的表豁免，是為了放過 bbc9ae5d、91714a58，否則會多誤擋這 2 題。67a423a3、3618c87e 的薄列剛好一半，不算過半。換成「每列平均改格數 <2」會多誤擋 2 題。evaluation 沒參與調參，結果擋錯 17、誤擋 0，算是一次獨立驗證。
- **(e) 形狀規律（自加）**：train 每對都保持輸入形狀（或輸出全是同一形狀），測試輸出卻違反，就不信。r06 上擋錯 0、誤擋 1（training），所以預設關。

## 資料與方法

- 只用 r06 artifacts（`artifacts/dsl-search-r06/{training,evaluation}.json`）。每題 trace 的 `attempts[kind=program]` 是混合入口實際排出的過 train 程式（最多 30 支，依 vote 排序，native 題帶 `origin`）。`scripts/r07_gate_eval.py` 用 `arcagi.dsl.program` 重跑這些程式，取得 train／test 輸出、4 個合成 pair 的通過數和格表統計，再套 `guard.judge`。沒有重跑任何搜尋。
- 候選資訊是否充足：training 195 題、evaluation 85 題有候選，**全部 faithful**（重跑後的 top-1 輸出＝r06 記下的預測），沒有缺資訊的題。限制有兩點：
  - Python 階段就解出的題，hybrid 不會跑 native，所以這些題沒有 native 候選。
  - 支持度只算 trace 記下的程式（≤30 支）。
- 線上入口：`python -m arcagi.solvers.gated {input} {output} {trace}`，可以接 `--external`。它內部呼叫原封不動的 `native/bin/solve`，讀它的 trace 重建候選後過 guard，判定寫進 `trace.metadata.guard`。plugin 形式是 `arcagi.solvers.gated:solve`，只有 Python search。抽 2 題實跑過：48d8fb45 因 `table 18/18 thin rows` 放棄，00d62c1b 保留。
- 指令：`uv run python scripts/r07_gate_eval.py --split {training|evaluation}`（每 split 不到 1 分鐘，單程序）。

## 沒擋到的錯答（training 22、evaluation 12）

這些錯答在 csv 裡是 `outcome=pass` 且 `base_correct=0`。多半是 S3 `stamp_key`（0962bcdd、3ac3eb23、10fcaaa3）、物件移動和裁切的組合，以及 `colormap` 寫死顏色的題。它們不帶格表，(b)(e) 也抓不到；目前唯一抓得到的是合成否決，但代價太高。r08 可考慮兩條路：把 `stamp_key` 這類 pattern 表接進同一套薄列證據量，或者先把合成 pair 做顏色正規化再校準。

## 線上全量 evaluation（隊長跑，2026-11-08 15:44）

- 指令：`systemd-run --user --scope -q -p MemoryMax=16G nice -n 19 uv run arcagi eval --split evaluation --name gated-r07 --external '.venv/bin/python -m arcagi.solvers.gated {input} {output} {trace}' --timeout 45 --workers 6`；head 272b76f（含 S3 families 06f6779、guard 3129cc4），native 45668f9（`native/bin` 為當時建置）。輸出 `artifacts/gated-r07/evaluation.json`、`evaluation-traces.jsonl`。
- 結果：**57/400**、errors 0；每題最長 19.2 秒；逐題耗時合計 5217 秒（r06 5093）。
- 對 r06（56）：新解 5af49b42（S3 families 06f6779，非守門所致）、退步 0。
- 守門：放棄 16 題（`all distrusted`，全是 r06 會答錯的題；離線預估 17）、誤擋 0；仍答錯 10 題（r06 過 train 答錯 29 → 10）。

## 線上全量 training（隊長跑，2026-11-08 16:05）

- 指令同上（`--split training`）；head 132a0b7、native 45668f9。輸出 `artifacts/gated-r07/training.json`。
- 結果：**147/400**、errors 0；每題最長 19.1 秒；逐題耗時合計 3520 秒。
- 對 r06（138）：新解 10（多為 S3 families 06f6779）、退步 1（6cdd2623：r06 由 native 在 15 秒解出，這次 native 16 秒內沒找到——19 秒期限下的負載雜訊，守門未參與）。
- 守門：放棄 32 題（全是會答錯的）、改選 1 題且改對、誤擋 0；仍答錯 20 題（r06 57）。
