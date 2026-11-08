# r09 學習曲線：錘子 hammer（活樹）＋三條對照

**結論**：主樹 `hammer` 的 AUC_L 是 **40**，不學的對照 `hammer-frozen` 是 32，靜態手寫拆法對照 `hammer-static` 是 48。H24 從 1 升到 2：epoch 0 由樹自己升 live 的睡眠造詞積木帶來，之後每個 epoch 都沒退。H8 全程 0，`llm_calls` 0，`false_pos` 0。相容模式 `dec-g1` 用 arcbatch 重現了 r08 的 sha `7aebb3c73f28`（M0），所以這一頁的數字可以跟 r08 直接比。

## 指令

```sh
R="nice -n 19 systemd-run --user --scope -q -p MemoryMax=16G uv run python scripts/r09_hammer.py"
$R --tree dec-g1                                   # M0 相容（arcbatch）
$R --tree hammer-frozen  --root <dir>              # 引擎凍結、無 halves／nest
$R --tree hammer-static  --root <dir>              # 引擎凍結、halves／nest 從 epoch 0 就 live
cd ~/code/playground-arc1/ws/hammer && ./ctl run --epochs 8 --daemon   # 主樹（活樹）
uv run python -m arcagi.hammer.metrics ~/code/playground-arc1/ws/hammer  # ΔAUC_total
uv run python -m arcagi.hammer.scan <root> --kind gate|route             # layer-2 掃描（不讀 H8／H24）
```

題組 `data/r09/taskset.json`（sha1 `983c3af9…`）：L16／H8／H24 照 r08，P48＝foot32 ∪ 指紋最近 r08 未解 L16 的 16 題。

## 曲線（epoch 0→8）

| 樹 | solved_L | AUC_L | solved_H24 | H8 | wall |
|---|---|---|---|---|---|
| dec-g1（M0） | 4 全程 | 32 | 1 | 0 | 3.6 秒，sha `7aebb3c73f28` ✓ |
| hammer-frozen | 4 全程 | 32 | 1 全程 | 0 | 17 秒 |
| hammer-static | 6 全程 | 48 | 1 全程 | 0 | 186 秒 |
| **hammer**（活樹） | 4,4,4,4,4,6,6,6,6 | **40** | 1,2,2,2,2,2,2,2,2 | 0 | 310 秒 |

- hammer 的升 live 紀錄：epoch 0 升 `comb_g1_2ff25d9c21`（`map (λ append $0 (reverse $0))`，新解 P 題 62c24649、67e8384a）和 `comb_g1_0652240849`（`transpose $in`），H24 因此 1→2；epoch 4 升 `decomp_halves`（`by:agent-r08`，新解 L16 496994bd、ce4f8723）和帶槽 comb `append $h0 (reverse $h0)`（`by:sleep`）。H24 熔斷沒有觸發（0 次回滾）。
- halves 升 live 之後，主跑要整批改走 Python 後端（C++ 沒有 halves），每 epoch 從 1～9 秒變成約 75 秒。
- 停滯判定：epoch 4、5、8 判 `stop`，各寫一份鑄模請求；只處理了第一份（見下）。
- ΔAUC_total（橫軸 log10 累計評估，對 hammer-frozen）：H8 **0.0**、H24 **+0.356**。
- LTO-SCF∪（P48 對半，A 折提煉的 live comb 凍結套到 B 折）：|U|=5、掉題 0、幾何平均加速 4.10 倍，bootstrap 90% 下界 0.88（< 1，不算確定）。

## layer-2（審查被暴力搜，不讀 H8／H24）

| 掃描 | 變體 | 實跑 | 接受 | 備註 |
|---|---|---|---|---|
| gate（G1 門參數） | 19 | 0（離線重放只得 1 群，積木集全同 base）；另抽 4 個真跑驗證離線去重正確 | 0 | 只有 `mdl_div`、`k`、`max_holes` 在 r09 引擎有作用 |
| route（狀態表） | 30 | 3 代表 | 1：ok 狀態改走 `rt_vsplit` | B 折折外 0 掉題、多解 6 題（三 seed 合計）、節點降 32.8%；多解來自 r08 手寫 halves／nest。只在 scratch 樹，**沒寫進活樹** |
| sieve/exclude（原語留一） | 32 | 32 | 0 | A 折選 len、range、repeat，B 折全擋 |
| sieve/equiv（探針等價，只挖） | 333 支程式 | — | — | 77 個等價類，約 77% 可在生成前剪；已寫信請 S1 加 `forbid` |

細節：[scan/](scan/)、[sieve/README](sieve/README.md)、[stall-replay/README](stall-replay/README.md)（r08 pool 判 starve、meta 判 saturate）。

## 鑄模廠（失蠟法）

- 測試蠟模（`by:test-replay`，B 線手寫，67e8384a）：3 段都擬合成功，產 3 條 comb incubating。只驗管線，**不計 M2(c)**。[foundry/README](foundry/README.md)
- **真蠟模**（epoch 4 stop → b27ca6d3，opus 子 agent 只看 train 寫帶檢查點的程式、程式已銷毀）：三步「大小 2 的物件改塗 8 → 8 的外圈畫 3 → 8 改回 2」。三段在 seed-sub 200k 內**都沒擬合到**，連「8 換回 2」都沒有；產出 0 條 comb、3 條斷裂面（`foundry_witness.jsonl` 的 `wf-b27ca6d3-{0,1,2}`）。原因：空樹的 32 個 list 原語寫「按顏色換色」「按物件大小重塗」要很多節點，蠟模的步太粗。
- epoch 5、8 的兩份請求（74dd1130、2204b7a8）沒處理（20:00 停手；同一原因大概也擬合不到）。

## 快照

`hammer/` 是活樹 `~/code/playground-arc1/ws/hammer/` 收輪時的快照：`curve.csv`（epoch 0～8）、`ops.jsonl`、`ledger.jsonl`、`frozen.json`、`foundry_witness.jsonl`、`wax-b27ca6d3.jsonl`。
