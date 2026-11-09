# N8d：H2——lambda 本體葉節點免遞迴（arcbatch-hot-f，A+B+E+F）

依據 [n8c.md](n8c.md) H2：`native/hot/seed_value.cpp` `eval()` 對 CONST／INPUT／VAR／LAM 子節點也做完整遞迴
（`arena()` TLS＋24 B CNode 拷貝），預估 3–7%。`-DHOT_F` 在 kid 迴圈就地解葉；步數記帳須逐位元一致
（葉節點原本就在 `--c.steps` 之前 return，不扣步數）。

任務書：scratchpad `n8d/codex-task.md`；實作回報：[n8d-impl.md](n8d-impl.md)（codex 寫）；bench：[n8d_bench.sh](n8d_bench.sh)。

## 結果

（跑中，見 [n8d-progress.md](n8d-progress.md)。）

## 結果（主 session 04:1x 收）

tests/native 43 passed；cmp 12 筆全 0 差異（含 eval_steps）。負載 13.5–15.5。

| budget | bin | wall 中位 (min..max) s | 對 arcbatch | 差異 |
|---:|---|---:|---:|---:|
| 1e6 | arcbatch | 9.766 (9.766..9.918) | 1.000× | ref |
| 1e6 | hot-e | 8.969 (8.616..9.116) | 1.089× | 0 |
| 1e6 | hot-f | 9.034 (8.066..9.069) | 1.081× | 0 |
| 1e7 | arcbatch | 144.639 (139.206..146.116) | 1.000× | ref |
| 1e7 | hot-e | 119.359 (116.450..120.949) | 1.212× | 0 |
| 1e7 | hot-f | 118.950 (118.001..119.856) | 1.216× | 0 |

**判讀**：hot-f 對 hot-e 1e7 只 +0.3%、1e6 −0.7% → 未過收件門（1e7 >2%），**不收**；arcbatch-hot-e 維持最佳（本輪 1e7 1.212×）。葉節點遞迴不是瓶頸（編譯器大概已內聯）。程式碼以 `-DHOT_F` 獨立目標保留供查。
