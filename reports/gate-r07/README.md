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

<!-- wf-nav -->
以下章節按語意拆到同資料夾的子檔，原文照搬：
- [各門為什麼是這個數字；資料與方法；沒擋到的錯答（training 22、evaluation 12）；線上全量 evaluation（隊長跑，2026-11-08 15:44）；線上全量 training（隊長跑，2026-11-08 16:05）；S1 ee869e5 後再量 evaluation（隊長跑，2026-11-08 16:35）](分析方法與線上量測.md)
