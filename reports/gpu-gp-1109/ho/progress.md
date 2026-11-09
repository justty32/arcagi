# gpgp-ho 進度（n3d）

- 程式：`native/gpu/gp/`（旗標 `--holdout loo`、`--mdl λ`、`--simplify min`；預設行為不變）、`native/Makefile` 目標 `gpugp-ho` → `native/bin/gpgp-ho`。`native/bin/gpgp*` 未重建。
- smoke：3c9b0459 原旗標與 ho 旗標都 solved（rot180）、test 對。
- 已完成：兩個單元跑完（DONE-ho、DONE-mdl），結論見 `../holdout.md`。
- 原版對照：real-40 = `bench/real/gp.jsonl`＋`gp-verify.jsonl`；on40 = `on40-orig.jsonl`＋`on40-orig-verify.jsonl`（overnight pass-1 中 8 solved＋33 隨機未解，seed 1109）。
- 剩：無（下一步見 holdout.md）。
