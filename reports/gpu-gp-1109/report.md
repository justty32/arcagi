# N3 GPU 遺傳式程式搜尋（gpgp）——同 GPU 時間下 GP／random／窮舉

← [夜跑看板](../../notes/rounds/gpu-night-1109/README.md)｜白話 [gp-白話](../../notes/rounds/gpu-night-1109/gp-白話.md)｜交接 [progress](progress.md)｜N2 雛形 [prototype](../native-cuda-1109/prototype.md)

## 問題

同一段 GPU 時間裡，遺傳式程式搜尋（GP）能不能在窮舉到不了的深度找到窮舉找不到的解？目的是改進 aos 的搜尋能力，不是衝解題率。

## 設計（摘要）

- `native/gpu/gp/gp_kernel.cu` 直接 `#include "../kernel.cu"`：原語與判解（`Verdict`）和 N2 窮舉同一份。
- 個體＝字母表索引序列（長 1..10）；預設 65536 個體、256 島；適應度 = 0.5·逐格相符 + 0.35·列聯表 colormap 相符 + 0.15·形狀 − 0.002·長度。菁英、環狀遷移、隨機移民、錦標賽、一點交配、四種突變。
- **判解**：train 全過 `Verdict`（exact，或尾端補一張 colormap）且 test 輸出合法；CPU 再以 arcsearch 原語確認並貪婪化簡，`depth` = 化簡後步數（不含尾端 colormap）。注意：這只保證 train 一致，**test 對不對要看 Python 驗證欄**。
- `--random`：同一取樣器、不做選擇（對照組）。`--synth`：植入長度 L 的隨機程式造題，且確認深度 < 4 全空間無解。
- 窮舉對照＝N2 `gpusearch --mode gpu --dedup 4 --prefix-cap 3000000 --depth 8 --stop-first`，同每題秒數。

## 族群大小調校（與 N2 長跑共用 GPU；題 6e19193c，15 秒）

| --pop | 功耗 | eval/s | 代數 |
|---|---|---|---|
| 65536 | 93 W | 1.02e7 | 2328 |
| 524288 | 125 W | 1.89e7 | 543 |
| 2097152（2048 島） | 114 W | 1.45e7 | 104 |

整夜長跑採 `--pop 524288`（顯存約 0.5 GB）。比較實驗用預設 65536（GP 與 random 相同）。

<!-- RESULTS -->
