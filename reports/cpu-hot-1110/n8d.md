# N8d：H2——lambda 本體葉節點免遞迴（arcbatch-hot-f，A+B+E+F）

依據 [n8c.md](n8c.md) H2：`native/hot/seed_value.cpp` `eval()` 對 CONST／INPUT／VAR／LAM 子節點也做完整遞迴
（`arena()` TLS＋24 B CNode 拷貝），預估 3–7%。`-DHOT_F` 在 kid 迴圈就地解葉；步數記帳須逐位元一致
（葉節點原本就在 `--c.steps` 之前 return，不扣步數）。

任務書：scratchpad `n8d/codex-task.md`；實作回報：[n8d-impl.md](n8d-impl.md)（codex 寫）；bench：[n8d_bench.sh](n8d_bench.sh)。

## 結果

（跑中，見 [n8d-progress.md](n8d-progress.md)。）
