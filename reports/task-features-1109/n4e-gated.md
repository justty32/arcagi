# N4e：GPU 窮舉結果當主線 gated 候選來源，在 training 上量得失（只量，不收編）

← 入口 [README](README.md)；前情 [N4d](n4d-six.md)

## 結論

GPU 窮舉的程式**沒有格表步驟**，`table` 門與 `unseen` 門一支也沒擋到，所以 **R1 跟 R0 的結果完全一樣**。真正的差別在「怎麼接進主線」。

- **只在主線放棄時才用 GPU（補位）**：training 新增 2 題對（46f33fce、a79310a0），新增 1 題假解（25d8a9c8），衝突 0。
- **GPU 答案蓋過主線（覆蓋）**：多出 3 題衝突，主線原本答對、GPU 答錯，等於淨賺 −1。

R2（同一個 test 輸出要有 ≥2 支程式支持）在 training 上反而比較差：擋掉了正解 a79310a0（只有 1 支程式支持），卻沒擋掉假解 25d8a9c8（3 支只是調換順序的程式互相支持）。

## 方法

- 來源：`reports/native-cuda-1109/overnight/phase-A.jsonl`（`--depth 5 --dedup 3 --budget 120`，800 題），加上 `filler/train-open-d6.jsonl`、`filler/eval-open-d6.jsonl`、`overnight/phase-B.jsonl`（depth 6，只跑還沒解的題，共新增 5 題有解，其中 test 對 1 題）。每題取 `best`，再加上 `samples`，去掉重複。gpusearch 每題最多存 5 支 samples，所以支持度只是下限。
- **直接重用主線守門的程式碼**，沒有重寫：
  - `arcagi.solvers.gated.evaluate` 用 Python DSL 重跑程式，丟掉沒過 train 的程式，算出 test 輸出與 `table_stats`。
  - `arcagi.solvers.guard.judge` 負責判定。
  - R0 不開門（`gates=()`）。R1 只開 `{"table","unseen"}`。主線 r07 預設門是 unseen、synth、table，這裡少了 `synth`，因為 GPU 結果沒有合成對可查，而且主線的 synth 門本來就只降序、不剔除。
  - R2 是在 R1 之上，取第一支「受信任、且 `guard.support_counts`≥2」的候選，沒有就放棄。
  - r08 的 native S1 支持度門（cf83c7f，在 `native/src/batch.cpp` 裡守 colormap、local_rule、x_vrule）是 C++ 搜尋內部的門，GPU 輸出沒有它需要的欄位，這裡**沒有重現**。R2 是功能最接近的替代。
- 主線基準：
  - training 用 `artifacts/gated-r07/training-traces.jsonl`（147/400 題；r08 沒有跑 training）。
  - evaluation 用 `artifacts/gated-r08/evaluation-traces.jsonl`（56/400）。
  - 逐個 test 對照 `tests_correct`。主線有沒有放棄，看 trace 的 `metadata.guard.abstained`。
- 腳本 [n4e/gated_rules.py](n4e/gated_rules.py)，摘要輸出 [n4e/gated_rules.out.txt](n4e/gated_rules.out.txt)，逐題結果 [n4e/per_task.jsonl](n4e/per_task.jsonl)。只在 CPU 上跑，不到 1 分鐘。

## 表 1：training（選規則只看這張）

有 GPU 程式的題共 57 題，每題都至少有 1 支在 Python 上重跑仍過 train。

| 規則 | 接法 | 主線未解題：新增 test 對（題） | 主線未解題：假解（過 train、test 錯） | 主線已解題：衝突 | evaluation 審計：新增／假解／衝突 |
|---|---|---|---|---|---|
| R0 不開門 | 覆蓋 | +2（46f33fce、a79310a0） | 5 題（2013d3e2、239be575、25d8a9c8、27a28665、aabf363d） | 3（1f85a75f、44f52bb0、72ca375d） | +2（66e6c45b、be03b35f）／0／0 |
| R1 table+unseen | 覆蓋 | +2（同上） | 5（同上） | 3（同上） | +2／0／0 |
| R2 R1＋支持度≥2 | 覆蓋 | +1（46f33fce） | 4（2013d3e2 被擋） | 2（44f52bb0、72ca375d） | +2／0／0 |
| R0＝R1 | **補位**（只在主線放棄時用） | **+2**（46f33fce、a79310a0） | **+1**（25d8a9c8） | **0** | +2／0／0 |
| R2 | 補位 | +1（46f33fce） | +1（25d8a9c8） | 0 | +2／0／0 |

