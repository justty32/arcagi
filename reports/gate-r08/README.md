# gate-r08：收輪 gated evaluation（S1 cf83c7f 支持度門，只用 training 選）

## 結論

- evaluation **56/400**（gated-r07s1 是 57），errors 0，每題最長 19.1 秒，逐題耗時合計 5107 秒。
- 退步 1 題：`be03b35f`。新解 0。
- 過 train 答錯（守門放行但答錯）**10→9**，少掉的是 `8597cfd7`。守門放棄 11 題（`all distrusted`），跟 r07s1 一樣。
- be03b35f 退步的原因：S1 第四任照 D-r7-18 只用 training 重選 native 支持度門（cf83c7f，連 colormap 也守），這題的 26 支 C++ 解全被支持度門擋掉（`support_gated` 30、`verified` 0），沒有候選可答。S1 第三任報告就提過：守 colormap 會掉 be03b35f，當時是看了 evaluation 才改成不守，D-r7-18 因此判它是審計汙染。這次的 −1 就是「不看 evaluation 選門檻」的誠實代價。主線**不回改**（回改＝看 evaluation 調參，D-r8-21）。

## 指令

- 入口：`python -m arcagi.solvers.gated`（D-r7-15，使用者 17:15 裁定）。head 為 tag `r08-seed0`（含 S1 cf83c7f、0f3b3cb、693da13），`make -C native` 於同一 head。
- `systemd-run --user --scope -q -p MemoryMax=16G nice -n 19 uv run arcagi eval --split evaluation --name gated-r08 --external '.venv/bin/python -m arcagi.solvers.gated {input} {output} {trace}' --timeout 45 --workers 6 --output artifacts/gated-r08/evaluation.json --traces artifacts/gated-r08/evaluation-traces.jsonl`
- 比對對象：`artifacts/gated-r07s1/evaluation.json`。
- 仍答錯 9 題：009d5c81、3194b014、642d658d、64a7c07e、73ccf9c2、9110e3c5、929ab4e9、95a58926、e7dd8335。
