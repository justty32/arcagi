# gpgp-ho 進度（n3d）

- 程式：`native/gpu/gp/`（旗標 `--holdout loo`、`--mdl λ`、`--simplify min`；預設行為不變）、`native/Makefile` 目標 `gpugp-ho` → `native/bin/gpgp-ho`。`native/bin/gpgp*` 未重建。
- smoke：3c9b0459 原旗標與 ho 旗標都 solved（rot180）、test 對。
- 在跑：`arcagi-n3d-ho`、`arcagi-n3d-mdl`（`run.sh ho|mdl`），輸出 `{real,on40}-{ho,mdl}.jsonl`＋`-verify.jsonl`，完成時寫 `DONE-<cfg>`。
- 原版對照：real-40 = `bench/real/gp.jsonl`＋`gp-verify.jsonl`；on40 = `on40-orig.jsonl`＋`on40-orig-verify.jsonl`（overnight pass-1 中 8 solved＋33 隨機未解，seed 1109）。
- 剩：`python3 summarize.py` 出表 → `../holdout.md`。