讀表說明：

- 「覆蓋」那三列的假解，有 4 題主線本來就已經過 train 答錯了（2013d3e2、239be575、27a28665、aabf363d，r07 判 kept）。換成 GPU 答案也還是錯，不算新增的錯。但 239be575 有一點例外：主線答對了 2 個 test 中的 1 個，GPU 兩個都錯，所以覆蓋會再少 1 個 test 對。
- 補位模式下唯一新增的假解是 25d8a9c8，主線原本是 all distrusted、放棄作答。
- 衝突的 3 題，GPU 程式都是靠調換順序、寫死顏色，在 train 上湊對：
  - 72ca375d：4 個 colormap 換順序後接 `crop_bbox`，支持度 4 是假的。
  - 1f85a75f：同類型的程式。
  - 44f52bb0：top1 `gravity>downscale>colormap` 在第 2 個 test 錯。
- 套用到全 training：主線 147→149 題對（補位、R1），過 train 答錯 +1。

## 表 2：evaluation（只做事後審計，不拿來選規則）

有 GPU 程式的題 17 題。各規則、各接法的結果都一樣：+2 題（66e6c45b、be03b35f，主線都放棄了），假解 0，衝突 0。56→58/400。be03b35f 正是 D-r8-21 接受的那 −1，補位接法就能補回來，而且不必改 r08 的 S1 門。

## 白話

GPU 窮舉找到的都是短的純組合程式，不帶格表，所以主線那兩道擋「記表」和「憑空冒出新顏色」的門對它們沒有作用。它的風險是另一種：只在 train 上碰巧湊對，例如 colormap 調換順序、寫死顏色、tile 和 downscale 互換。這種程式常常好幾支一起出現、互相「支持」，所以「≥2 支程式支持」的門擋不住。反而是真正的正解，有時只有 1 支程式支持（a79310a0），會被這道門誤擋。

GPU 一旦蓋過主線已經選好的答案，就會把主線答對的題改錯（3 題）。只讓 GPU 在主線放棄時補位，training 上是 +2 對、+1 錯，主線已答的題完全不受影響。

## 給使用者的建議與預設

- **預設：收，接法用「補位」，規則用 R1**（table+unseen；對這個來源等同不開門，但留著門比較安全，將來 GPU 原語若加入格表步驟也守得住）。
  - training 證據：+2 題對、+1 假解、0 衝突，淨 +1。
  - 補位時依 trace 排序取 GPU 的 top1（`best` 優先）。
- **不建議 R2**：在 training 上比 R1 少 1 題對，假解一樣多。
- **不建議覆蓋接法**：training 有 3 題衝突，淨 −1。
- 25d8a9c8 這類假解：如果要再壓低，可以研究「把只是交換步驟順序的程式算成同一支、再數支持度」，或「colormap 寫死的顏色在 test 輸入裡沒出現就降序」。這兩個做法都只能在 training 上選門檻；這次只量，沒有做。
- 需要使用者裁的點：補位接法在 training 上淨 +1、evaluation 審計 +2，是否值得把 GPU 窮舉的離線結果接進 gated 入口（需要 GPU 預算或預先算好的快取）。

## 限制

- 支持度受 samples 上限 5 支與 `--dedup 3` 影響，只是下限。
- 主線 training 基準是 r07；r08 的 S1 門會讓 training 結果有些出入，但 r08 沒有跑 training。
- 沒有重現 C++ 搜尋內部的 S1 支持度門。

## 安全

只寫本檔與 `n4e/`。只在 CPU 上跑（`arcagi-n4e-rules` scope，不到 1 分鐘），沒用 GPU，沒動主線、活樹或其他單元。
