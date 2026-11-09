# N4f：GPU 窮舉補位接進主線 gated 入口（opt-in，預設關）

前情：[N4e](../task-features-1109/n4e-gated.md)（R1 補位：training +2 對／+1 假解／0 衝突）。

## 怎麼開

```
ARCAGI_GPU_FALLBACK=reports/native-cuda-1109/overnight/phase-A.jsonl:reports/native-cuda-1109/filler/train-open-d6.jsonl:reports/native-cuda-1109/filler/eval-open-d6.jsonl:reports/native-cuda-1109/overnight/phase-B.jsonl \
  python -m arcagi.solvers.gated {input} {output} {trace}
```

- 值是用 `os.pathsep` 分隔的 gpusearch JSONL 路徑。用環境變數，是因為外部協議的 argv 固定，同 `ARCAGI_SYNTH` 的慣例。`main()`（external）和 `solve()`（plugin）兩個入口都支援。
- 行為（`src/arcagi/solvers/gated.py`：`load_gpu_programs`、`gpu_fallback`、`_gpu_from_env`）：
  - 只在主線 `guard.judge` 放棄時才觸發。
  - 該題的 GPU 程式按 `best` 在前、`samples` 在後排序並去重，用 `gated.evaluate` 重跑；沒過 train 的丟掉。
  - 剩下的過 `guard.judge(gates={"table","unseen"})`，也就是 R1。過了就採用，reason 加上 `gpu-fallback: ` 前綴；沒過就保留主線原本的放棄。
  - 開啟時 trace 的 `metadata.guard.gpu_fallback` 會記 `{used, n_programs, reason}`。
- 未設這個環境變數時，不讀檔、不加欄位，輸出和改前逐位元相同。

## 驗證

| 項目 | 結果 |
|---|---|
| 預設關時是否不變（[headcheck.py](headcheck.py)） | 用改前（15b2aa0）與改後的 `gated.main`，餵同一份存檔 trace，比對輸出檔與 trace 檔的 bytes。training 400 題加 evaluation 400 題：**same=800 diff=0**（[headcheck.out.txt](headcheck.out.txt)） |
| 單元測試 | `tests/solvers/test_gated_gpu_fallback.py`：只在放棄時觸發、unseen 門擋得住、沒過 train 不採用、關閉時 main/solve 不變、載入時去重且保序。`tests/solvers` 共 141 passed |
| training 重放（[replay.py](replay.py)，[out](replay-training.out.txt)） | 關閉時 147（與存檔 0 差異）。開啟時 **149**。新增對題：46f33fce、a79310a0。新增假解：25d8a9c8。衝突 0。補位觸發 3 題（主線放棄 233 題）。**與 N4e 完全一致** |
| evaluation 審計（只跑一次，沒調任何東西；[out](replay-evaluation.out.txt)） | 56→**58**（66e6c45b、be03b35f），假解 0，衝突 0，觸發 2 題。與 N4e 一致 |

重放方式：拿 `artifacts/gated-r07/training-traces.jsonl` 和 `artifacts/gated-r08/evaluation-traces.jsonl` 裡存好的 hybrid trace，重跑 `gated.gate`（預設門），不重跑主線搜尋。逐題結果太大，沒有 commit，放在 scratchpad。

## 風險

- 25d8a9c8 這類假解：GPU 程式靠調換 colormap 順序、寫死顏色在 train 上湊對。table 和 unseen 門擋不住，training 上多 1 題假解。
- 補位只用離線快取。快取沒有的題（GPU 沒跑過或沒解出）不受影響；要擴大效果，得另外花 GPU 預算算快取。
- 快取的程式靠 Python DSL 重跑驗證。registry 變了的話，程式會在 `evaluate` 那一步被丟掉，結果偏保守。
- 主線 training 的基準是 r07（r08 沒跑 training）。
- headcheck 的改前副本放在 src 外面，`ROOT` 會解析錯，必須設 `ARCAGI_SYNTH`。第一次沒設時有 1 題（a5313dff）不同，原因是 synth 門讀不到資料，是比對工具的問題，不是改動造成的。
