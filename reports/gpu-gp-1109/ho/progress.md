# gpgp-ho 進度（n3d）

- 程式：`native/gpu/gp/`（旗標 `--holdout loo`、`--mdl λ`、`--simplify min`；預設行為不變）、`native/Makefile` 目標 `gpugp-ho` → `native/bin/gpgp-ho`。`native/bin/gpgp*` 未重建。
- smoke：3c9b0459 原旗標與 ho 旗標都 solved（rot180）、test 對。
- 已完成：兩個單元跑完（DONE-ho、DONE-mdl），結論見 `../holdout.md`。
- 原版對照：real-40 = `bench/real/gp.jsonl`＋`gp-verify.jsonl`；on40 = `on40-orig.jsonl`＋`on40-orig-verify.jsonl`（overnight pass-1 中 8 solved＋33 隨機未解，seed 1109）。
- 剩：n3e λ 掃描在跑（見下）。

## n3e：MDL λ 掃描（11-10 00:58 開跑）

- 單元：`arcagi-n3e-sweep.scope`（`timeout --signal=TERM 17199` → 最晚 05:45 收；MemoryMax=12G、nice 19；顯存約 0.5 GB）。
- 內容：`sweep.sh`，real-40／on40 × λ∈{0,0.003,0.006,0.01}（`--simplify min`、無 holdout、20 s/題）× seed 1–3，順序 seed>λ>題組。24 run 每個約 7–13 分，估 04:30～05:45 跑完；seed 3 可能被 05:45 截斷，截斷時 TERM 處理仍會重驗＋彙總。
- 輸出：`sweep/`（gitignore；`sweep.log` 看進度，`*.done` 為完整 run）；彙總 `sweep-summary.md`（`sweep_summarize.py`），最後一行 `SWEEPDONE` 表示收完。
- smoke（scratchpad）：real 2 題 λ0.006 跑通；on40 2 題 λ0.003×2 seed，2013d3e2 train solved、test 錯（假 solved，與 on40-mdl 一致）；TERM 15 s 截斷也正確寫出 summary＋SWEEPDONE、無殘留程序。
- 收尾：`sweep-summary.md` 有 SWEEPDONE 後，讀表寫結論進 `../holdout.md`（選預設 λ、假 solved 比例對 λ 的趨勢、seed 間變異）。
