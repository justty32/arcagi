---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T17:20:10+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# arcbatch 空樹語言模式上線：400 題逐題與 Python 一致、子搜尋 1547 次 0 差異，快 12～22 倍（693da13、5872187）

空樹語言模式做好了，已 push 到 main（0f3b3cb、693da13，報告在 5872187）。C++ 跟 Python seed 逐題一致，6 個 worker 下快 12～22 倍。

## 一致性（以 b67dc2a 之後的 Python 為真值）

- golden 747 組：全過。
- 求值器：400 題 bank 裡的 79,309 支程式 × 340,533 個輸入值，0 差異。
- 整題 100k 節點，training 400 題：純枚舉、r07 拆法兩種都是 400/400 一致。比對的是 program、nodes、nodes_to_first、near（逐位元）。
- 整題 1M 節點，r08 L16＋P32：全一致。
- 子搜尋重播：九種拆法全開（含 halves、nest），r08 的 80 題共 1,547 次子搜尋，0 差異。
- 「子目標錄製工具」我已經做了，主線不用另寫：`native/tools/seed_record.py record` 先錄，`arcbatch --mode seed-sub` 重跑，再用 `seed_record.py compare` 比對。它只在執行期包住 `decomp.search` 和 `cond_witness`，不改 seed 原始碼。

## 速度（牆鐘秒數，6 workers，Python／C++）

| 題組 | 預算 | 純枚舉 | r07 拆法 |
|---|---|---|---|
| r08 L16 | 100k | 2.14／0.111 | 1.01／0.063 |
| r08 L16 | 1M | 20.7／1.58 | 12.0／0.97 |
| r08 P32 | 100k | 4.90／0.232 | 2.76／0.167 |
| r08 P32 | 1M | 68.2／3.48 | 39.8／2.50 |
| training 400 | 100k | 45.8／2.59 | 32.2／1.46 |

- training 400 題、1M 節點：C++ 25～27 秒，記憶體峰值 1.8G。Python 同樣設定用 6 workers 時超過 8G，被 scope 的 OOM 砍掉（機器沒事）。**提醒：Python 跑 1M 節點時 workers 要減少。**

## 跟 05 規格不同的地方（報告 §2.4）

1. `--mode seed` 的 `decomp` 除了 `false`，也接受 `true` 和 r07 的拆法名單（map、zip_pos、if、take、conj_transpose、conj_reverse、append），C++ 自己跑 decomp，結果跟 Python 一致。halves、nest 會回錯，訊息叫你改用 seed-sub。照 D-r8-13 只用 `false`＋seed-sub 也行。
2. seed-sub：
   - `budget` 是 Enumerator 的預算。
   - `cond_limit` 是絕對上限；另外也收 `cond_budget`，limit＝cond_budget − nodes。
   - `program` 只放枚舉找到的，cond 找到的放在 `cond.program`。
3. `eval_steps` 是精確計數，包括 HOF 裡 lambda 的步數，所以跟 Python 的近似值不同。
4. seed-run 的 `inputs`（陣列）和 `input`（單一）兩種都吃。
5. `--taskset` 可以吃 r08 檔的任何 split（例：`--split practice`）；`--ids a,b,c` 可以只取子集（CRN 用）。

## 還沒做

- 收輪的 evaluation（gated 入口）：等你們排時段，我這邊 binary 已經 make 好了。
- 舊樹 native 的熱點（apply_more 等）。
- G4 還在 Python。
