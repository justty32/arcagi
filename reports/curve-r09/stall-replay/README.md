第九輪 B 線：`hammer/stall.py` 停滯三判回放 r08 曲線的驗收。判準照 [02 §1 步 5](../../../notes/rounds/r09/02-規劃-fable.md)，window＝3，判準寫在 `stall.py` docstring，回放前寫死。

## 判準

| 狀態 | 條件（近 3 epoch） |
|---|---|
| starve | gate 進料每個 epoch 都是 0（優先判） |
| saturate | `solved_L`、`solved_H24`、`lib_bits` 全不動 |
| stop | saturate 且未解 L16 的最佳 `near` 分數也不動 |
| ok | 其他，或不足 3 個 epoch |

## r08 轉接

- 曲線（`curve.csv`）：`gate_in`＝`clean_P`（pool 樹只壓縮乾淨的練習池解）；r08 沒記 near 分數，所以回放最多判到 saturate，判不到 stop。
- meta（`meta/rounds.json`）：每個 meta 回合當一個 epoch；`solved_L`＝該回合的 AUC 均值，`lib_bits` 欄用 logcost 均值代（meta 層的分數）；H24 與 gate 進料沒逐回合記，當缺值跳過（不判 starve）。

## 結果（每個 epoch／回合結束後的判定）

| r08 曲線 | 判定序列 | 驗收 |
|---|---|---|
| `pool` | ok ok starve starve starve starve starve starve starve | **starve**（預期 starve，過） |
| `meta`（5 回合） | ok ok saturate saturate saturate | **saturate**（預期 saturate，過） |
| `pool-foot32` | ok ok ok ok ok saturate saturate saturate saturate | 參考：有進料、第 5 pass 起平 |
| `pool-g4/seed1` | ok ok starve ×7 | 參考：同 pool |
| `dec-g1` | ok ok ok saturate ok ok saturate saturate saturate | 參考：pass 4 庫有變動，判回 ok |

重跑：`uv run python -m arcagi.hammer.stall curve reports/curve-r08/pool/curve.csv`、`uv run python -m arcagi.hammer.stall meta reports/curve-r08/meta/rounds.json`；測試 `tests/hammer/test_b_stall.py`。
